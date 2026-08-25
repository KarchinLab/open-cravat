# Production mergesqlite parallel merge

Supersedes PLAN.md's open questions, following prototype validation on the
`cv-OC-833-mergesqlite-parallel` branch (uncommitted `cravat_util.py` changes
in this worktree).

## What the prototype validated

- Correctness: content-identical to serial (modulo uid renumbering) on two
  independent real datasets - pilot_1000 (297k variants) and pilot_1000_wxs
  (347k variants).
- Speedup: 1.94x-2.30x on a 4-core box at `--workers 4`.
- Concatenation phase (the one serial step) measured at ~15% of total
  wall-clock (3.7s of 24.5s, 4 shards, pilot_1000 dataset). This bounds the
  achievable speedup at any shard count via Amdahl's law: ~1/0.15 ≈ 6.7x
  ceiling regardless of worker count, at today's shard granularity.

## Decisions for production

1. **Uid allocation: local-then-renumber, not fixed blocks.** Each shard
   assigns local 0-based uids independently; the concatenation phase (which
   already rewrites every row via `INSERT...SELECT`) renumbers uids globally
   as it copies. Removes the prototype's hard-fail-on-overflow footgun
   entirely instead of just making the block size generous.

2. **Gene table: one global pass, not per-shard replication + dedup.** The
   gene table isn't chromosome-partitionable (real data has gene rows whose
   hugo symbol is never any variant's *primary* `base__hugo` call - see the
   `TBC1D3B`/alt-contig case found during validation). Don't copy the whole
   gene table into every shard. Merge it once, directly from the original
   input dbs, alongside the concatenation phase - same dedupe-by-first-hugo
   logic the serial merge always used, run once instead of N times.

3. **Single node only. No cluster/multi-node support.** Keep the
   `ProcessPoolExecutor`-based local multiprocessing model. Do not split into
   plan/shard/concat subcommands or add Slurm-array-job orchestration - a
   distributed-systems dependency isn't wanted in OC. Parallelism is capped at
   local core count; accepted tradeoff.

4. **Partition by whole chromosome only. No sub-chromosome/position-range
   partitioning.** Considered, rejected:
   - Chromosome-only bucketing needs only `base__chrom` equality filtering
     (`WHERE base__chrom IN (...)`) and one `GROUP BY base__chrom` count query
     for load-balancing.
   - Sub-chromosome partitioning would need per-chromosome position quantile
     boundaries (materially more expensive than a row-count group-by),
     per-shard OR'd range predicates instead of simple `IN (...)` set
     membership, and new boundary-correctness handling (multi-allelic sites at
     one position must stay in one shard; half-open-interval edge bugs).
     Roughly doubles the code/test surface of the partitioning/query layer
     specifically - shard-merge internals, gene handling, postagg recompute,
     and concatenation are unaffected either way.
   - It wouldn't pay for itself: concatenation is a fixed, shard-count-
     independent cost (~15% measured) that sets the ceiling long before more
     shards would matter, and the real ceiling on *useful* shard count is the
     human chromosome count (~25 buckets, chrX+chrY paired) - only a box with
     far more cores than that would benefit, and only up to the same Amdahl
     ceiling. Not worth it for today's target hardware.

5. **vcfinfo global `multi_sample`: fix upstream, not via monkeypatch.** The
   prototype forces `multi_sample` by wrapping the instantiated vcfinfo
   object's `setup()` - coupled to vcfinfo's private internals. Production:
   add a proper override hook to vcfinfo itself (accept `multi_sample` via its
   existing `--confs` mechanism) as a change to the sibling modules repo
   (open-cravat-modules-karchinlab), and call it plainly from cravat_util.py's
   shard workers. Removes the monkeypatch entirely.

6. **Concatenation stays serial. No tree/pairwise-merge.** The measured ~15%
   is dominated by unavoidable bulk-copy work, not coordination overhead - a
   tree-merge would add its own worker pool, intermediate partial files, and
   new failure modes to shrink an already-small, already-simple slice of the
   total. Skip it; revisit only if profiling on a future dataset shows
   concatenation growing disproportionately.

7. **Drop `casecontrol` support entirely.** No requirement to recompute
   casecontrol after a parallel merge. Removes: the "exclude casecontrol from
   shard postagg names" branch, the separate final serial casecontrol
   invocation, and the whole whole-cohort-vs-shardable postaggregator
   classification concern. `tagsampler`, `varmeta`, and `vcfinfo` (with the
   fix in point 5) become uniformly per-shard, no exceptions.

## Unchanged from the prototype

- `--parallel` / `--workers N` flags on the existing `mergesqlite` subcommand.
- Chromosome bucketing via greedy LPT bin-packing. chrX+chrY are no longer
  forced into the same bucket: that existed only to keep a pseudoautosomal-
  region gene co-located with its shard's own gene-dedup pass, which point 2
  above eliminates entirely (gene is merged once, globally, independent of
  bucketing) - so the forcing has no remaining correctness purpose and is
  dropped as dead complexity.
- Pre-merge validation shared between serial and parallel paths
  (`mergesqlite_validate_and_prepare`).

## Explicitly out of scope

- Multi-node/cluster execution (point 3).
- Sub-chromosome partitioning (point 4).
- Parallelizing the concatenation phase (point 6).
- `casecontrol` support in the parallel path (point 7).
