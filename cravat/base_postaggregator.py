import sqlite3
import sys
import traceback
import logging
import os
import time
import argparse 
from cravat.util import get_caller_name
from cravat.config_loader import ConfigLoader
from cravat.constants import VARIANT, GENE, LEVELS
from cravat.exceptions import InvalidData

class BasePostAggregator (object):
    
    def __init__(self, cmd_args):
        try:
            # self.module_name = get_caller_name(sys.modules[self.__module__].__file__)
            self.module_name = get_caller_name(cmd_args[0])
            self.parse_cmd_args(cmd_args)
            self._setup_logger()
            config_loader = ConfigLoader()
            self.conf = config_loader.get_module_conf(self.module_name)
            self.fix_col_names()
            self.dbconn = None
            self.cursor = None
            self.cursor_w = None
            self._open_db_connection()
            self.should_run_annotate = self.check()
        except Exception as e:
            self._log_exception(e)

    def check(self):
        """
        Return boolean indicating whether main 'annotate' loop should be run.
        Should be overridden in sub-classes.
        """
        return True
    
    def fix_col_names (self):
        for col in self.conf['output_columns']:
            col['name'] = self.module_name + '__' + col['name']
            
    def _log_exception(self, e, halt=True):
        if self.logger:
            self.logger.exception(e)
        if halt:
            sys.exit(traceback.format_exc())
        else:
            traceback.print_exc()
    
    def _define_cmd_parser(self):
        try:
            parser = argparse.ArgumentParser()
            parser.add_argument('-n',
                                dest='run_name',
                                help='name of cravat run')
            parser.add_argument('-d',
                                dest='output_dir',
                                help='Output directory. '\
                                     +'Default is input file directory.')
            parser.add_argument('-l',
                                dest='level',
                                default='variant',
                                help='Summarize level. '\
                                     +'Default is variant.')
            self.cmd_arg_parser = parser
        except Exception as e:
            self._log_exception(e)
    
    def parse_cmd_args(self, cmd_args):
        self._define_cmd_parser()
        parsed_args = self.cmd_arg_parser.parse_args(cmd_args[1:])
        if parsed_args.run_name:
            self.run_name = parsed_args.run_name
        if parsed_args.output_dir:
            self.output_dir = parsed_args.output_dir
        if parsed_args.level:
            self.level = parsed_args.level
        self.levelno = LEVELS[self.level]
        self.dbpath = os.path.join(self.output_dir, self.run_name + '.sqlite')

    def run(self):
        if not self.should_run_annotate:
            return
        try:
            start_time = time.time()
            self.logger.info('started: {0}'.format(time.asctime(time.localtime(start_time))))
            self.base_setup()
            for input_data in self._get_input():
                try:
                    output_dict = self.annotate(input_data)
                    fixed_output = {}
                    for k, v in output_dict.items():
                        fixed_output[self.module_name + '__' + k] = v
                    self.write_output(input_data, fixed_output)
                except Exception as e:
                    self._log_runtime_exception(input_data, e)
            self.dbconn.commit()
            self.base_cleanup()
            end_time = time.time()
            run_time = end_time - start_time
            self.logger.info('finished: {0}'.format(time.asctime(time.localtime(end_time))))
            self.logger.info('runtime: {0:0.3f}'.format(run_time))
        except Exception as e:
            self._log_exception(e)
    
    def write_output (self, input_data, output_dict):
        q = 'update ' + self.level + ' set '
        for col_def in self.conf['output_columns']:
            col_name = col_def['name']
            if col_name in output_dict:
                val = output_dict[col_name]
                if col_def['type'] == 'string':
                    val = '"' + val + '"'
                else:
                    val = str(val)
                q += col_name + '=' + val + ','
        q = q.rstrip(',')
        q += ' where '
        if self.levelno == VARIANT:
            q += 'base__uid=' + str(input_data['base__uid'])
        elif self.levelno == GENE:
            q += 'base__hugo="' + input_data['base__hugo'] + '"'
        self.cursor_w.execute(q)
        
    def _log_runtime_exception(self, input_data, e):
        try:
            error_classname = e.__class__.__name__
            err_line = '\t'.join([error_classname, str(e)])
            self.invalid_file.write(err_line + '\n')
            if not(isinstance(e,InvalidData)):
                self._log_exception(e, halt=False)
        except Exception as e:
            self._log_exception(e, halt=False)
    
    # Setup function for the base_annotator, different from self.setup() 
    # which is intended to be for the derived annotator.
    def base_setup(self):
        self._alter_tables()
        self.setup()
    
    def _open_db_connection (self):
        self.db_path = os.path.join(self.output_dir, self.run_name + '.sqlite')
        if os.path.exists(self.db_path):
            self.dbconn = sqlite3.connect(self.db_path)
            self.cursor = self.dbconn.cursor()
            self.cursor_w = self.dbconn.cursor()
        else:
            msg = self.db_path + ' not found'
            if self.logger:
                self.logger.error(msg)
            sys.exit(msg)
    
    def _close_db_connection (self):
        self.cursor.close()
        self.cursor_w.close()
        self.dbconn.close()
    
    def _alter_tables (self):
        # annotator table
        q = 'insert into {:} values ("{:}", "{:}")'.format(
            self.level + '_annotator', self.module_name, self.conf['title'])
        self.cursor_w.execute(q)
        # data table and header table
        header_table_name = self.level + '_header'
        for col_def in self.conf['output_columns']:
            colname = col_def['name']
            coltitle = col_def['title']
            coltype = col_def['type']
            # data table
            q = 'alter table ' + self.level + ' add column ' +\
                colname + ' ' + coltype
            self.cursor_w.execute(q)
            # header table
            q = 'insert into {} values ("{}", "{}", "{}")'.format(
                header_table_name, colname, coltitle, coltype)
            self.cursor_w.execute(q)
        self.dbconn.commit()
        
    # Placeholder, intended to be overridded in derived class
    def setup(self):
        pass
    
    def base_cleanup(self):
        self.cleanup()
        if self.dbconn != None:
            self._close_db_connection()

    def cleanup(self):
        pass
            
    def _setup_logger(self):
        try:
            self.logger = logging.getLogger('cravat.' + self.module_name)
        except Exception as e:
            self._log_exception(e)
        
    def _get_input(self):
        dbconnloop = sqlite3.connect(self.db_path)
        cursorloop = dbconnloop.cursor()
        q = 'select * from ' + self.level
        cursorloop.execute(q)
        for row in cursorloop.fetchall():
            try:
                input_data = {}
                for i in range(len(row)):
                    input_data[cursorloop.description[i][0]] = row[i]
                yield input_data
            except Exception as e:
                self._log_runtime_error(e)
                continue
    
    def annotate (self, input_data):
        sys.stdout.write('        annotate method should be implemented. ' +\
                'Exiting ' + self.annotator_display_name + '...\n')
        exit(-1)
