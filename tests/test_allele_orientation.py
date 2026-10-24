import unittest

from cravat.allele_orientation import (
    orient_alleles_to_target_ref,
    zygosity_after_liftover,
    NOT_A_VARIANT,
)


class OrientAllelesToTargetRefTest(unittest.TestCase):
    def test_reference_already_matches(self):
        self.assertEqual(orient_alleles_to_target_ref("A", "A", "G"), ("A", "G", False))

    def test_opposite_strand_reverse_complements_both(self):
        # hg19 A>G lifted onto a minus-strand site whose hg38 reference is T
        self.assertEqual(orient_alleles_to_target_ref("T", "A", "G"), ("T", "C", False))

    def test_assembly_disagrees_on_ref_swaps_alleles(self):
        # F5 rs6025: hg19 ref T / alt C, but the hg38 reference at the
        # lifted site is C. The pathogenic hg38 variant is C>T.
        self.assertEqual(orient_alleles_to_target_ref("C", "T", "C"), ("C", "T", True))

    def test_swap_on_opposite_strand(self):
        # hg19 T>C onto a minus-strand site: hg38 reference is revcomp(alt) = G
        self.assertEqual(orient_alleles_to_target_ref("G", "T", "C"), ("G", "A", True))

    def test_reference_matches_neither_allele_is_unchanged(self):
        # target A is neither C, G, nor their reverse complements (G, C)
        self.assertEqual(orient_alleles_to_target_ref("A", "C", "G"), ("C", "G", False))

    def test_chain_strand_resolves_ambiguity_at_at_site(self):
        # ref A / alt T with hg38 ref T: from the bases alone this is read as a
        # strand flip; on a "+" site it can only be a swap
        self.assertEqual(orient_alleles_to_target_ref("T", "A", "T"), ("T", "A", False))
        self.assertEqual(
            orient_alleles_to_target_ref("T", "A", "T", strand="+"), ("T", "A", True)
        )

    def test_minus_strand_site_only_reverse_complements(self):
        self.assertEqual(
            orient_alleles_to_target_ref("A", "T", "C", strand="-"), ("A", "G", False)
        )
        # target equals alt's letter, but a "-" site can never be a plain swap
        self.assertEqual(
            orient_alleles_to_target_ref("C", "T", "C", strand="-"), ("T", "C", False)
        )


class ZygosityAfterLiftoverTest(unittest.TestCase):
    def test_unswapped_calls_are_unchanged(self):
        self.assertEqual(zygosity_after_liftover("het", False), "het")
        self.assertEqual(zygosity_after_liftover("hom", False), "hom")

    def test_het_survives_a_swap(self):
        self.assertEqual(zygosity_after_liftover("het", True), "het")

    def test_hom_alt_becomes_hom_reference_after_a_swap(self):
        self.assertIs(zygosity_after_liftover("hom", True), NOT_A_VARIANT)

    def test_ref_sentinel_is_a_variant_only_after_a_swap(self):
        self.assertEqual(zygosity_after_liftover("ref", True), "hom")
        self.assertIs(zygosity_after_liftover("ref", False), NOT_A_VARIANT)

    def test_unknown_zygosity_is_never_dropped(self):
        # e.g. a VCF row with no GT field has zygosity None
        self.assertIsNone(zygosity_after_liftover(None, False))
        self.assertIsNone(zygosity_after_liftover(None, True))


class ConverterLiftoverTest(unittest.TestCase):
    """Converter.liftover() with a stub chain and a stub hg38 reference."""

    def make_converter(self, hg38_base):
        from types import SimpleNamespace
        from cravat.cravat_convert import MasterCravatConverter

        converter = MasterCravatConverter.__new__(MasterCravatConverter)
        converter.lifter = SimpleNamespace(
            convert_coordinate=lambda chrom, pos: [("chr1", pos + 30762, "+")]
        )
        converter.wgsreader = SimpleNamespace(get_bases=lambda chrom, pos: hg38_base)
        return converter

    def test_rs6025_alleles_are_swapped_to_hg38_orientation(self):
        converter = self.make_converter("C")
        self.assertEqual(
            converter.liftover("chr1", 169519049, "T", "C"),
            ["chr1", 169549811, "C", "T", True],
        )

    def test_matching_reference_is_not_swapped(self):
        converter = self.make_converter("T")
        self.assertEqual(
            converter.liftover("chr1", 169519049, "T", "C"),
            ["chr1", 169549811, "T", "C", False],
        )


if __name__ == "__main__":
    unittest.main()
