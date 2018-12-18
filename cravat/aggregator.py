import os
import argparse
import sys
import sqlite3
import re
import time
import logging
import yaml
from cravat import CravatReader
from cravat import CravatWriter
import json

class Aggregator (object):
    
    cr_type_to_sql = {'string':'text',
                      'int':'integer',
                      'float':'real'}
    commit_threshold = 10000
    
    def __init__(self, cmd_args):
        self.annotators = []
        self.ipaths = {}
        self.readers = {}
        self.base_fpath = None
        self.level = None
        self.input_dir = None
        self.input_base_fname = None
        self.output_dir = None
        self.output_base_fname = None
        self.key_name = None
        self.table_name = None
        self.base_prefix = 'base'
        self.base_dir = os.path.abspath(__file__)
        self.parse_cmd_args(cmd_args)
        self._setup_logger()
        
    def parse_cmd_args(self, cmd_args):
        parser = argparse.ArgumentParser()
        parser.add_argument('path',
                            help='Path to this aggregator module')
        parser.add_argument('-i',
                            dest='input_dir',
                            required=True,
                            help='Directory containing annotator outputs')
        parser.add_argument('-l',
                            dest='level',
                            required= True,
                            help='Level to aggregate')
        parser.add_argument('-n',
                            dest='name',
                            required=True,
                            help='Name of run')
        parser.add_argument('-d',
                            dest='output_dir',
                            help='Directory for aggregator output. '\
                                 +'Default is input directory.')
        parser.add_argument('-x',
                            dest='delete',
                            action='store_true',
                            help='Deletes the existing one and creates ' +\
                                 'a new one.')
        parsed = parser.parse_args(cmd_args)
        self.level = parsed.level
        self.name = parsed.name
        self.input_dir = os.path.abspath(parsed.input_dir)
        if parsed.output_dir:
            self.output_dir = parsed.output_dir
        else:
            self.output_dir = self.input_dir
        self.set_input_base_fname()
        if self.input_base_fname == None:
            exit()
        self.set_output_base_fname()
        if not(os.path.exists(self.output_dir)):
            os.makedirs(self.output_dir)
        self.delete = parsed.delete
    
    def _setup_logger(self):
        self.logger = logging.getLogger('cravat.aggregator')
        self.logger.info('level: {0}'.format(self.level))
        self.logger.info('input directory: %s' %self.input_dir)
        
    def run(self):
        self._setup()
        if self.input_base_fname == None:
            return
        start_time = time.time()
        self.logger.info('started: %s' %\
                         time.asctime(time.localtime(start_time)))
        self.dbconn.commit()
        self.cursor.execute('pragma synchronous=0;')
        self.cursor.execute('pragma journal_mode=WAL;')
        n = 0
        for _, rd in self.base_reader.loop_data():
            n += 1
            names = list(rd.keys())
            values = []
            for name in names:
                val = rd[name]
                valtype = type(val)
                if valtype is str:
                    val = '\'' + val + '\''
                else:
                    if val == None:
                        val = '\'\''
                    else:
                        val = str(val)
                values.append(val)
            q = 'insert into %s (%s) values (%s);' \
                %(self.table_name, 
                  ', '.join([self.base_prefix + '__' + v for v in names]), 
                  ', '.join(values))
            self.cursor.execute(q)
            if n%self.commit_threshold == 0:
                self.dbconn.commit()
        self.dbconn.commit()
        for annot_name in self.annotators:
            reader = self.readers[annot_name]
            n = 0
            for _, rd in reader.loop_data():
                n += 1
                key_val = rd[self.key_name]
                reader_col_names = [x for x in rd if x != self.key_name]
                update_toks = []
                for reader_col_name in reader_col_names:
                    db_col_name = '%s__%s' %(annot_name, reader_col_name)
                    val = rd[reader_col_name]
                    set_val = 'null'
                    if val is not None:
                        if type(val) is str:
                            set_val = '"%s"' %val
                        else:
                            set_val = str(val)
                    update_toks.append('%s=%s' %(db_col_name, set_val))
                q = 'update %s set %s where %s="%s";' %(
                    self.table_name,
                    ', '.join(update_toks),
                    self.base_prefix + '__' + self.key_name,
                    key_val)
                self.cursor.execute(q)
                if n%self.commit_threshold == 0:
                    self.dbconn.commit()
            self.dbconn.commit()
        self.fill_categories()
        self.cursor.execute('pragma synchronous=2;')
        self.cursor.execute('pragma journal_mode=delete;')
        end_time = time.time()
        self.logger.info('finished: %s' %time.asctime(time.localtime(end_time)))
        runtime = end_time - start_time
        self.logger.info('runtime: %s' %round(runtime, 3))
        self._cleanup()

    def make_reportsub (self):
        if self.level in ['variant', 'gene']:
            q = 'select * from {}_reportsub'.format(self.level)
            self.cursor.execute(q)
            self.reportsub = {}
            for r in self.cursor.fetchall():
                (col_name, sub) = r
                self.reportsub[col_name] = json.loads(sub)
        else:
            self.reportsub = {}

    def do_reportsub_col_cats_str (self, col_name, col_cats):
        (module_name, col) = col_name.split('__')
        if module_name in self.reportsub and col in self.reportsub[module_name]:
            sub = self.reportsub[module_name][col]
            for k in sub:
                col_cats = col_cats.replace(k, sub[k])
        return col_cats

    def fill_categories (self):
        q = 'select * from {}_header'.format(self.level)
        self.cursor.execute(q)
        rs = self.cursor.fetchall()
        cols_to_fill = []
        for r in rs:
            col_name = r[0]
            col_type = r[2]
            col_cats_str = r[3]
            if len(r) > 7:
                col_ctg = r[7]
            else:
                col_ctg = None
            if col_ctg in ['single', 'multi']:
                if col_cats_str == None or len(col_cats_str) == 0 or col_cats_str == '[]':
                    cols_to_fill.append(col_name)
                else:
                    col_cats_str = self.do_reportsub_col_cats_str(col_name, col_cats_str)
                    self.write_col_cats_str(col_name, col_cats_str)
        for col_name in cols_to_fill:
            q = 'select distinct {} from {}'.format(col_name, self.level)
            self.cursor.execute(q)
            rs = self.cursor.fetchall()
            col_cats = []
            for r in rs:
                if r[0] == None:
                    continue
                vals = r[0].split(';')
                for col_cat in vals:
                    if col_cat not in col_cats:
                        col_cats.append(col_cat)
            col_cats.sort()
            col_cats_str = '[' + ','.join(['"' + v + '"' for v in col_cats]) + ']'
            col_cats_str = self.do_reportsub_col_cats_str(col_name, col_cats_str)
            self.write_col_cats_str(col_name, col_cats_str)
        self.dbconn.commit()
    
    def write_col_cats_str (self, col_name, col_cats_str):
        q = 'update {}_header set col_cats=\'{}\' where col_name=\'{}\''.format(
            self.level,
            col_cats_str,
            col_name)
        self.cursor.execute(q)

    def _cleanup(self):
        self.cursor.close()
        self.dbconn.close()
    
    def set_input_base_fname (self):
        crv_fname = self.name + '.crv'
        crx_fname = self.name + '.crx'
        crg_fname = self.name + '.crg'
        crs_fname = self.name + '.crs'
        crm_fname = self.name + '.crm'
        for fname in os.listdir(self.input_dir):
            if self.level == 'variant':
                if fname == crx_fname:
                    self.input_base_fname = fname
                elif fname == crv_fname and not self.input_base_fname:
                    self.input_base_fname = fname
            elif self.level == 'gene' and fname == crg_fname:
                self.input_base_fname = fname
            elif self.level == 'sample' and fname == crs_fname:
                self.input_base_fname = fname
            elif self.level == 'mapping' and fname == crm_fname:
                self.input_base_fname = fname
    
    def set_output_base_fname (self):
        self.output_base_fname = self.name
        
    def _setup(self):
        if self.level == 'variant':
            self.key_name = 'uid'
        elif self.level == 'gene':
            self.key_name = 'hugo'
        elif self.level == 'sample':
            self.key_name = ''
        elif self.level == 'mapping':
            self.key_name = ''
        self.table_name = self.level
        self.header_table_name = self.table_name + '_header'
        self.reportsub_table_name = self.table_name + '_reportsub'
        annot_name_re = re.compile('.*\.(.*)\.[var,gen]')
        for fname in os.listdir(self.input_dir):
            if fname.startswith(self.name + '.'):
                if self.level == 'variant' and fname.endswith('.var'):
                    annot_name_match = annot_name_re.match(fname)
                    annot_name = annot_name_match.group(1)
                    self.annotators.append(annot_name)
                    self.ipaths[annot_name] = \
                        os.path.join(self.input_dir, fname)
                elif self.level == 'gene' and fname.endswith('.gen'):
                    annot_name_match = annot_name_re.match(fname)
                    annot_name = annot_name_match.group(1)
                    self.annotators.append(annot_name)
                    self.ipaths[annot_name] = \
                        os.path.join(self.input_dir, fname)
        self.annotators.sort()
        self.base_fpath = os.path.join(self.input_dir, self.input_base_fname)
        self._setup_io()
        self._setup_table()
  
    def _setup_table(self):
        columns = []
        unique_names = set([])
        # annotator table
        annotator_table = self.level + '_annotator'
        q = 'drop table if exists {:}'.format(annotator_table)
        self.cursor.execute(q)
        q = 'create table {:} (name text, displayname text)'.format(
            annotator_table)
        self.cursor.execute(q)
        q = 'insert into {:} values ("{:}", "{:}")'.format(
            annotator_table, 'base', 'Base Information')
        self.cursor.execute(q)
        for _, col_def in self.base_reader.get_all_col_defs().items():
            col_name = self.base_prefix + '__' + col_def['name']
            columns.append([col_name, col_def['title'], col_def['type'], col_def['categories'], col_def['width'], col_def['desc'], col_def['hidden'], col_def['category']])
            unique_names.add(col_name)
        for annot_name in self.annotators:
            reader = self.readers[annot_name]
            annotator_name = reader.get_annotator_name()
            if annotator_name == '':
                annotator_name = annot_name
            annotator_displayname = reader.get_annotator_displayname()
            if annotator_displayname == '':
                annotator_displayname = annotator_name.upper()
            q = 'insert into {:} values ("{:}", "{:}")'.format(
                annotator_table, annotator_name, annotator_displayname)
            self.cursor.execute(q)
            orded_col_index = sorted(list(reader.get_all_col_defs().keys()))
            for col_index in orded_col_index:
                col_def = reader.get_col_def(col_index)
                reader_col_name = col_def['name']
                if reader_col_name == self.key_name: continue
                db_col_name = '%s__%s' %(annot_name, reader_col_name)
                db_type = col_def['type']
                db_col_title = col_def['title']
                db_col_cats = col_def['categories']
                if db_col_name in unique_names:
                    err_msg = 'Duplicate column name %s found in %s. ' \
                        %(db_col_name, reader.path)
                    sys.exit(err_msg)
                else:
                    columns.append([db_col_name, db_col_title, db_type, db_col_cats, col_def['width'], col_def['desc'], col_def['hidden'], col_def['category']])
                    unique_names.add(db_col_name)
        col_def_strings = []
        for col in columns:
            name = col[0]
            sql_type = self.cr_type_to_sql[col[2]]
            s = name + ' ' + sql_type
            col_def_strings.append(s)
        # data table
        q = 'drop table if exists %s' %self.table_name
        self.cursor.execute(q)
        q = 'create table %s (%s);' \
            %(self.table_name, ', '.join(col_def_strings))
        self.cursor.execute(q)
        # index tables
        index_n = 0
        # index_columns is a list of columns to include in this index
        for index_columns in self.base_reader.get_index_columns():
            cols = ['base__{0}'.format(x) for x in index_columns]
            q = 'create index {table_name}_idx_{idx_num} on {table_name} ({columns});'\
                .format(table_name = self.table_name,
                        idx_num = str(index_n),
                        columns = ', '.join(cols)
                        )
            self.cursor.execute(q)
            index_n += 1
        # header table
        q = 'drop table if exists %s' %self.header_table_name
        self.cursor.execute(q)
        q = 'create table %s (col_name text, col_title text, col_type text, col_cats text, col_width int, col_desc text, col_hidden boolean, col_ctg text);' \
            %(self.header_table_name)
        self.cursor.execute(q)
        for col_row in columns:
            if col_row[3]:
                col_row[3] = json.dumps(col_row[3])
            # use prepared statement to allow " characters in categories and desc
            insert_template = 'insert into {} values (?, ?, ?, ?, ?, ?, ?, ?)'.format(self.header_table_name)
            self.cursor.execute(insert_template, col_row)
        # report substitution table
        if self.level in ['variant', 'gene']:
            q = 'drop table if exists {}'.format(self.reportsub_table_name)
            self.cursor.execute(q)
            q = 'create table {} (module text, subdict text)'.format(self.reportsub_table_name)
            self.cursor.execute(q)
            if hasattr(self.base_reader, 'report_substitution'):
                sub = self.base_reader.report_substitution
                if sub:
                    module = 'base'
                    q = 'insert into {} values (\'{}\', \'{}\')'.format(
                        self.reportsub_table_name,
                        'base',
                        json.dumps(sub)
                    )
                    self.cursor.execute(q)
            for module in self.readers:
                if hasattr(self.base_reader, 'report_substitution'):
                    sub = self.readers[module].report_substitution
                    if sub:
                        q = 'insert into {} values ("{}", \'{}\')'.format(
                            self.reportsub_table_name,
                            module,
                            json.dumps(sub)
                        )
                        self.cursor.execute(q)
        self.make_reportsub()
        self.dbconn.commit()

    def _setup_io(self):
        self.base_reader = CravatReader(self.base_fpath)
        for annot_name in self.annotators:
            self.readers[annot_name] = CravatReader(self.ipaths[annot_name])
        self.db_fname = self.output_base_fname + '.sqlite'
        self.db_path = os.path.join(self.output_dir, self.db_fname)
        if self.delete and os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.dbconn = sqlite3.connect(self.db_path)
        self.cursor = self.dbconn.cursor()

if __name__ == '__main__':
    aggregator = Aggregator(sys.argv)
    aggregator.run()
