import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace

from cravat.cravat_util import mergesqlite

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
    c.executemany(
        "insert into info values (?, ?)",
        [
            ("_input_paths", input_paths_str),
            ("Input file name", ";".join(input_paths.values())),
            ("Number of unique input variants", str(len(variants))),
            ("Result created at", "2026-01-01 00:00:00"),
            ("Result modified at", "2026-01-01 00:00:00"),
        ],
    )

    conn.commit()
    conn.close()


class MergeSqliteTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.db1 = os.path.join(self.tmpdir, "db1.sqlite")
        self.db2 = os.path.join(self.tmpdir, "db2.sqlite")
        self.outpath = os.path.join(self.tmpdir, "merged.sqlite")

    def run_merge(self, paths):
        args = SimpleNamespace(path=paths, outpath=self.outpath)
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


if __name__ == "__main__":
    unittest.main()
