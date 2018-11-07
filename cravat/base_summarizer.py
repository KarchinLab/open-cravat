import logging, os, time, traceback, argparse
from .exceptions import ConfigurationError
from .inout import CravatReader
from .inout import CravatWriter
from .inout import AllMappingsParser
from cravat.config_loader import ConfigLoader
import sys
from .constants import crv_def
from .constants import crx_def
from .constants import crg_def
from .constants import all_mappings_col_name
from .constants import mapping_parser_name
from .exceptions import InvalidData

import sqlite3

class BaseAnnotator(object):
    
    valid_levels = ['variant','gene']
    valid_input_formats = ['crv','crx','crg']
    id_col_defs = {'variant':crv_def[0],
                   'gene':crg_def[0]}
    default_input_columns = {'crv':[x['name'] for x in crv_def],
                             'crx':[x['name'] for x in crx_def],
                             'crg':[x['name'] for x in crg_def]}
    required_conf_keys = ['level', 'output_columns']
        
    def __init__(self, cmd_args):
        try:
            self.logger = None
            main_fpath = os.path.abspath(sys.modules[self.__module__].__file__)
            main_basename = os.path.basename(main_fpath)
            if '.' in main_basename:
                self.annotator_name = '.'.join(main_basename.split('.')[:-1])
            else:
                self.annotator_name = main_basename
            self.annotator_dir = os.path.dirname(main_fpath)
            self.data_dir = os.path.join(self.annotator_dir, 'data')
            
            # Load command line opts
            self.primary_input_path = None
            self.secondary_paths = None
            self.output_dir = None
            self.output_basename = None
            self.plain_output = None
            self.job_conf_path = None
            self.parse_cmd_args(cmd_args)
            # Make output dir if it doesn't exist
            if not(os.path.exists(self.output_dir)):
                os.makedirs(self.output_dir)
            
            self._setup_logger()
            config_loader = ConfigLoader(self.job_conf_path)
            self.conf = config_loader.get_module_conf(self.annotator_name)
            self._verify_conf()
            self._id_col_name = self.conf['output_columns'][0]['name']
            if 'logging_level' in self.conf:
                self.logger.setLevel(self.conf['logging_level'].upper())
            if 'title' in self.conf:
                self.annotator_display_name = self.conf['title']
            else:
                self.annotator_display_name = os.path.basename(self.annotator_dir).upper()
            self.logger.info('Initialized %s' %self.annotator_name)
            
            self.dbconn = None
            self.cursor = None
        except Exception as e:
            self._log_exception(e)
        
    def _log_exception(self, e, halt=True):
        if self.logger:
            self.logger.exception(e)
        if halt:
            sys.exit(traceback.format_exc())
        else:
            traceback.print_exc()
    
    def _verify_conf(self):
        try:
            for k in self.required_conf_keys:
                if k not in self.conf:
                    err_msg = 'Required key "%s" not found in configuration' %k
                    raise ConfigurationError(err_msg)
            if self.conf['level'] in self.valid_levels:
                    self.conf['output_columns'] = [self.id_col_defs[self.conf['level']]] + self.conf['output_columns']
            else:
                err_msg = '%s is not a valid level. Valid levels are %s' \
                            %(self.conf['level'], ', '.join(self.valid_levels))
                raise ConfigurationError(err_msg)
            if 'input_format' in self.conf:
                if self.conf['input_format'] not in self.valid_input_formats:
                    err_msg = 'Invalid input_format %s, select from %s' \
                        %(self.conf['input_format'], ', '.join(self.valid_input_formats))
            else:
                if self.conf['level'] == 'variant':
                    self.conf['input_format'] = 'crv'
                elif self.conf['level'] == 'gene':
                    self.conf['input_format'] = 'crg'
            if 'input_columns' in self.conf:
                id_col_name = self.id_col_defs[self.conf['level']]['name']
                if id_col_name not in self.conf['input_columns']:
                    self.conf['input_columns'].append(id_col_name)
            else:
                self.conf['input_columns'] = self.default_input_columns[self.conf['input_format']]
        except Exception as e:
            self._log_exception(e)
    
    def _define_cmd_parser(self):
        try:
            parser = argparse.ArgumentParser()
            parser.add_argument('input_file',
                                help='Input file to be annotated.')
            parser.add_argument('-s',
                                action='append',
                                dest='secondary_inputs',
                                help='Secondary inputs. '\
                                     +'Format as <module_name>:<path>')
            parser.add_argument('-n',
                                dest='name',
                                help='Name of job. Default is input file name.')
            parser.add_argument('-d',
                                dest='output_dir',
                                help='Output directory. '\
                                     +'Default is input file directory.')
            parser.add_argument('-c',
                                dest='conf',
                                help='Path to optional run conf file.')
            parser.add_argument('-p', '--plainoutput',
                                action='store_true',
                                dest='plainoutput',
                                help='Skip column definition writing')
            self.cmd_arg_parser = parser
        except Exception as e:
            self._log_exception(e)
    
    # Parse the command line arguments
    def parse_cmd_args(self, cmd_args):
        try:
            self._define_cmd_parser()
            parsed_args = self.cmd_arg_parser.parse_args(cmd_args[1:])
                
            self.primary_input_path = os.path.abspath(parsed_args.input_file)
            
            self.secondary_paths = {}
            if parsed_args.secondary_inputs:
                for secondary_def in parsed_args.secondary_inputs:
                    sec_name, sec_path = secondary_def.split('@')
                    self.secondary_paths[sec_name] = os.path.abspath(sec_path)
            
            self.output_dir = os.path.dirname(self.primary_input_path)
            if parsed_args.output_dir:
                self.output_dir = parsed_args.output_dir
    
            self.plain_output = parsed_args.plainoutput
            
            self.output_basename = os.path.basename(self.primary_input_path)
            if parsed_args.name:
                self.output_basename = parsed_args.name
            
            if parsed_args.conf:
                self.job_conf_path = parsed_args.conf
        except Exception as e:
            self._log_exception(e)
    
    
    # Runs the annotator.
    def run(self):
        try:
            start_time = time.time()
            self.logger.info('Running %s' %self.annotator_name)
            self.base_setup()
            for lnum, input_data, secondary_data in self._get_input():
                try:
                    if secondary_data == {}:
                        output_dict = self.annotate(input_data)
                    else:
                        output_dict = self.annotate(input_data, secondary_data)
                    # This enables summarizing without writing for now.
                    if output_dict == None:
                        continue
                    # Preserves the first column
                    output_dict[self._id_col_name] = input_data[self._id_col_name]
                    self.output_writer.write_data(output_dict)
                except Exception as e:
                    self._log_runtime_exception(lnum, input_data, e)
            
            # This does summarizing.
            self.postprocess()
            
            self.base_cleanup()
            run_time = time.time() - start_time
            self.logger.info('Completed %s in %s seconds' %(self.annotator_name, 
                                                            round(run_time,3)))
        except Exception as e:
            self._log_exception(e)
    
    def postprocess (self):
        pass
    
    def get_gene_summary_data (self, cf):
        cols = [self.annotator_name + '__' + coldef['name'] \
                for coldef in self.conf['output_columns']]
        cols[0] = 'base__hugo'
        gene_collection = {}
        for d in cf.get_variant_iterator_filtered_uids_cols(cols):
            hugo = d['hugo']
            if hugo == None:
                continue
            if hugo not in gene_collection:
                gene_collection[hugo] = {}
                for col in cols[1:]:
                    gene_collection[hugo][col.split('__')[1]] = []
            self.build_gene_collection(hugo, d, gene_collection)
        data = {}
        for hugo in gene_collection:
            out = self.summarize_by_gene(hugo, gene_collection)
            if out == None:
                continue
            row = []
            for col in cols[1:]:
                if col in out:
                    val = out[col]
                else:
                    val = None
                row.append(val) 
            data[hugo] = out
        return data

    def _log_runtime_exception (self, lnum, input_data, e):
        try:
            error_classname = e.__class__.__name__
            err_line = '\t'.join([input_data[self._id_col_name], error_classname, str(e)])
            self.invalid_file.write(err_line + '\n')
            if not(isinstance(e,InvalidData)):
                self._log_exception(e, halt=False)
        except Exception as e:
            self._log_exception(e, halt=False)

    # Setup function for the base_annotator, different from self.setup() 
    # which is intended to be for the derived annotator.
    def base_setup(self):
        try:
            self._setup_primary_input()
            self._setup_secondary_inputs()
            self._setup_outputs()
            self._open_db_connection()
            self.setup()
        except Exception as e:
            self._log_exception(e)
    
    def _setup_primary_input(self):
        try:
            self.primary_input_reader = CravatReader(self.primary_input_path)
            requested_input_columns = self.conf['input_columns']
            defined_columns = self.primary_input_reader.get_column_names()
            missing_columns = set(requested_input_columns) - set(defined_columns)
            if missing_columns:
                if len(defined_columns) > 0:
                    err_msg = 'Columns not defined in input: %s' \
                        %', '.join(missing_columns)
                    raise ConfigurationError(err_msg)
                else:
                    default_columns = self.default_input_columns[self.conf['input_format']]
                    for col_name in requested_input_columns:
                        try:
                            col_index = default_columns.index(col_name)
                        except ValueError:
                            err_msg = 'Column %s not defined for %s format input' \
                                %(col_name, self.conf['input_format'])
                            raise ConfigurationError(err_msg)
                        if col_name == 'pos':
                            data_type = 'int'
                        else:
                            data_type = 'string'
                        self.primary_input_reader.override_column(col_index,
                                                                  col_name,
                                                                  data_type=data_type)
        except Exception as e:
            self._log_exception(e)
    
    def _setup_secondary_inputs(self):
        try:
            self.secondary_readers = {}
            try:
                num_expected = len(self.conf['secondary_inputs'])
            except KeyError:
                num_expected = 0
            num_provided = len(self.secondary_paths)
            if num_expected > num_provided:
                raise Exception('Too few secondary inputs. %d expected, ' +\
                    '%d provided'%(num_expected, num_provided))
            elif num_expected < num_provided:
                raise Exception('Too many secondary inputs. %d expected, %d provided'\
                        %(num_expected, num_provided))
            for sec_name, sec_input_path in self.secondary_paths.items():
                key_col = self.conf['secondary_inputs'][sec_name]\
                                                       ['match_columns']\
                                                       ['secondary']
                use_columns = self.conf['secondary_inputs'][sec_name]['use_columns']
                fetcher = SecondaryInputFetcher(sec_input_path,
                                                key_col,
                                                fetch_cols=use_columns)
                self.secondary_readers[sec_name] = fetcher
        except Exception as e:
            self._log_exception(e)
    
    # Open the output files (.var, .gen, .ncd) that are needed
    def _setup_outputs(self):
        try:
            level = self.conf['level']
            if level == 'variant':
                output_suffix = 'var'
            elif level == 'gene':
                output_suffix = 'gen'
            elif level == 'summary':
                output_suffix = 'sum'
            else:
                output_suffix = 'out'
                
            if not(os.path.exists(self.output_dir)):
                os.makedirs(self.output_dir)
                
            self.output_path = os.path.join(
                self.output_dir, 
                '.'.join([self.output_basename, 
                self.annotator_name,
                output_suffix]))
            self.invalid_path = os.path.join(
                self.output_dir, 
                '.'.join([self.output_basename, 
                self.annotator_name,
                'err']))
            if self.plain_output:
                self.output_writer = CravatWriter(self.output_path, 
                                                  include_definition = False,
                                                  include_titles = True,
                                                  titles_prefix = '')
            else:
                self.output_writer = CravatWriter(self.output_path)
                self.output_writer.write_meta_line('name',
                                                   self.annotator_name)
                self.output_writer.write_meta_line('displayname',
                                                   self.annotator_display_name)
#                 self.output_writer.write_names(self.annotator_name,
#                                                self.annotator_display_name)
            skip_aggregation = []
            for col_index, col_def in enumerate(self.conf['output_columns']):
                self.output_writer.add_column(col_index,
                                              col_def['title'],
                                              col_def['name'],
                                              col_def['type'])
                if not(col_def.get('aggregate', True)):
                    skip_aggregation.append(col_def['name'])
            if not(self.plain_output):
                self.output_writer.write_definition()
                self.output_writer.write_meta_line('no_aggregate',
                                                   ','.join(skip_aggregation))
            self.invalid_file = open(self.invalid_path, 'w')
        except Exception as e:
                self._log_exception(e)
    
    def _open_db_connection (self):
        db_dirs = [self.data_dir,
                   os.path.join('/ext', 'resource', self.annotator_name)]
        db_path = None
        for db_dir in db_dirs:
            db_path = os.path.join(db_dir, self.annotator_name + '.sqlite')
            if os.path.exists(db_path):
                self.dbconn = sqlite3.connect(db_path)
                self.cursor = self.dbconn.cursor()
    
    def close_db_connection (self):
        self.cursor.close()
        self.dbconn.close()
    
    def get_uid_col (self):
        return self.conf['output_columns'][0]['name']
        
    # Placeholder, intended to be overridded in derived class
    def setup(self):
        pass
    
    def base_cleanup(self):
        try:
            self.output_writer.close()
            self.invalid_file.close()
            if self.dbconn != None:
                self.close_db_connection()
            self.cleanup()
        except Exception as e:
            self._log_exception(e)
    
    # Placeholder, intended to be overridden in derived class
    def cleanup(self):
        pass
            
    # Setup the logging utility
    def _setup_logger(self):
        try:
            self.logger = logging.getLogger(self.annotator_name)
            self.logger.propagate = False
            self.logger.setLevel('INFO')
            log_path = os.path.join(self.output_dir, 
                                    '.'.join([self.output_basename, 
                                             self.annotator_name, 
                                             'log']))
            handler = logging.FileHandler(log_path, mode='w')
            formatter = logging.Formatter(
                '%(name)20s%(lineno)6d   %(asctime)20s   %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        except Exception as e:
            self._log_exception(e)
        
    # Gets the input dict from both the input file, and 
    # any depended annotators depended annotator feature not complete.
    def _get_input(self):
        for lnum, reader_data in self.primary_input_reader.loop_data('dict'):
            try:
                input_data = {}
                for col_name in self.conf['input_columns']:
                    input_data[col_name] = reader_data[col_name]
                if all_mappings_col_name in input_data:
                    input_data[mapping_parser_name] = \
                        AllMappingsParser(input_data[all_mappings_col_name])
                secondary_data = {}
                for annotator_name, fetcher in self.secondary_readers.items():
                    input_key_col = self.conf['secondary_inputs']\
                                              [annotator_name]\
                                               ['match_columns']\
                                                ['primary']
                    input_key_data = input_data[input_key_col]
                    secondary_data[annotator_name] = fetcher.get(input_key_data)
                yield lnum, input_data, secondary_data
            except Exception as e:
                self._log_runtime_error(lnum, e)
                continue
    
    def annotate (self, input_data):
        sys.stdout.write('        annotate method should be implemented. ' +\
                'Exiting ' + self.annotator_display_name + '...\n')
        exit(-1)
        
class SecondaryInputFetcher():
    def __init__(self,
                 input_path,
                 key_col,
                 fetch_cols=[]):
        self.key_col = key_col
        self.input_path = input_path
        self.input_reader = CravatReader(self.input_path)
        valid_cols = self.input_reader.get_column_names()
        if key_col not in valid_cols:
            err_msg = 'Key column %s not present in secondary input %s' \
                %(key_col, self.input_path)
            raise ConfigurationError(err_msg)
        if fetch_cols:
            unmatched_cols = list(set(fetch_cols) - set(valid_cols))
            if unmatched_cols:
                err_msg = 'Column(s) %s not present in secondary input %s' \
                    %(', '.join(unmatched_cols), self.input_path)
                raise ConfigurationError(err_msg)
            self.fetch_cols = fetch_cols
        else:
            self.fetch_cols = valid_cols
        self.data = {}
        self.load_input()
    
    def load_input(self):
        for _, all_col_data in self.input_reader.loop_data('dict'):
            key_data = all_col_data[self.key_col]
            if key_data not in self.data: self.data[key_data] = []
            fetch_col_data = {}
            for col in self.fetch_cols:
                fetch_col_data[col] = all_col_data[col]
            self.data[key_data].append(fetch_col_data)
    
    def get(self, key_data):
        if key_data in self.data:
            return self.data[key_data]
        else:
            return []
        
    def get_values (self, key_data, key_column):
        ret = [v[key_column] for v in self.data[key_data]]
        return ret
