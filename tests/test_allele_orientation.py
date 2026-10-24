import unittest

from cravat.allele_orientation import orient_alleles_to_target_ref


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
