# Contig-parallel mergesqlite

## Context

A 1,000-sample scale test of `oc util mergesqlite` (50 batches of 20 samples,
comparing `cv/OC-832-mergesqlite-bug` against `cvaske/cv-OC-833-postagg-recompute`)
found no memory scaling concern (peak RSS ~0.21GB merging 50 dbs / 1,000 samples /
~297k variants), but did find a real wall-clock cost: merging + recomputing
postaggregators over the full cohort took 69.4s, all of it single-threaded
(`n_procs` stayed at 1 for the whole call - no forking, no `--mp`).

That 69.4s matters most in a scenario where the 50 batch `oc run`s are parallelized
across a Slurm cluster (collapsing the batch phase from ~485s sequential down to
~19s, the slowest single batch): once batching is parallel, the serial merge becomes
the dominant tail cost and the thing worth cutting next.

This documents whether `mergesqlite`'s two phases (structural merge, postaggregator
recompute) could be parallelized by genomic contig, based on reading the actual
merge loop and the four default postaggregator modules' code - not just a
suggestion, a checked design.

## Phase 1: structural merge

**Current state** (`mergesqlite()` in `cravat/cravat_util.py`): a single sequential
loop, `for dbpath, label in zip(dbpaths[1:], labels[1:])`, one input db at a time.
Every iteration reads and mutates shared state:
- `new_uid` - a monotonic counter assigning uids to new variants
- `vid_to_uid` - dedup dict, `(chrom, pos, ref, alt) -> uid`, used to detect a
  variant already present from an earlier input db
- `genes` - set of hugo symbols already copied into the output
- `new_fileno` / `rev_input_paths` - renumbers each db's `_input_paths` entries

None of this is sharded by contig today; it's sharded by input db, and inherently
serial because db N's processing depends on having already merged dbs 1..N-1 into
the same dicts.

**Why contig is a valid shard boundary**: `chrom` is part of the dedup key
(`variant_id(chrom, pos, ref, alt)`), so a chr7 variant can never collide with a
chr3 one. Genes are effectively single-contig too (with one known exception below).

**Proposed shape**:
1. Partition each input db's variant/sample/mapping rows by `base__chrom` (already
   an indexed column in practice - `oc run`'s own indexing step indexes
   `variant.base__chrom`).
2. Each contig-worker gets a private uid range (or an atomically-allocated block)
   and builds its own local `vid_to_uid`/`genes`, scoped to just that contig, across
   all 50 input dbs - the same merge algorithm as today, just contig-restricted.
3. Each worker writes to its **own** sqlite file, not a shared one - SQLite has one
   writer per file, so concurrent workers can't target one output db directly
   regardless of shard boundary.
4. A final serial pass concatenates shards into the merged output via
   `ATTACH DATABASE` + `INSERT INTO ... SELECT` - bulk SQL, not the current
   row-by-row Python loop, so this tail is cheap even though it's serial.

**Known caveats**:
- Pseudoautosomal-region genes (a handful of genes annotated on both X and Y)
  aren't strictly single-contig - needs one small gene-table dedup pass after
  concatenation (the table is tiny, this is not a cost concern).
- Contigs aren't equal-sized (chr1 vs chrY) - naive one-worker-per-chromosome would
  load-balance badly. Bucket contigs into balanced work units instead, or split the
  largest chromosomes further (e.g. by arm or position range).
- The pre-merge consistency checks (`mergesqlite_check_info`: column/annotator-
  version/sample-id-collision checks) already read each db in full and are cheap -
  stay serial, unaffected by this change.

## Phase 2: postaggregator recompute

Checked all four default postaggregators
(`postaggregators/{tagsampler,varmeta,vcfinfo,casecontrol}`) against the base
class's row loop (`base_postaggregator.py`: a cursor-streamed, one-row-at-a-time
`select * from <level>` with per-row `annotate()` + `UPDATE`).

| Module | Per-row scope | Global dependency | Chromosome-safe to shard? |
|---|---|---|---|
| `tagsampler` | queries `sample`/`mapping` filtered to that row's own `uid` | none | yes, zero merge work |
| `varmeta` | same, `uid`-scoped only | none | yes, zero merge work |
| `vcfinfo` | `uid`-scoped only | one boolean, `multi_sample = count(distinct sample_id) > 1`, computed once in `setup()`, gates both value formatting and the declared column type/filterable schema | yes, but `multi_sample` must be computed once globally and forced into every shard's `setup()` - a shard with too few chrom-local samples could otherwise compute it differently than other shards, producing inconsistent schema across the merged output |
| `casecontrol` | `uid`-scoped in `annotate()` | `setup()` computes `len(case_samples)`/`len(cont_samples)` from the **entire** `sample` table; that count is the direct denominator in every row's Fisher's-exact p-value | **not naively** - a chromosome shard would drop samples with no calls on that contig from the denominator, silently corrupting every p-value in the shard, not just the affected samples' rows |

Both `vcfinfo` and `casecontrol` also have `category`-typed output columns
(`filter`/`zygosity`; `multiallelic`) whose distinct-value lists get unioned into
`variant_header` by the base class's `fill_categories()` pass, which runs once
after all rows are annotated - stays a cheap, serial, header-only step regardless
of sharding.

**Concrete data point**: in the 69.4s "full recompute" merge measured in the scale
test, only `tagsampler` and `vcfinfo` actually ran (`casecontrol` no-op'd - no
`casecontrol.cohorts` module option was given; `varmeta` no-op'd - its `check()` is
vcf-format's opposite of `vcfinfo`'s, and the test data is vcf-converted). So the
entire measured 39.2s postagg overhead came from two modules that parallelize with
*zero* merge complexity. `casecontrol`'s harder case only bites when a real cohort
comparison run is in play.

**Proposed shape for `casecontrol`**: precompute `case_samples`/`cont_samples`
(really just two integers) once, globally, before fanning out to shards, and inject
them into every shard's `setup()` instead of letting each shard derive them
independently. This is a small, well-understood "compute one global scalar first,
then fan out" pattern - not a structural rewrite of the module.

## Expected impact

Not yet measured, but directionally: the 69.4s recompute-merge cost splits into a
structural-merge portion (~30s, comparing `merged_oc833_skip` against
`merged_oc832`) and a postagg portion (~39s, both of which parallelize cleanly per
the table above). Contig-sharding both halves should bring the serial merge tail
down from ~70s to roughly the cost of the slowest single contig shard plus a cheap
concatenation pass - likely single-digit-to-low-teens of seconds at this sample
count. That would meaningfully change the batch+merge-on-Slurm comparison from the
scale test (currently ~88.6s optimistic-parallel vs. 134.3s for one monolithic
1,000-sample run): shrinking the merge tail is what would turn that into a clear
win instead of a close call.

## Open questions / follow-up work before implementing

- Exact sharding granularity: literal per-chromosome, or balanced buckets grouping
  small chromosomes together and splitting chr1-3 further?
- Uid allocation scheme across shards: fixed wide ranges per contig-bucket
  (simplest, wastes some uid space) vs. an atomic shared counter (no waste, adds
  coordination).
- Where the shard-then-concatenate output files live during the run (temp dir
  lifecycle, cleanup on failure).
- Whether to build this as a new `mergesqlite` mode/flag, or a separate tool that
  wraps `mergesqlite`'s existing per-contig-subset logic.
- Re-run the scale test's phase 2/3 methodology (same 50 batch dbs, same
  monitor_run.py harness) against a prototype to confirm the actual speedup before
  committing to the design.
