"""Re-orient a variant's ref/alt alleles to the reference base of the assembly
it was lifted over to.

Kept free of other cravat imports so it can be unit tested on its own.
"""

_COMPLEMENT = str.maketrans("ACGTacgt", "TGCAtgca")


def _revcomp(bases):
    return bases.translate(_COMPLEMENT)[::-1]


def orient_alleles_to_target_ref(target_ref, ref, alt):
    """Return (new_ref, new_alt, swapped) for a variant lifted onto a site
    whose reference base in the destination assembly is `target_ref`.

    - destination reference is the reverse complement of `ref`: the site is on
      the opposite strand, so both alleles are reverse complemented.
    - destination reference already equals `ref`: nothing to do.
    - destination reference equals `alt`: the two assemblies disagree about
      which allele is the reference (e.g. F5 rs6025, hg19 ref T / hg38 ref C),
      so ref and alt are swapped. `swapped` is True so the caller can reinterpret
      any genotype/zygosity that was expressed relative to the old ref/alt.
    - destination reference equals the reverse complement of `alt`: both of the
      above, on the opposite strand.
    - destination reference matches neither allele: returned unchanged.

    For single-base A/T and C/G sites the first branch (strand flip) wins an
    ambiguity that the bases alone cannot resolve; the liftover chain's strand
    would be needed to decide.
    """
    if target_ref == _revcomp(ref):
        return target_ref, _revcomp(alt), False
    if target_ref == ref:
        return ref, alt, False
    if target_ref == alt:
        return alt, ref, True
    if target_ref == _revcomp(alt):
        return target_ref, _revcomp(ref), True
    return ref, alt, False
