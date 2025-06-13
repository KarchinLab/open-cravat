from pyliftover import LiftOver

import cravat
from cravat import LiftoverFailure
from cravat import admin_util as au, get_live_mapper, get_live_annotator, constants


def clean_annot_dict (d):
    keys = d.keys()
    for key in keys:
        value = d[key]
        if value == '' or value == {}:
            d[key] = None
        elif type(value) is dict:
            d[key] = clean_annot_dict(value)
    if type(d) is dict:
        all_none = True
        for key in keys:
            if d[key] is not None:
                all_none = False
                break
        if all_none:
            d = None
    return d

class LiveModuleCache:
    _instance = None
    mapper = None
    annotators = {}
    lifters = {}
    wgsreader = cravat.get_wgs_reader(assembly="hg38")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LiveModuleCache, cls).__new__(cls)
        return cls._instance

    def load_lifter(self, assembly):
        print(f'loading {assembly} lifter')
        if assembly not in self.lifters.keys():
            if not constants.liftover_chain_paths[assembly]:
                raise LiftoverFailure(f'Assembly "{assembly}" not supported.')
            self.lifters[assembly] = LiftOver(constants.liftover_chain_paths[assembly])
        print('done loading lifter')

    # TODO: This is borrowed from cravat_convert.MasterCravatConverter
    # this should be refactored into a separate, reusable module
    def liftover(self, coords, assembly):
        chrom = coords.get('chrom')
        pos = coords.get('pos')
        ref = coords.get('ref_base')
        alt = coords.get('alt_base')
        reflen = len(ref)
        altlen = len(alt)
        if chrom == "chrMT":
            newchrom = "chrM"
            newpos = pos
        elif reflen == 1 and altlen == 1:
            res = self.lifters[assembly].convert_coordinate(chrom, pos - 1)
            if res is None or len(res) == 0:
                raise LiftoverFailure("Liftover failure")
            if len(res) > 1:
                raise LiftoverFailure("Liftover failure")
            try:
                el = res[0]
            except:
                raise LiftoverFailure("Liftover failure")
            newchrom = el[0]
            newpos = el[1] + 1
        elif reflen >= 1 and altlen == 0:  # del
            pos1 = pos
            pos2 = pos + reflen - 1
            res1 = self.lifters[assembly].convert_coordinate(chrom, pos1 - 1)
            res2 = self.lifters[assembly].convert_coordinate(chrom, pos2 - 1)
            if res1 is None or res2 is None or len(res1) == 0 or len(res2) == 0:
                raise LiftoverFailure("Liftover failure")
            if len(res1) > 1 or len(res2) > 1:
                raise LiftoverFailure("Liftover failure")
            el1 = res1[0]
            el2 = res2[0]
            newchrom1 = el1[0]
            newpos1 = el1[1] + 1
            newchrom2 = el2[0]
            newpos2 = el2[1] + 1
            newchrom = newchrom1
            newpos = newpos1
            newpos = min(newpos1, newpos2)
        elif reflen == 0 and altlen >= 1:  # ins
            res = self.lifters[assembly].convert_coordinate(chrom, pos - 1)
            if res is None or len(res) == 0:
                raise LiftoverFailure("Liftover failure")
            if len(res) > 1:
                raise LiftoverFailure("Liftover failure")
            el = res[0]
            newchrom = el[0]
            newpos = el[1] + 1
        else:
            pos1 = pos
            pos2 = pos + reflen - 1
            res1 = self.lifters[assembly].convert_coordinate(chrom, pos1 - 1)
            res2 = self.lifters[assembly].convert_coordinate(chrom, pos2 - 1)
            if res1 is None or res2 is None or len(res1) == 0 or len(res2) == 0:
                raise LiftoverFailure("Liftover failure")
            if len(res1) > 1 or len(res2) > 1:
                raise LiftoverFailure("Liftover failure")
            el1 = res1[0]
            el2 = res2[0]
            newchrom1 = el1[0]
            newpos1 = el1[1] + 1
            newchrom2 = el2[0]
            newpos2 = el2[1] + 1
            newchrom = newchrom1
            newpos = min(newpos1, newpos2)
        hg38_ref = self.wgsreader.get_bases(newchrom, newpos)
        if hg38_ref == cravat.util.reverse_complement(ref):
            newref = hg38_ref
            newalt = cravat.util.reverse_complement(alt)
        else:
            newref = ref
            newalt = alt
        return {
            'chrom': newchrom,
            'pos': newpos,
            'ref_base': newref,
            'alt_base': newalt
        }


    def load_live_mapper(self):
        if self.mapper is None:
            print('populating live mapper')
            cravat_conf = au.get_cravat_conf()
            if 'genemapper' in cravat_conf:
                default_mapper = cravat_conf['genemapper']
            else:
                default_mapper = 'hg38'
            self.mapper = get_live_mapper(default_mapper)

    def load_live_annotators (self, annotator_names=[]):
        print('populating live annotators')
        conf = au.get_system_conf()
        if 'live' in conf:
            live_conf = conf['live']
            if 'include' in live_conf:
                include_live_modules = live_conf['include']
            else:
                include_live_modules = []
            if 'exclude' in live_conf:
                exclude_live_modules = live_conf['exclude']
            else:
                exclude_live_modules = []
        else:
            include_live_modules = []
            exclude_live_modules = []

        modules = au.get_local_module_infos(types=['annotator'])
        for module in modules:
            if module.name in self.annotators:
                continue
            if module.name not in annotator_names:
                continue

            if module.name not in self.annotators and module.name not in exclude_live_modules:
                annotator = get_live_annotator(module.name)
                if annotator is None:
                    continue
                self.annotators[module.name] = annotator
        print('done populating live annotators')

    def get_live_annotation (self, input_data, annotators):
        from cravat.constants import mapping_parser_name
        from cravat.constants import all_mappings_col_name
        from cravat.inout import AllMappingsParser
        response = {}
        crx_data = self.mapper.map(input_data)
        crx_data = self.mapper.live_report_substitute(crx_data)
        crx_data[mapping_parser_name] = AllMappingsParser(crx_data[all_mappings_col_name])
        for k, v in self.annotators.items():
            if annotators is not None and k not in annotators:
                continue
            try:
                annot_data = v.annotate(input_data=crx_data)
                annot_data = v.live_report_substitute(annot_data)
                if annot_data == '' or annot_data == {}:
                    annot_data = None
                elif type(annot_data) is dict:
                    annot_data = clean_annot_dict(annot_data)
                response[k] = annot_data
            except Exception as e:
                import traceback
                traceback.print_exc()
                response[k] = None
        del crx_data[mapping_parser_name]
        response['crx'] = crx_data
        return response