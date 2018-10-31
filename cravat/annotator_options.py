import os
import yaml
from .exceptions import ConfigurationError
from .constants import crv_def, crx_def, crg_def

class AnnotatorOptions(object):
    valid_levels = ['variant','gene']
    valid_input_formats = ['crv','crx','crg']
    id_col_defs = {'variant':crv_def[0],
                   'gene':crg_def[0]}
    default_input_columns = {'crv':[x['name'] for x in crv_def],
                             'crx':[x['name'] for x in crx_def],
                             'crg':[x['name'] for x in crg_def]}
    required_conf_keys = ['level', 'output_columns']

    def __init__(self, annotator_dir):
        self.secondary_inputs = {}
        self.secondary_paths = {}
        self.annotator_dir = os.path.abspath(annotator_dir)
        self.annotator_name = os.path.basename(self.annotator_dir)
        self.annotator_conf_path = os.path.join(self.annotator_dir, 
                                                self.annotator_name + '.yml')
        
    # Parse the default conf files and the optional job conf
    def parse_all_conf_files(self):
        self.parse_conf_file(self.annotator_conf_path)
        #TODO parse cravat.conf if available
        if self.job_conf_path:
            self.parse_conf_file(self.job_conf_path)

    # Parse just the annotator conf file
    def parse_annotator_conf(self):
        self.parse_conf_file(self.annotator_conf_path)
    
    # Parse a generic conf file.
    # Apply special parsing rules to certain conf keys
    def parse_conf_file(self, conf_path):
        d = yaml.load(open(conf_path))
        for k in self.required_conf_keys:
            if k not in d:
                err_msg = 'Required key "%s" not found in configuration' %k
                raise ConfigurationError(err_msg)
        if d['level'] in self.valid_levels:
                d['output_columns'] = [self.id_col_defs[d['level']]] + d['output_columns']
        else:
            err_msg = '%s is not a valid level. Valid levels are %s' \
                        %(d['level'], ', '.join(self.valid_levels))
            raise ConfigurationError(err_msg)
        if 'input_format' in d:
            if d['input_format'] not in self.valid_input_formats:
                err_msg = 'Invalid input_format %s, select from %s' \
                    %(d['input_format'], ', '.join(self.valid_input_formats))
        else:
            if d['level'] == 'variant':
                d['input_format'] = 'crv'
            elif d['level'] == 'gene':
                d['input_format'] = 'crg'
        if 'input_columns' in d:
            id_col_name = self.id_col_defs[d['level']]['name']
            if id_col_name not in d['input_columns']:
                d['input_columns'].append(id_col_name)
        else:
            d['input_columns'] = self.default_input_columns[d['input_format']]
        for k, v in d.items():
            self.__dict__[k] = v
    def __getitem__(self, key):
        return self.__dict__[key]
    def __setitem__(self, key, value):
        self.__dict__[key] = value