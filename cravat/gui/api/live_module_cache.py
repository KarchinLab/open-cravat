from cravat import admin_util as au, get_live_mapper, get_live_annotator

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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LiveModuleCache, cls).__new__(cls)
        return cls._instance

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