import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import cravat.admin_util as au
import cravat.constants as constants
from cravat.cravat_util import (
    mergesqlite,
    mergesqlite_bucket_chroms,
    mergesqlite_drop_columns,
    mergesqlite_status_json_path,
)

try:
    import scipy.stats  # noqa: F401 - only needed for the casecontrol recompute test

    _HAVE_SCIPY = True
except ImportError:
    _HAVE_SCIPY = False

# The postaggregator-recompute tests below exercise the real tagsampler/
# varmeta/vcfinfo/casecontrol module code (per PLAN-merge-postaggregators.md,
# recompute deliberately runs the real modules rather than reimplementing
# their logic), so they need those modules installed under
# cravat/modules/postaggregators/ (gitignored, not part of this checkout -
# copy them in from a `oc module install-base` module dir to run these).
_POSTAGG_MODULES_AVAILABLE = all(
    au.module_exists_local(name) for name in ("tagsampler", "varmeta", "vcfinfo")
)
_CASECONTROL_AVAILABLE = (
    _POSTAGG_MODULES_AVAILABLE and au.module_exists_local("casecontrol") and _HAVE_SCIPY
)

# Column shapes mirror what real oc-produced result dbs carry: a handful of
# "base__*" key columns plus one arbitrary annotator column per table, so
# the header/annotator consistency checks in mergesqlite() have something
# real to compare.
VARIANT_COLS = [
    ("base__uid", "integer"),
    ("base__chrom", "text"),
    ("base__pos", "integer"),
    ("base__ref_base", "text"),
    ("base__alt_base", "text"),
    ("test__score", "real"),
]
GENE_COLS = [("base__hugo", "text"), ("test__gscore", "real")]
# Real result dbs carry a base__hugo column on variant too (the gene
# mapper's primary-gene call for that variant) - the parallel merge path's
# gene-table bucketing keys off it (see mergesqlite_prune_shard_db1's
# docstring), but the base VARIANT_COLS above (predating OC-833) doesn't
# have one, so the --parallel tests below use this instead.
VARIANT_COLS_WITH_HUGO = [
    ("base__uid", "integer"),
    ("base__chrom", "text"),
    ("base__pos", "integer"),
    ("base__ref_base", "text"),
    ("base__alt_base", "text"),
    ("base__hugo", "text"),
    ("test__score", "real"),
]
SAMPLE_COLS = [
    ("base__uid", "integer"),
    ("base__sample_id", "text"),
    ("base__zygosity", "text"),
]
MAPPING_COLS = [
    ("base__uid", "integer"),
    ("base__fileno", "integer"),
    ("base__transcript", "text"),
]

# Fuller column shapes for the postaggregator-recompute tests: real
# tagsampler/vcfinfo/casecontrol code reads base__tags and
# base__original_line from mapping, and base__phred/filter/alt_reads/
# tot_reads/af/hap_block/hap_strand from sample (vcfinfo only). All
# declared "text" so inserted ints/floats round-trip as the exact strings
# these modules' ';'-joins are asserted against, instead of picking up
# SQLite's REAL-affinity coercion (e.g. 30 -> "30.0").
SAMPLE_COLS_FULL = [
    ("base__uid", "integer"),
    ("base__sample_id", "text"),
    ("base__zygosity", "text"),
    ("base__phred", "text"),
    ("base__filter", "text"),
    ("base__alt_reads", "text"),
    ("base__tot_reads", "text"),
    ("base__af", "text"),
    ("base__hap_block", "text"),
    ("base__hap_strand", "text"),
]
MAPPING_COLS_FULL = [
    ("base__uid", "integer"),
    ("base__fileno", "integer"),
    ("base__transcript", "text"),
    ("base__tags", "text"),
    ("base__original_line", "text"),
]


def _col_def(col_name):
    return json.dumps({"title": col_name, "type": "string"})


def build_db(
    path,
    variants,
    samples,
    mappings,
    genes,
    input_paths,
    variant_annotator_version="1.0.0",
    gene_annotator_version="1.0.0",
    variant_cols=VARIANT_COLS,
    gene_cols=GENE_COLS,
    sample_cols=SAMPLE_COLS,
    mapping_cols=MAPPING_COLS,
    extra_info=None,
):
    """Builds a minimal but real-shaped cravat result sqlite db.

    variants: rows of (uid, chrom, pos, ref, alt, score)
    samples: rows of (uid, sample_id, zygosity)
    mappings: rows of (uid, fileno, transcript)
    genes: rows of (hugo, gscore)
    input_paths: {str(fileno): filepath}
    """
    conn = sqlite3.connect(path)
    c = conn.cursor()

    for table, cols, rows in [
        ("variant", variant_cols, variants),
        ("gene", gene_cols, genes),
        ("sample", sample_cols, samples),
        ("mapping", mapping_cols, mappings),
    ]:
        col_sql = ", ".join(f"{name} {sqltype}" for name, sqltype in cols)
        c.execute(f"create table {table} ({col_sql})")
        placeholders = ",".join("?" * len(cols))
        c.executemany(f"insert into {table} values ({placeholders})", rows)

    for header_table, cols in [
        ("variant_header", variant_cols),
        ("gene_header", gene_cols),
        ("sample_header", sample_cols),
        ("mapping_header", mapping_cols),
    ]:
        c.execute(f"create table {header_table} (col_name text, col_def text)")
        c.executemany(
            f"insert into {header_table} values (?, ?)",
            [(name, _col_def(name)) for name, _ in cols],
        )

    c.execute("create table variant_annotator (name text, displayname text, version text)")
    c.execute(
        "insert into variant_annotator values (?, ?, ?)",
        ("test", "Test Annotator", variant_annotator_version),
    )
    c.execute("create table gene_annotator (name text, displayname text, version text)")
    c.execute(
        "insert into gene_annotator values (?, ?, ?)",
        ("test_gene", "Test Gene Annotator", gene_annotator_version),
    )

    c.execute("create table info (colkey text primary key, colval text)")
    input_paths_str = json.dumps(input_paths).replace('"', "'")
    info_rows = [
        ("_input_paths", input_paths_str),
        ("Input file name", ";".join(input_paths.values())),
        ("Number of unique input variants", str(len(variants))),
        ("Result created at", "2026-01-01 00:00:00"),
        ("Result modified at", "2026-01-01 00:00:00"),
    ]
    if extra_info:
        info_rows.extend(extra_info.items())
    c.executemany("insert into info values (?, ?)", info_rows)

    conn.commit()
    conn.close()


class MergeSqliteTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.db1 = os.path.join(self.tmpdir, "db1.sqlite")
        self.db2 = os.path.join(self.tmpdir, "db2.sqlite")
        self.outpath = os.path.join(self.tmpdir, "merged.sqlite")

    def run_merge(self, paths, **arg_overrides):
        # skip_postaggregator=True by default: these structural-merge tests
        # predate postaggregator recompute (OC-833) and use a deliberately
        # minimal synthetic schema that real postaggregator modules aren't
        # shaped to run against (e.g. no base__tags in mapping). The
        # postaggregator-recompute tests below opt back in explicitly, with
        # a fuller schema.
        arg_defaults = dict(
            path=paths,
            outpath=self.outpath,
            skip_postaggregator=True,
            postaggregators=[],
            module_option=None,
            md=None,
            parallel=False,
            workers=None,
        )
        arg_defaults.update(arg_overrides)
        args = SimpleNamespace(**arg_defaults)
        mergesqlite(args)

    def query(self, sql, params=()):
        conn = sqlite3.connect(self.outpath)
        c = conn.cursor()
        c.execute(sql, params)
        rows = c.fetchall()
        conn.close()
        return rows


class TestSharedVariant(MergeSqliteTestBase):
    def test_shared_variant_merges_sample_and_mapping_rows(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db2.vcf"},
        )

        self.run_merge([self.db1, self.db2])

        variant_rows = self.query("select base__uid from variant")
        self.assertEqual(len(variant_rows), 1, "shared variant must not be duplicated")
        uid = variant_rows[0][0]

        sample_rows = self.query(
            "select base__uid, base__sample_id from sample order by base__sample_id"
        )
        self.assertEqual(
            sample_rows, [(uid, "sample1"), (uid, "sample2")],
            "both samples for the shared variant must be present, under the same uid",
        )

        mapping_rows = self.query("select base__uid from mapping")
        self.assertEqual(
            len(mapping_rows), 2,
            "both mapping rows for the shared variant must be present",
        )
        self.assertTrue(all(r[0] == uid for r in mapping_rows))


class TestUniqueVariants(MergeSqliteTestBase):
    def test_unique_variants_get_noncolliding_uids(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
        )

        self.run_merge([self.db1, self.db2])

        variant_rows = self.query(
            "select base__uid, base__chrom from variant order by base__chrom"
        )
        self.assertEqual(len(variant_rows), 2)
        uids = [r[0] for r in variant_rows]
        self.assertEqual(len(set(uids)), 2, "uids must not collide")

        # Every sample/mapping row must reference one of the real merged uids.
        sample_uids = {r[0] for r in self.query("select base__uid from sample")}
        mapping_uids = {r[0] for r in self.query("select base__uid from mapping")}
        self.assertEqual(sample_uids, set(uids))
        self.assertEqual(mapping_uids, set(uids))


class TestConsistencyChecks(MergeSqliteTestBase):
    def test_mismatched_variant_annotator_version_errors_no_output(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            variant_annotator_version="1.0.0",
        )
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            variant_annotator_version="2.0.0",
        )

        with self.assertRaises(SystemExit):
            self.run_merge([self.db1, self.db2])
        self.assertFalse(os.path.exists(self.outpath))

    def test_mismatched_sample_header_columns_errors_no_output(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        extra_sample_cols = SAMPLE_COLS + [("base__extra", "text")]
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "sample2", "hom", "x")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            sample_cols=extra_sample_cols,
        )

        with self.assertRaises(SystemExit):
            self.run_merge([self.db1, self.db2])
        self.assertFalse(os.path.exists(self.outpath))

    def test_mismatched_mapping_header_columns_errors_no_output(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        extra_mapping_cols = MAPPING_COLS + [("base__extra", "text")]
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_002", "x")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            mapping_cols=extra_mapping_cols,
        )

        with self.assertRaises(SystemExit):
            self.run_merge([self.db1, self.db2])
        self.assertFalse(os.path.exists(self.outpath))

    def test_converter_format_mismatch_errors_when_recomputing_postaggregators(self):
        # vcfinfo/varmeta recompute would otherwise silently use db1's
        # _converter_format alone for the whole merged sample set.
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            extra_info={"_converter_format": "vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            extra_info={"_converter_format": "csv"},
        )

        with self.assertRaises(SystemExit):
            self.run_merge([self.db1, self.db2], skip_postaggregator=False)
        self.assertFalse(os.path.exists(self.outpath))

    def test_converter_format_mismatch_allowed_with_skip_postaggregator(self):
        # With no recompute happening, a converter-format mismatch is
        # someone else's problem (out of scope here, same as before OC-833).
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            extra_info={"_converter_format": "vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            extra_info={"_converter_format": "csv"},
        )

        self.run_merge([self.db1, self.db2], skip_postaggregator=True)
        self.assertTrue(os.path.exists(self.outpath))

    def test_mixed_null_and_string_sample_ids_does_not_crash(self):
        # A stray NULL base__sample_id alongside real ones (e.g. a db that
        # hasn't been through tagsampler's setup(), which is what normally
        # normalizes nulls to "no-sample") must not crash the pre-merge
        # info-gathering pass.
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, None, "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
        )

        self.run_merge([self.db1, self.db2])

        self.assertTrue(os.path.exists(self.outpath))
        sample_ids = {r[0] for r in self.query("select base__sample_id from sample")}
        self.assertEqual(sample_ids, {None, "sample2"})


class TestMergedInfo(MergeSqliteTestBase):
    def test_merged_info_has_recomputed_variant_count_and_input_paths(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[
                (1, "chr1", 100, "A", "T", 0.5),  # shared with db1
                (2, "chr2", 200, "C", "G", 0.7),  # unique to db2
            ],
            samples=[(1, "sample2", "hom"), (2, "sample2", "hom")],
            mappings=[(1, 0, "NM_001"), (2, 0, "NM_002")],
            genes=[("GENE1", 0.9), ("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
        )

        self.run_merge([self.db1, self.db2])

        n_variant_rows = self.query("select count(*) from variant")[0][0]
        self.assertEqual(n_variant_rows, 2)

        colval = self.query(
            'select colval from info where colkey="Number of unique input variants"'
        )[0][0]
        self.assertEqual(int(colval), n_variant_rows)

        input_paths_raw = self.query(
            'select colval from info where colkey="_input_paths"'
        )[0][0]
        input_paths = json.loads(input_paths_raw.replace("'", '"'))
        self.assertEqual(set(input_paths.values()), {"/in/db1.vcf", "/in/db2.vcf"})


class TestSampleIdCollision(MergeSqliteTestBase):
    def test_collision_no_label_errors_no_output(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "SAMPLE1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "SAMPLE1", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
        )

        with self.assertRaises(SystemExit):
            self.run_merge([self.db1, self.db2])
        self.assertFalse(os.path.exists(self.outpath))

    def test_collision_with_label_renames_only_labeled_db(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "SAMPLE1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "SAMPLE1", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
        )

        self.run_merge([self.db1, f"{self.db2}:cohortB"])

        sample_ids = {r[0] for r in self.query("select base__sample_id from sample")}
        self.assertEqual(sample_ids, {"SAMPLE1", "cohortB__SAMPLE1"})

    def test_collision_with_label_on_first_db_still_renames(self):
        # Exercises the rename applied to the already-copied base db,
        # rather than to a db merged in later.
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "SAMPLE1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "C", "G", 0.7)],
            samples=[(1, "SAMPLE1", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
        )

        self.run_merge([f"{self.db1}:cohortA", self.db2])

        sample_ids = {r[0] for r in self.query("select base__sample_id from sample")}
        self.assertEqual(sample_ids, {"cohortA__SAMPLE1", "SAMPLE1"})


class TestNewUidCounterClobbered(MergeSqliteTestBase):
    def test_third_dbs_new_variant_does_not_reuse_second_dbs_new_uid(self):
        # Regression test for the `new_uid` running-counter variable being
        # clobbered: the Sample/Mapping blocks reuse `new_uid` as a loop
        # scratch variable (`new_uid = uid_dic[uid]`), stomping on the
        # counter the Variant block relies on to hand out fresh, unused
        # base__uid values across every remaining dbpath.
        #
        # db1 contributes one variant (uid 1).
        # db2 contributes that *same* variant (shared with db1) plus one
        # brand-new variant, and has sample/mapping rows for both -
        # processing the shared-variant sample row after the new-variant
        # variant row is what clobbers `new_uid` back down.
        # db3 then contributes one more brand-new variant. With a correct
        # running counter it must get a uid distinct from every uid used
        # so far; the bug hands it db2's new variant's uid instead.
        db3 = os.path.join(self.tmpdir, "db3.sqlite")

        build_db(
            self.db1,
            variants=[(1, "1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[
                (1, "1", 100, "A", "T", 0.5),  # shared with db1
                (2, "2", 200, "C", "G", 0.7),  # new
            ],
            samples=[(1, "sample2", "het"), (2, "sample3", "het")],
            mappings=[(1, 0, "NM_001"), (2, 0, "NM_002")],
            genes=[("GENE1", 0.9), ("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
        )
        build_db(
            db3,
            variants=[(1, "3", 300, "G", "A", 0.9)],  # new
            samples=[(1, "sample4", "het")],
            mappings=[(1, 0, "NM_003")],
            genes=[("GENE3", 0.1)],
            input_paths={"0": "/in/db3.vcf"},
        )

        self.run_merge([self.db1, self.db2, db3])

        variant_rows = self.query("select base__uid, base__chrom from variant")
        self.assertEqual(
            len(variant_rows), 3, "all three distinct variants must be present"
        )
        uids = [r[0] for r in variant_rows]
        self.assertEqual(
            len(set(uids)), 3,
            f"every distinct variant must get its own base__uid, got {uids}",
        )

        uid_by_chrom = {chrom: uid for uid, chrom in variant_rows}
        sample4_uid = self.query(
            'select base__uid from sample where base__sample_id="sample4"'
        )[0][0]
        self.assertEqual(
            sample4_uid, uid_by_chrom["3"],
            "sample4 must be attached to db3's own new variant, not an "
            "earlier variant whose uid got reused",
        )


class TestVariantIdDelimiterCollision(MergeSqliteTestBase):
    def test_distinct_variants_with_colliding_concatenated_id_stay_distinct(self):
        # Regression test for variant_id()'s undelimited concatenation
        # (chrom + str(pos) + ref + alt): chrom="1"/pos=234 and
        # chrom="12"/pos=34 both concatenate to "1234", so with the same
        # ref/alt these two genuinely different variants collide onto the
        # same id string.
        build_db(
            self.db1,
            variants=[(1, "1", 234, "A", "G", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "12", 34, "A", "G", 0.7)],
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
        )

        self.run_merge([self.db1, self.db2])

        variant_rows = self.query(
            "select base__uid, base__chrom, base__pos from variant"
        )
        self.assertEqual(
            len(variant_rows), 2,
            "chr1:234 and chr12:34 are distinct variants and must both be "
            "present, despite variant_id() concatenating them the same way",
        )

        uid_by_locus = {(chrom, pos): uid for uid, chrom, pos in variant_rows}
        sample_uids = dict(
            self.query("select base__sample_id, base__uid from sample")
        )
        self.assertEqual(
            sample_uids["sample1"], uid_by_locus[("1", 234)],
            "sample1 belongs to the chr1:234 variant",
        )
        self.assertEqual(
            sample_uids["sample2"], uid_by_locus[("12", 34)],
            "sample2 belongs to the chr12:34 variant, not chr1:234's uid",
        )


class TestRepeatedInputFileAcrossDbs(MergeSqliteTestBase):
    def test_merging_dbs_with_shared_input_filepath_does_not_crash(self):
        # Regression test for fileno_dic only recording an entry for a
        # source db's fileno when that db's input filepath is *new* to the
        # merge, while the Mapping block unconditionally looks up every
        # row's fileno in fileno_dic - so a later db whose input filepath
        # was already contributed by an earlier db raises a KeyError.
        build_db(
            self.db1,
            variants=[(1, "1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/shared.vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "2", 200, "C", "G", 0.7)],
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/shared.vcf"},  # same filepath as db1
        )

        self.run_merge([self.db1, self.db2])

        mapping_rows = self.query(
            "select base__uid, base__fileno from mapping order by base__uid"
        )
        self.assertEqual(len(mapping_rows), 2, "both mapping rows must be merged in")
        filenos = {fileno for _, fileno in mapping_rows}
        self.assertEqual(
            len(filenos), 1,
            "both mapping rows point at the same shared input file and "
            "must resolve to the same merged fileno",
        )


class TestDuplicateDbpathLabels(MergeSqliteTestBase):
    def test_same_physical_db_merged_twice_with_different_labels(self):
        # Regression test for `labels` being a dict keyed by the resolved
        # dbpath string: passing the same physical file twice with two
        # different :label suffixes silently drops the first label, since
        # the second assignment overwrites labels[dbpath].
        build_db(
            self.db1,
            variants=[(1, "1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "2", 200, "C", "G", 0.7)],
            samples=[(1, "SAMPLE_X", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
        )

        self.run_merge([self.db1, f"{self.db2}:cohortA", f"{self.db2}:cohortB"])

        sample_ids = {r[0] for r in self.query("select base__sample_id from sample")}
        self.assertEqual(
            sample_ids,
            {"sample1", "cohortA__SAMPLE_X", "cohortB__SAMPLE_X"},
            "each :label suffix on the same physical db must be honored "
            "independently, not collapsed to the last one seen",
        )


class TestColumnOrderMismatch(MergeSqliteTestBase):
    def test_same_column_names_different_order_errors_no_output(self):
        # Regression test for mergesqlite_check_info() sorting column names
        # before comparing them: two dbs with the same column *set* but a
        # different physical *order* used to pass the check even though
        # the merge loop reads/writes rows positionally, using db1's
        # column order for every db - a same-named-but-reordered column
        # (e.g. ref_base/alt_base swapped) would silently merge wrong
        # values into the output with no error at all.
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
        )
        # Same column names as VARIANT_COLS, but ref_base/alt_base swapped.
        reordered_variant_cols = [
            ("base__uid", "integer"),
            ("base__chrom", "text"),
            ("base__pos", "integer"),
            ("base__alt_base", "text"),
            ("base__ref_base", "text"),
            ("test__score", "real"),
        ]
        build_db(
            self.db2,
            variants=[(1, "chr2", 200, "G", "C", 0.7)],  # matches reordered cols
            samples=[(1, "sample2", "hom")],
            mappings=[(1, 0, "NM_002")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            variant_cols=reordered_variant_cols,
        )

        with self.assertRaises(SystemExit):
            self.run_merge([self.db1, self.db2])
        self.assertFalse(os.path.exists(self.outpath))


def build_nonvcf_pair(db1_path, db2_path):
    """A 2-variant, 3-sample merge scenario shaped for postaggregator
    recompute: db1 and db2 share the chr1:100 variant (contributing
    sample1/sample2 respectively), and db2 alone contributes a second,
    unique chr2:200 variant (sample3). Non-vcf converter format, so
    tagsampler and varmeta both run on recompute but vcfinfo doesn't
    (mirrors real dbs: vcfinfo and varmeta are mutually exclusive, gated
    on opposite sides of the same "_converter_format"=="vcf" check)."""
    build_db(
        db1_path,
        variants=[(1, "chr1", 100, "A", "T", 0.5)],
        samples=[(1, "sample1", "het", None, None, None, None, None, None, None)],
        mappings=[(1, 0, "NM_001", None, "line-a")],
        genes=[("GENE1", 0.9)],
        input_paths={"0": "/in/db1.vcf"},
        sample_cols=SAMPLE_COLS_FULL,
        mapping_cols=MAPPING_COLS_FULL,
        extra_info={"_converter_format": "csv"},
    )
    build_db(
        db2_path,
        variants=[
            (1, "chr1", 100, "A", "T", 0.5),  # shared with db1
            (2, "chr2", 200, "C", "G", 0.7),  # new
        ],
        samples=[
            (1, "sample2", "hom", None, None, None, None, None, None, None),
            (2, "sample3", "het", None, None, None, None, None, None, None),
        ],
        mappings=[
            (1, 0, "NM_001", None, "line-b"),
            (2, 0, "NM_002", None, "line-c"),
        ],
        genes=[("GENE1", 0.9), ("GENE2", 0.3)],
        input_paths={"0": "/in/db2.vcf"},
        sample_cols=SAMPLE_COLS_FULL,
        mapping_cols=MAPPING_COLS_FULL,
        extra_info={"_converter_format": "csv"},
    )


class TestDropColumnsIndexHandling(unittest.TestCase):
    """Exercises mergesqlite_drop_columns() directly against a raw sqlite3
    connection, rather than through mergesqlite() - no real postaggregator
    modules needed, since this is purely a schema-surgery helper."""

    def test_drops_covering_index_without_crashing_and_keeps_other_indexes(self):
        conn = sqlite3.connect(":memory:")
        c = conn.cursor()
        c.execute("create table t (a text, b text, c text)")
        c.execute("create index idx_b on t(b)")
        c.execute("create index idx_c on t(c)")
        c.execute("insert into t values ('a1', 'b1', 'c1')")

        mergesqlite_drop_columns(conn, "t", ["b"])

        c.execute("select * from t")
        self.assertEqual(c.fetchall(), [("a1", "c1")])
        c.execute("select name from sqlite_master where type='index'")
        self.assertEqual(
            {r[0] for r in c.fetchall()}, {"idx_c"},
            "idx_b (on the dropped column) must go; idx_c (untouched) must survive",
        )
        conn.close()


class TestPostaggregatorFlagValidation(MergeSqliteTestBase):
    def test_p_nonexistent_module_errors_no_output(self):
        build_nonvcf_pair(self.db1, self.db2)

        with self.assertRaises(SystemExit):
            self.run_merge(
                [self.db1, self.db2],
                skip_postaggregator=False,
                postaggregators=["zzz_mergesqlite_test_nonexistent_module"],
            )
        self.assertFalse(os.path.exists(self.outpath))

    def test_missing_default_postaggregator_is_silently_skipped_not_errored(self):
        # Unlike an explicit -p name, a default (tagsampler/casecontrol/
        # varmeta/vcfinfo) that isn't installed locally shouldn't block
        # the merge - it's just not recomputed.
        build_nonvcf_pair(self.db1, self.db2)

        with mock.patch("cravat.cravat_util.au.module_exists_local", return_value=False):
            self.run_merge([self.db1, self.db2], skip_postaggregator=False)

        self.assertTrue(os.path.exists(self.outpath))


class TestMdFlag(MergeSqliteTestBase):
    def test_md_redirects_module_resolution(self):
        # An empty --md dir has none of the default postaggregators, so if
        # --md is actually being honored here, none of them run -
        # regardless of what's really installed in this checkout's normal
        # modules_dir. (Unlike oc run's gene mapper, mergesqlite does all
        # its module resolution in the one process that parses --md, with
        # no multiprocessing involved, so this doesn't hit the forkserver
        # issue --md has there.)
        build_nonvcf_pair(self.db1, self.db2)
        fake_md = os.path.join(self.tmpdir, "empty_modules_dir")
        os.makedirs(fake_md, exist_ok=True)
        prior_md = constants.custom_modules_dir
        self.addCleanup(setattr, constants, "custom_modules_dir", prior_md)

        self.run_merge([self.db1, self.db2], skip_postaggregator=False, md=fake_md)

        self.assertEqual(au.get_modules_dir(), fake_md)
        postagg_cols = self.query(
            "select col_name from variant_header where "
            'col_name like "tagsampler__%" or col_name like "varmeta__%" or '
            'col_name like "vcfinfo__%" or col_name like "casecontrol__%"'
        )
        self.assertEqual(
            postagg_cols, [],
            "no default postaggregator exists in the empty --md dir, so "
            "none should have run",
        )


class TestPostaggregatorRecomputeFailureCleanup(MergeSqliteTestBase):
    def test_recompute_failure_removes_incomplete_output_and_status_json(self):
        build_nonvcf_pair(self.db1, self.db2)
        status_json_path = mergesqlite_status_json_path(self.outpath)
        fake_module_info = SimpleNamespace(
            script_path="/nonexistent/path/zzz_mergesqlite_test_fake_postagg.py",
            conf={},
        )

        with mock.patch(
            "cravat.cravat_util.mergesqlite_is_local_postaggregator", return_value=False
        ), mock.patch(
            "cravat.cravat_util.au.module_exists_local", return_value=True
        ), mock.patch(
            "cravat.cravat_util.au.get_local_module_info", return_value=fake_module_info
        ):
            with self.assertRaises(Exception):
                self.run_merge([self.db1, self.db2], skip_postaggregator=False)

        self.assertFalse(
            os.path.exists(self.outpath),
            "a failed recompute must not leave a half-finished output file behind",
        )
        self.assertFalse(
            os.path.exists(status_json_path),
            "the .status.json the failed recompute wrote must be cleaned up too",
        )


@unittest.skipUnless(
    _POSTAGG_MODULES_AVAILABLE,
    "tagsampler/varmeta/vcfinfo postaggregator modules are not installed locally",
)
class TestPostaggregatorRecomputeDefaultsNonVcf(MergeSqliteTestBase):
    def test_defaults_recompute_tagsampler_and_varmeta_not_vcfinfo_or_casecontrol(self):
        build_nonvcf_pair(self.db1, self.db2)

        self.run_merge([self.db1, self.db2], skip_postaggregator=False)

        uid_by_chrom = dict(self.query("select base__chrom, base__uid from variant"))
        tagsampler_by_uid = dict(
            self.query(
                "select base__uid, tagsampler__numsample || ':' || tagsampler__samples "
                "from variant"
            )
        )
        self.assertEqual(
            tagsampler_by_uid[uid_by_chrom["chr1"]],
            "2:sample1;sample2",
            "tagsampler__numsample/samples must reflect the merged sample "
            "set (sample1 from db1 + sample2 from db2), not either input "
            "db's own sample set alone",
        )
        self.assertEqual(tagsampler_by_uid[uid_by_chrom["chr2"]], "1:sample3")

        varmeta_by_uid = dict(
            self.query("select base__uid, varmeta__zygosity from variant")
        )
        self.assertEqual(varmeta_by_uid[uid_by_chrom["chr1"]], "het;hom")
        self.assertEqual(varmeta_by_uid[uid_by_chrom["chr2"]], "het")

        # vcfinfo is vcf-only (check() requires _converter_format=="vcf") and
        # casecontrol no-ops with no cohorts conf given - neither should
        # have run at all, so neither should have added any column.
        for module_name in ("vcfinfo", "casecontrol"):
            self.assertEqual(
                self.query(
                    f'select count(*) from variant_header where col_name like "{module_name}__%"'
                )[0][0],
                0,
                f"{module_name} should not have run",
            )


@unittest.skipUnless(
    _POSTAGG_MODULES_AVAILABLE,
    "tagsampler/varmeta/vcfinfo postaggregator modules are not installed locally",
)
class TestPostaggregatorRecomputeDefaultsVcf(MergeSqliteTestBase):
    def test_defaults_recompute_vcfinfo_not_varmeta_for_vcf_source(self):
        # varmeta and vcfinfo can't both run on the same db (their check()
        # conditions are each other's opposite on "_converter_format"), so
        # the vcf side of "varmeta/vcfinfo columns present and correct" is
        # covered here rather than in the non-vcf scenario above.
        # hap_block/hap_strand are left None here: vcfinfo.yml declares
        # them type "int", which setup() only widens for single-sample
        # jobs, so a multi-sample join like "1;2" gets written back
        # unquoted (base_postaggregator.write_output() only quotes
        # col_type=="string") - a preexisting vcfinfo bug, out of scope
        # here per the plan ("no reimplementation of module logic"), that
        # happens to only surface on modern sqlite3's single-statement
        # enforcement. Leaving them unset nulls the column out cleanly
        # instead (empty-string join -> None) and sidesteps it.
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het", 30, "PASS", 5, 10, 0.5, None, None)],
            mappings=[(1, 0, "NM_001", None, "line-a")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "vcf"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],  # shared with db1
            samples=[(1, "sample2", "hom", 40, "PASS", 8, 10, 0.8, None, None)],
            mappings=[(1, 0, "NM_001", None, "line-b")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db2.vcf"},
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "vcf"},
        )

        self.run_merge([self.db1, self.db2], skip_postaggregator=False)

        row = self.query(
            "select vcfinfo__phred, vcfinfo__filter, vcfinfo__zygosity, "
            "vcfinfo__alt_reads, vcfinfo__tot_reads, vcfinfo__af, "
            "vcfinfo__hap_block, vcfinfo__hap_strand from variant"
        )[0]
        self.assertEqual(
            row,
            ("30;40", "PASS;PASS", "het;hom", "5;8", "10;10", "0.5;0.8", None, None),
            "vcfinfo columns must reflect both merged samples (multi_sample "
            "is recomputed from the merged sample set), not just db1's",
        )

        self.assertEqual(
            self.query(
                'select count(*) from variant_header where col_name like "varmeta__%"'
            )[0][0],
            0,
            "varmeta should not have run (check() requires non-vcf)",
        )


@unittest.skipUnless(
    _POSTAGG_MODULES_AVAILABLE,
    "tagsampler/varmeta/vcfinfo postaggregator modules are not installed locally",
)
class TestSkipPostaggregatorFlag(MergeSqliteTestBase):
    def test_skip_postaggregator_leaves_no_postaggregator_columns(self):
        build_nonvcf_pair(self.db1, self.db2)

        self.run_merge([self.db1, self.db2], skip_postaggregator=True)

        postagg_cols = self.query(
            "select col_name from variant_header where "
            'col_name like "tagsampler__%" or col_name like "varmeta__%" or '
            'col_name like "vcfinfo__%" or col_name like "casecontrol__%"'
        )
        self.assertEqual(
            postagg_cols, [], "no postaggregator column should exist with nothing re-run"
        )


@unittest.skipUnless(
    _POSTAGG_MODULES_AVAILABLE,
    "tagsampler/varmeta/vcfinfo postaggregator modules are not installed locally",
)
class TestAdditivePFlag(MergeSqliteTestBase):
    def test_p_tagsampler_redundant_with_defaults_gives_same_result(self):
        build_nonvcf_pair(self.db1, self.db2)

        self.run_merge(
            [self.db1, self.db2],
            skip_postaggregator=False,
            postaggregators=["tagsampler"],
        )

        uid_by_chrom = dict(self.query("select base__chrom, base__uid from variant"))
        tagsampler_by_uid = dict(
            self.query(
                "select base__uid, tagsampler__numsample || ':' || tagsampler__samples "
                "from variant"
            )
        )
        self.assertEqual(tagsampler_by_uid[uid_by_chrom["chr1"]], "2:sample1;sample2")
        self.assertEqual(tagsampler_by_uid[uid_by_chrom["chr2"]], "1:sample3")

        # -p is additive, not an override: varmeta (a default) must still
        # have run even though only tagsampler was named explicitly.
        self.assertEqual(
            self.query(
                'select count(*) from variant_header where col_name like "varmeta__%"'
            )[0][0],
            1,
        )


@unittest.skipUnless(
    _CASECONTROL_AVAILABLE,
    "casecontrol postaggregator module (and/or scipy) is not available locally",
)
class TestPostaggregatorRecomputeCasecontrolModuleOption(MergeSqliteTestBase):
    def test_module_option_casecontrol_cohorts_runs_casecontrol(self):
        from scipy.stats import fisher_exact

        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],
            samples=[(1, "sample1", "het", None, None, None, None, None, None, None)],
            mappings=[(1, 0, "NM_001", None, "line-a")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "csv"},
        )
        build_db(
            self.db2,
            variants=[(1, "chr1", 100, "A", "T", 0.5)],  # shared with db1
            samples=[(1, "sample2", "hom", None, None, None, None, None, None, None)],
            mappings=[(1, 0, "NM_001", None, "line-b")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db2.vcf"},
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "csv"},
        )

        cohorts_path = os.path.join(self.tmpdir, "cohorts.txt")
        with open(cohorts_path, "w") as f:
            f.write("sample1 case\nsample2 control\n")

        # contrast with the no-op case in
        # TestPostaggregatorRecomputeDefaultsNonVcf: with cohorts conf
        # given, casecontrol now finds it via check() and actually runs.
        self.run_merge(
            [self.db1, self.db2],
            skip_postaggregator=False,
            module_option=[f"casecontrol.cohorts={cohorts_path}"],
        )

        row = self.query(
            "select casecontrol__dom_pvalue, casecontrol__rec_pvalue, "
            "casecontrol__all_pvalue, casecontrol__hom_case, "
            "casecontrol__het_case, casecontrol__ref_case, "
            "casecontrol__hom_cont, casecontrol__het_cont, "
            "casecontrol__ref_cont, casecontrol__multiallelic from variant"
        )[0]
        (
            dom_pvalue, rec_pvalue, all_pvalue,
            hom_case, het_case, ref_case,
            hom_cont, het_cont, ref_cont,
            multiallelic,
        ) = row

        # sample1 (case) is het, sample2 (control) is hom.
        self.assertEqual((hom_case, het_case, ref_case), (0, 1, 0))
        self.assertEqual((hom_cont, het_cont, ref_cont), (1, 0, 0))
        self.assertAlmostEqual(dom_pvalue, fisher_exact([[1, 0], [1, 0]], "greater")[1])
        self.assertAlmostEqual(rec_pvalue, fisher_exact([[0, 1], [1, 0]], "greater")[1])
        self.assertAlmostEqual(all_pvalue, fisher_exact([[1, 0], [2, 0]], "greater")[1])
        self.assertIsNone(
            multiallelic,
            "db1 and db2's mapping rows for the shared variant have "
            "distinct base__original_line values, so it isn't multiallelic",
        )


class TestBucketChroms(unittest.TestCase):
    """Unit tests of mergesqlite_bucket_chroms() directly, independent of
    a full merge - the load-balancing logic the --parallel path relies
    on. No chromosome pairing/co-location logic to test here: every
    chromosome (including chrX/chrY) is just its own independently-
    weighted bucketing item - gene handling doesn't depend on chromosome
    bucketing at all (mergesqlite_merge_genes() merges the gene table
    once, globally - see OC-833 production decision 2), so there's
    nothing left for bucketing to coordinate around."""

    def test_every_chromosome_assigned_to_exactly_one_bucket(self):
        weights = {"chr1": 100, "chr2": 90, "chrX": 5, "chrY": 5}
        buckets = mergesqlite_bucket_chroms(weights, n_workers=4)
        self.assertEqual(
            {c for b in buckets for c in b}, set(weights.keys()),
            "every chromosome must be assigned to exactly one bucket",
        )
        all_chroms = [c for b in buckets for c in b]
        self.assertEqual(len(all_chroms), len(set(all_chroms)))

    def test_never_produces_more_buckets_than_distinct_items(self):
        # 3 chromosomes even though 8 workers are requested - no point
        # spawning empty-bucket workers.
        weights = {"chr1": 10, "chr2": 10, "chr3": 1}
        buckets = mergesqlite_bucket_chroms(weights, n_workers=8)
        self.assertEqual(len(buckets), 3)

    def test_balances_by_weight_not_just_chromosome_count(self):
        # One huge chromosome plus four tiny ones, 2 workers: the huge one
        # must not share a bucket with any of the tiny ones if a
        # single-tiny-chromosome bucket would be better balanced.
        weights = {"chr1": 1000, "chr2": 1, "chr3": 1, "chr4": 1, "chr5": 1}
        buckets = mergesqlite_bucket_chroms(weights, n_workers=2)
        self.assertEqual(len(buckets), 2)
        big_bucket = next(b for b in buckets if "chr1" in b)
        self.assertEqual(big_bucket, ["chr1"])


class ParallelMergeSqliteTestBase(MergeSqliteTestBase):
    """Extends MergeSqliteTestBase with a second output path, so tests can
    run both the serial and parallel paths over the same input dbs and
    compare their output directly."""

    def setUp(self):
        super().setUp()
        self.serial_outpath = os.path.join(self.tmpdir, "merged_serial.sqlite")
        self.parallel_outpath = os.path.join(self.tmpdir, "merged_parallel.sqlite")

    def run_merge_to(self, paths, outpath, **arg_overrides):
        arg_defaults = dict(
            path=paths,
            outpath=outpath,
            skip_postaggregator=True,
            postaggregators=[],
            module_option=None,
            md=None,
            parallel=False,
            workers=None,
        )
        arg_defaults.update(arg_overrides)
        args = SimpleNamespace(**arg_defaults)
        mergesqlite(args)

    def query_path(self, dbpath, sql, params=()):
        conn = sqlite3.connect(dbpath)
        c = conn.cursor()
        c.execute(sql, params)
        rows = c.fetchall()
        conn.close()
        return rows

    def variant_keys(self, dbpath):
        return {
            (chrom, pos, ref, alt)
            for chrom, pos, ref, alt in self.query_path(
                dbpath,
                "select base__chrom, base__pos, base__ref_base, base__alt_base from variant",
            )
        }

    def gene_names(self, dbpath):
        return {r[0] for r in self.query_path(dbpath, "select base__hugo from gene")}

    def samples_by_variant_key(self, dbpath):
        uid_to_key = {
            r[0]: r[1:]
            for r in self.query_path(
                dbpath,
                "select base__uid, base__chrom, base__pos, base__ref_base, base__alt_base "
                "from variant",
            )
        }
        return {
            (uid_to_key[uid], sample_id, zygosity)
            for uid, sample_id, zygosity in self.query_path(
                dbpath, "select base__uid, base__sample_id, base__zygosity from sample"
            )
        }


class TestParallelBasicMerge(ParallelMergeSqliteTestBase):
    def test_shared_and_unique_variants_merge_correctly_in_parallel(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", "GENE1", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )
        build_db(
            self.db2,
            variants=[
                (1, "chr1", 100, "A", "T", "GENE1", 0.5),  # shared with db1
                (2, "chr2", 200, "C", "G", "GENE2", 0.7),  # unique to db2
            ],
            samples=[(1, "sample2", "hom"), (2, "sample3", "het")],
            mappings=[(1, 0, "NM_001"), (2, 0, "NM_002")],
            genes=[("GENE1", 0.9), ("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )

        self.run_merge_to(
            [self.db1, self.db2], self.parallel_outpath, parallel=True, workers=3,
        )

        variant_rows = self.query_path(
            self.parallel_outpath, "select base__uid, base__chrom from variant"
        )
        self.assertEqual(len(variant_rows), 2, "shared variant must not be duplicated")
        uids = [r[0] for r in variant_rows]
        self.assertEqual(len(uids), len(set(uids)), "uids must be unique across shards")

        self.assertEqual(
            self.variant_keys(self.parallel_outpath),
            {("chr1", 100, "A", "T"), ("chr2", 200, "C", "G")},
        )
        self.assertEqual(self.gene_names(self.parallel_outpath), {"GENE1", "GENE2"})

        uid_by_chrom = dict(
            self.query_path(self.parallel_outpath, "select base__chrom, base__uid from variant")
        )
        sample_ids_chr1 = {
            r[0]
            for r in self.query_path(
                self.parallel_outpath,
                "select base__sample_id from sample where base__uid=?",
                (uid_by_chrom["chr1"],),
            )
        }
        self.assertEqual(sample_ids_chr1, {"sample1", "sample2"})


class TestParallelAltContigGeneDedup(ParallelMergeSqliteTestBase):
    """Regression test for a real edge case found while validating OC-833
    against pilot scale-test data: a gene mapper can call the same hugo
    symbol on a primary chromosome AND one of its ALT contigs (e.g. real
    data had "TBC1D3B" on both "chr17" and "chr17_KI270909v1_alt") - two
    different chrom buckets (mergesqlite_bucket_chroms has no chrom
    pairing/co-location logic at all - every chromosome, including
    chrX/chrY, is just its own independently-weighted bucketing item), so
    a naive per-shard gene table could end up with this hugo duplicated
    across shards. mergesqlite_merge_genes() sidesteps that entirely by
    merging the gene table once, globally, directly from the original
    input dbs - independent of chromosome bucketing - so this hugo
    dedupes correctly regardless of which bucket either chromosome
    landed in."""

    def test_same_hugo_on_primary_and_alt_contig_dedupes_after_concatenation(self):
        build_db(
            self.db1,
            variants=[(1, "chr17", 100, "A", "T", "TBC1D3B", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("TBC1D3B", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )
        build_db(
            self.db2,
            variants=[(1, "chr17_KI270909v1_alt", 200, "C", "G", "TBC1D3B", 0.7)],
            samples=[(1, "sample2", "het")],
            mappings=[(1, 0, "NM_002")],
            genes=[("TBC1D3B", 0.9)],
            input_paths={"0": "/in/db2.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )

        # Neither chrom is chrX/chrY, so with enough workers these two
        # land in different buckets/shards, each independently adding its
        # own TBC1D3B gene row (correctly, from its own shard's point of
        # view - see mergesqlite_prune_shard_db1's docstring).
        self.run_merge_to(
            [self.db1, self.db2], self.parallel_outpath, parallel=True, workers=2,
        )

        self.assertEqual(self.gene_names(self.parallel_outpath), {"TBC1D3B"})
        self.assertEqual(
            self.query_path(self.parallel_outpath, "select count(*) from gene")[0][0], 1,
            "the same hugo referenced from two different (non-PAR-paired) "
            "chrom buckets must still dedupe to one gene row",
        )
        self.assertEqual(
            self.variant_keys(self.parallel_outpath),
            {("chr17", 100, "A", "T"), ("chr17_KI270909v1_alt", 200, "C", "G")},
        )


class TestParallelFilenoConsistency(ParallelMergeSqliteTestBase):
    def test_same_physical_input_file_gets_one_fileno_across_shards(self):
        # fileA.vcf is referenced by db1 (chrX, chr1's db1-side row) and
        # db3 (chr3) - three mapping rows, spread across what should be
        # 3 different shards, that must all resolve to the same fileno.
        # fileB.vcf is referenced only by db2 (chr1's db2-side row, chr2,
        # chrY) - a second, different-but-internally-consistent fileno.
        build_db(
            self.db1,
            variants=[
                (1, "chr1", 100, "A", "T", "GENE1", 0.5),
                (2, "chrX", 500, "G", "C", "PARGENE", 0.2),
            ],
            samples=[(1, "s1", "het"), (2, "s2", "het")],
            mappings=[(1, 0, "NM_001A"), (2, 0, "NM_0X")],
            genes=[("GENE1", 0.9), ("PARGENE", 0.5)],
            input_paths={"0": "/in/fileA.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )
        db2 = os.path.join(self.tmpdir, "db2.sqlite")
        build_db(
            db2,
            variants=[
                (1, "chr1", 100, "A", "T", "GENE1", 0.5),  # shared with db1
                (2, "chr2", 200, "C", "G", "GENE2", 0.7),
                (3, "chrY", 600, "T", "A", "PARGENE", 0.4),
            ],
            samples=[(1, "s3", "hom"), (2, "s4", "het"), (3, "s5", "het")],
            mappings=[(1, 0, "NM_001B"), (2, 0, "NM_002"), (3, 0, "NM_0Y")],
            genes=[("GENE1", 0.9), ("GENE2", 0.3), ("PARGENE", 0.5)],
            input_paths={"0": "/in/fileB.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )
        db3 = os.path.join(self.tmpdir, "db3.sqlite")
        build_db(
            db3,
            variants=[(1, "chr3", 300, "A", "G", "GENE3", 0.1)],
            samples=[(1, "s6", "het")],
            mappings=[(1, 0, "NM_003")],
            genes=[("GENE3", 0.6)],
            input_paths={"0": "/in/fileA.vcf"},  # same physical file as db1
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )

        self.run_merge_to(
            [self.db1, db2, db3], self.parallel_outpath, parallel=True, workers=4,
        )

        fileno_by_transcript = dict(
            self.query_path(
                self.parallel_outpath, "select base__transcript, base__fileno from mapping"
            )
        )
        file_a_filenos = {
            fileno_by_transcript[t] for t in ("NM_001A", "NM_0X", "NM_003")
        }
        file_b_filenos = {
            fileno_by_transcript[t] for t in ("NM_001B", "NM_002", "NM_0Y")
        }
        self.assertEqual(
            len(file_a_filenos), 1,
            "every mapping row from fileA.vcf must resolve to the same fileno "
            "across shards",
        )
        self.assertEqual(
            len(file_b_filenos), 1,
            "every mapping row from fileB.vcf must resolve to the same fileno "
            "across shards",
        )
        self.assertNotEqual(
            file_a_filenos, file_b_filenos,
            "fileA.vcf and fileB.vcf are different physical files and must "
            "get different filenos",
        )


class TestParallelUidsGloballyUnique(ParallelMergeSqliteTestBase):
    """OC-833 production decision 1: shards no longer allocate uids from
    private fixed-width blocks (with a hard-fail on overflow) - each
    shard allocates new variant uids independently, starting from the
    same shared value, and mergesqlite_concatenate_shards() gives every
    row a fresh, globally-unique uid as it copies. This exercises a case
    that would have collided under local, unrenumbered shard uids: many
    new variants (more than old prototype's hard-fail threshold in the
    now-removed test would have allowed) split across chrom buckets."""

    def test_many_new_variants_across_shards_get_unique_uids(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", "GENE1", 0.5)],
            samples=[(1, "sample1", "het")],
            mappings=[(1, 0, "NM_001")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )
        build_db(
            self.db2,
            variants=[
                (1, "chr1", 200, "C", "G", "GENE2", 0.7),  # new, shard chr1
                (2, "chr1", 300, "G", "A", "GENE2", 0.3),  # new, shard chr1
                (3, "chr2", 400, "T", "C", "GENE3", 0.1),  # new, shard chr2
                (4, "chr2", 500, "A", "C", "GENE3", 0.2),  # new, shard chr2
            ],
            samples=[
                (1, "sample2", "het"), (2, "sample3", "het"),
                (3, "sample4", "het"), (4, "sample5", "het"),
            ],
            mappings=[
                (1, 0, "NM_002"), (2, 0, "NM_003"), (3, 0, "NM_004"), (4, 0, "NM_005"),
            ],
            genes=[("GENE2", 0.3), ("GENE3", 0.1)],
            input_paths={"0": "/in/db2.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )

        self.run_merge_to(
            [self.db1, self.db2], self.parallel_outpath, parallel=True, workers=2,
        )

        uids = [
            r[0] for r in self.query_path(self.parallel_outpath, "select base__uid from variant")
        ]
        self.assertEqual(len(uids), 5)
        self.assertEqual(
            len(uids), len(set(uids)),
            "every shard's new variants must still get globally-unique uids "
            "after concatenation, even though shards allocate new uids "
            "from overlapping (not private) ranges",
        )


class TestParallelMatchesSerialStructural(ParallelMergeSqliteTestBase):
    """Structural-merge-only (skip_postaggregator=True) equivalence check
    between --parallel and the default serial path, across several
    chromosomes (including a PAR gene) and a shared input file."""

    def test_parallel_output_matches_serial_modulo_uid(self):
        build_db(
            self.db1,
            variants=[
                (1, "chr1", 100, "A", "T", "GENE1", 0.5),
                (2, "chrX", 500, "G", "C", "PARGENE", 0.2),
            ],
            samples=[(1, "s1", "het"), (2, "s2", "het")],
            mappings=[(1, 0, "NM_001A"), (2, 0, "NM_0X")],
            genes=[("GENE1", 0.9), ("PARGENE", 0.5)],
            input_paths={"0": "/in/fileA.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )
        db2 = os.path.join(self.tmpdir, "db2.sqlite")
        build_db(
            db2,
            variants=[
                (1, "chr1", 100, "A", "T", "GENE1", 0.5),  # shared with db1
                (2, "chr2", 200, "C", "G", "GENE2", 0.7),
                (3, "chrY", 600, "T", "A", "PARGENE", 0.4),
            ],
            samples=[(1, "s3", "hom"), (2, "s4", "het"), (3, "s5", "het")],
            mappings=[(1, 0, "NM_001B"), (2, 0, "NM_002"), (3, 0, "NM_0Y")],
            genes=[("GENE1", 0.9), ("GENE2", 0.3), ("PARGENE", 0.5)],
            input_paths={"0": "/in/fileB.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )
        db3 = os.path.join(self.tmpdir, "db3.sqlite")
        build_db(
            db3,
            variants=[(1, "chr3", 300, "A", "G", "GENE3", 0.1)],
            samples=[(1, "s6", "het")],
            mappings=[(1, 0, "NM_003")],
            genes=[("GENE3", 0.6)],
            input_paths={"0": "/in/fileA.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
        )
        paths = [self.db1, db2, db3]

        self.run_merge_to(paths, self.serial_outpath, parallel=False)
        self.run_merge_to(paths, self.parallel_outpath, parallel=True, workers=4)

        self.assertEqual(
            self.variant_keys(self.serial_outpath), self.variant_keys(self.parallel_outpath),
        )
        self.assertEqual(
            self.gene_names(self.serial_outpath), self.gene_names(self.parallel_outpath),
        )
        self.assertEqual(
            self.samples_by_variant_key(self.serial_outpath),
            self.samples_by_variant_key(self.parallel_outpath),
        )
        serial_uids = [
            r[0] for r in self.query_path(self.serial_outpath, "select base__uid from variant")
        ]
        parallel_uids = [
            r[0] for r in self.query_path(self.parallel_outpath, "select base__uid from variant")
        ]
        self.assertEqual(len(serial_uids), len(set(serial_uids)))
        self.assertEqual(len(parallel_uids), len(set(parallel_uids)))


@unittest.skipUnless(
    _POSTAGG_MODULES_AVAILABLE,
    "tagsampler/varmeta/vcfinfo postaggregator modules are not installed locally",
)
class TestParallelMatchesSerialPostagg(ParallelMergeSqliteTestBase):
    """Same comparison as TestParallelMatchesSerialStructural, but with
    real postaggregator recompute (skip_postaggregator=False) - checks
    tagsampler/varmeta columns agree between the serial and parallel
    paths too, not just the structural merge."""

    def test_postagg_recomputed_columns_match_serial(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", "GENE1", 0.5)],
            samples=[(1, "sample1", "het", None, None, None, None, None, None, None)],
            mappings=[(1, 0, "NM_001", None, "line-a")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "csv"},
        )
        db2 = os.path.join(self.tmpdir, "db2.sqlite")
        build_db(
            db2,
            variants=[
                (1, "chr1", 100, "A", "T", "GENE1", 0.5),  # shared with db1
                (2, "chr2", 200, "C", "G", "GENE2", 0.7),
            ],
            samples=[
                (1, "sample2", "hom", None, None, None, None, None, None, None),
                (2, "sample3", "het", None, None, None, None, None, None, None),
            ],
            mappings=[
                (1, 0, "NM_001", None, "line-b"),
                (2, 0, "NM_002", None, "line-c"),
            ],
            genes=[("GENE1", 0.9), ("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "csv"},
        )
        paths = [self.db1, db2]

        self.run_merge_to(paths, self.serial_outpath, parallel=False, skip_postaggregator=False)
        self.run_merge_to(
            paths, self.parallel_outpath, parallel=True, workers=2, skip_postaggregator=False,
        )

        def tagsampler_and_varmeta_by_key(dbpath):
            uid_to_key = {
                r[0]: r[1:]
                for r in self.query_path(
                    dbpath,
                    "select base__uid, base__chrom, base__pos, base__ref_base, base__alt_base "
                    "from variant",
                )
            }
            rows = self.query_path(
                dbpath,
                "select base__uid, tagsampler__numsample, tagsampler__samples, "
                "varmeta__zygosity from variant",
            )
            return {uid_to_key[r[0]]: r[1:] for r in rows}

        self.assertEqual(
            tagsampler_and_varmeta_by_key(self.serial_outpath),
            tagsampler_and_varmeta_by_key(self.parallel_outpath),
        )


@unittest.skipUnless(
    _POSTAGG_MODULES_AVAILABLE,
    "tagsampler/varmeta/vcfinfo postaggregator modules are not installed locally",
)
class TestParallelVcfinfoGlobalMultiSample(ParallelMergeSqliteTestBase):
    """The vcfinfo edge case OC-833's parallel design calls out
    explicitly: each shard here has only ONE sample locally (so each
    shard's own setup() would compute multi_sample=False if left alone),
    but the cohort as a whole has two - vcfinfo's column typing must
    reflect the cohort-wide truth (multi_sample=True), not either shard's
    local subset."""

    def test_shard_local_single_sample_does_not_leak_into_column_typing(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", "GENE1", 0.5)],
            samples=[(1, "sample1", "het", 30, "PASS", 5, 10, 0.5, None, None)],
            mappings=[(1, 0, "NM_001", None, "line-a")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "vcf"},
        )
        db2 = os.path.join(self.tmpdir, "db2.sqlite")
        build_db(
            db2,
            variants=[(1, "chr2", 200, "C", "G", "GENE2", 0.7)],
            samples=[(1, "sample2", "hom", 40, "PASS", 8, 10, 0.8, None, None)],
            mappings=[(1, 0, "NM_002", None, "line-b")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "vcf"},
        )

        self.run_merge_to(
            [self.db1, db2], self.parallel_outpath, parallel=True, workers=2,
            skip_postaggregator=False,
        )

        col_def = json.loads(
            self.query_path(
                self.parallel_outpath,
                'select col_def from variant_header where col_name="vcfinfo__phred"',
            )[0][0]
        )
        self.assertEqual(
            col_def["type"], "string",
            "vcfinfo__phred must keep its default multi-sample column type "
            "(the cohort has 2 samples total), even though each shard's own "
            "local sample table has only 1 - a shard-local single_sample "
            "column-type mutation must not leak into the merged schema",
        )
        self.assertFalse(col_def["filterable"])

        phred_by_chrom = dict(
            self.query_path(
                self.parallel_outpath, "select base__chrom, vcfinfo__phred from variant"
            )
        )
        self.assertEqual(phred_by_chrom["chr1"], "30")
        self.assertEqual(phred_by_chrom["chr2"], "40")


@unittest.skipUnless(
    au.module_exists_local("casecontrol"),
    "casecontrol postaggregator module is not installed locally",
)
class TestParallelCasecontrolRejected(ParallelMergeSqliteTestBase):
    """OC-833 production decision 7: casecontrol is dropped entirely from
    the --parallel path (not run per-shard, and not run serially against
    the final output either, unlike the original prototype) - its
    Fisher's-exact denominator is a whole-cohort scalar, out of scope for
    per-shard parallelization, and there's no requirement to support it
    after a parallel merge at all. mergesqlite_validate_and_prepare()
    hard-fails before any output file is written whenever casecontrol
    would actually do something (a "cohorts" module option given)
    together with --parallel - these tests don't need scipy, since
    casecontrol's own Fisher's-exact code never actually runs."""

    def _build_two_dbs_with_case_and_control(self):
        build_db(
            self.db1,
            variants=[(1, "chr1", 100, "A", "T", "GENE1", 0.5)],
            samples=[(1, "case1", "het", None, None, None, None, None, None, None)],
            mappings=[(1, 0, "NM_001", None, "line-a")],
            genes=[("GENE1", 0.9)],
            input_paths={"0": "/in/db1.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "csv"},
        )
        db2 = os.path.join(self.tmpdir, "db2.sqlite")
        build_db(
            db2,
            variants=[(1, "chr2", 200, "C", "G", "GENE2", 0.7)],
            samples=[(1, "cont1", "hom", None, None, None, None, None, None, None)],
            mappings=[(1, 0, "NM_002", None, "line-b")],
            genes=[("GENE2", 0.3)],
            input_paths={"0": "/in/db2.vcf"},
            variant_cols=VARIANT_COLS_WITH_HUGO,
            sample_cols=SAMPLE_COLS_FULL,
            mapping_cols=MAPPING_COLS_FULL,
            extra_info={"_converter_format": "csv"},
        )
        return [self.db1, db2]

    def test_cohorts_option_with_parallel_hard_fails_no_output(self):
        paths = self._build_two_dbs_with_case_and_control()
        cohorts_path = os.path.join(self.tmpdir, "cohorts.txt")
        with open(cohorts_path, "w") as f:
            f.write("case1 case\ncont1 control\n")

        with self.assertRaises(SystemExit):
            self.run_merge_to(
                paths, self.parallel_outpath, parallel=True, workers=2,
                skip_postaggregator=False,
                module_option=[f"casecontrol.cohorts={cohorts_path}"],
            )
        self.assertFalse(
            os.path.exists(self.parallel_outpath),
            "casecontrol.cohorts + --parallel must be rejected before any "
            "output file is written",
        )

    def test_explicit_p_casecontrol_with_parallel_hard_fails_no_output(self):
        paths = self._build_two_dbs_with_case_and_control()
        cohorts_path = os.path.join(self.tmpdir, "cohorts.txt")
        with open(cohorts_path, "w") as f:
            f.write("case1 case\ncont1 control\n")

        with self.assertRaises(SystemExit):
            self.run_merge_to(
                paths, self.parallel_outpath, parallel=True, workers=2,
                skip_postaggregator=False, postaggregators=["casecontrol"],
                module_option=[f"casecontrol.cohorts={cohorts_path}"],
            )
        self.assertFalse(os.path.exists(self.parallel_outpath))

    def test_default_casecontrol_without_cohorts_still_merges_in_parallel(self):
        # No cohorts conf given at all - casecontrol would no-op even in
        # the default serial merge (see
        # TestPostaggregatorRecomputeDefaultsNonVcf), so a bare
        # --parallel run with defaults must not be rejected just because
        # casecontrol happens to be installed locally.
        paths = self._build_two_dbs_with_case_and_control()
        self.run_merge_to(
            paths, self.parallel_outpath, parallel=True, workers=2,
            skip_postaggregator=False,
        )
        self.assertTrue(os.path.exists(self.parallel_outpath))
        cols = {
            r[0] for r in self.query_path(
                self.parallel_outpath, "select col_name from variant_header"
            )
        }
        self.assertFalse(
            any(c.startswith("casecontrol__") for c in cols),
            "casecontrol must not contribute any columns in --parallel mode",
        )


if __name__ == "__main__":
    unittest.main()
