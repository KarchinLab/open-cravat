from cravat.config_loader import ConfigLoader
from cravat.allele_orientation import alt_for_hom_ref_mismatch


class BaseConverter(object):
    IGNORE = "converter_ignore"

    def __init__(self):
        self.format_name = None
        self.output_dir = None
        self.run_name = None
        self.input_assembly = None
        self.module_name = self.__class__.__module__
        config_loader = ConfigLoader()
        self.conf = config_loader.get_module_conf(self.module_name)

    def check_format(self, *args, **kwargs):
        err_msg = (
            "Converter for %s format has no method check_format" % self.format_name
        )
        raise NotImplementedError(err_msg)

    def setup(self, *args, **kwargs):
        err_msg = "Converter for %s format has no method setup" % self.format_name
        raise NotImplementedError(err_msg)

    def convert_line(self, *args, **kwargs):
        err_msg = (
            "Converter for %s format has no method convert_line" % self.format_name
        )
        raise NotImplementedError(err_msg)

    def convert_file(self, file, *args, exc_handler=None, **kwargs):
        ln = 0
        for line in file:
            ln += 1
            try:
                yield ln, line, self.convert_line(line)
            except Exception as e:
                if exc_handler:
                    exc_handler(ln, line, e)
                    continue
                else:
                    raise e

    def addl_operation_for_unique_variant(self, wdict, wdict_no):
        pass

    def hom_ref_mismatch_row(self, chrom, pos, ref, tags, sample_id=""):
        """For microarray-style converters that only emit alleles differing from
        the input assembly's reference. A call homozygous for that reference is
        normally skipped, but where the liftover target assembly has a different
        reference base (e.g. F5 rs6025, hg19 T / hg38 C) it is homozygous for a
        variant. Returns a row to emit for it, with zygosity "ref" (see
        allele_orientation.zygosity_after_liftover), or None if there is nothing
        to emit. Rows for single-base sites only; never raises.
        """
        from cravat import constants, get_wgs_reader
        from pyliftover import LiftOver

        chain_path = constants.liftover_chain_paths.get(self.input_assembly)
        if chain_path is None:
            return None
        cache = self.__dict__.setdefault("_hom_ref_mismatch_cache", {})
        if "lifter" not in cache:
            cache["lifter"] = LiftOver(chain_path)
            cache["target"] = get_wgs_reader(assembly="hg38")
        try:
            res = cache["lifter"].convert_coordinate(chrom, pos - 1)
            if not res or len(res) != 1:
                return None
            newchrom, newpos, strand = res[0][0], res[0][1] + 1, res[0][2]
            target_base = cache["target"].slice(newchrom, newpos)
        except (KeyError, IndexError, ValueError, AttributeError, TypeError):
            return None
        alt = alt_for_hom_ref_mismatch(ref, target_base, strand)
        if alt is None:
            return None
        return {
            "tags": tags,
            "chrom": chrom,
            "pos": pos,
            "ref_base": ref,
            "alt_base": alt,
            "sample_id": sample_id,
            "zygosity": "ref",
        }
