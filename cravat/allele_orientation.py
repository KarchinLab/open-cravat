"""Re-orient a variant's ref/alt alleles to the reference base of the assembly
it was lifted over to.

Kept free of other cravat imports so it can be unit tested on its own.
"""

_COMPLEMENT = str.maketrans("ACGTacgt", "TGCAtgca")


def _revcomp(bases):
    return bases.translate(_COMPLEMENT)[::-1]


def orient_alleles_to_target_ref(target_ref, ref, alt, strand=None):
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

    `strand` is the liftover chain's strand for the site ("+" or "-"), when
    known. For single-base A/T and C/G sites the bases alone cannot tell a
    strand flip from a swap, so without it the strand flip wins; with it, only
    the branches consistent with the chain's strand are considered.
    """
    same_strand = strand != "-"
    opposite_strand = strand != "+"
    if opposite_strand and target_ref == _revcomp(ref):
        return target_ref, _revcomp(alt), False
    if same_strand and target_ref == ref:
        return ref, alt, False
    if same_strand and target_ref == alt:
        return alt, ref, True
    if opposite_strand and target_ref == _revcomp(alt):
        return target_ref, _revcomp(ref), True
    return ref, alt, False


NOT_A_VARIANT = object()


def zygosity_after_liftover(zygosity, swapped):
    """Reinterpret a converter-supplied zygosity once ref/alt may have swapped.

    Returns the zygosity to keep (which may itself be None), or NOT_A_VARIANT if the
    call is homozygous for the destination assembly's reference. Converters use "hom"/"het" (relative to the
    alleles they emitted) and "ref" for a call homozygous for the input
    assembly's reference allele, emitted with the other assembly's reference as
    the alt so it survives a swap.
    """
    z = str(zygosity or "").lower()
    if z.startswith("hom"):
        return NOT_A_VARIANT if swapped else zygosity
    if z == "ref":
        return "hom" if swapped else NOT_A_VARIANT
    return zygosity


def alt_for_hom_ref_mismatch(ref, target_base, strand):
    """For a call homozygous for the input assembly's reference allele `ref`,
    return the alt allele (in the input assembly's orientation) to emit so that
    the call survives liftover, or None if the destination assembly agrees with
    `ref` at this site and there is nothing to report.

    `target_base` is the destination assembly's plus-strand base at the lifted
    site and `strand` is the liftover chain's strand for it.
    """
    base = target_base.upper()
    if strand == "-":
        base = _revcomp(base)
    if len(base) == 1 and base in "ACGT" and base != ref.upper():
        return base
    return None
