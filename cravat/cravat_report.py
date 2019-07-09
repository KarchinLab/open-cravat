import argparse
import sys
import sqlite3
import os
import json
from cravat.cravat_filter import CravatFilter
from cravat import admin_util as au
from cravat.config_loader import ConfigLoader
from cravat import util
import subprocess
import re
import logging
import time
import cravat.cravat_util as cu
import re
import aiosqlite3

class CravatReport:

    def __init__ (self, cmd_args, status_writer):
        self.status_writer = status_writer
        self.parse_cmd_args(cmd_args)
        self.cursor = None
        self.cf = None
        self.filtertable = 'filter'
        self.colinfo = {}
        self.colnos = {}
        self.ord_cols = {}
        self.var_added_cols = []
        self.summarizing_modules = []
        self.columngroups = {}
        self.column_subs = {}
        self._setup_logger()

    async def prep (self):
        await self.connect_db()
        await self.load_filter()

    def _setup_logger(self):
        if hasattr(self, 'no_log') and self.no_log:
            return
        try:
            self.logger = logging.getLogger('cravat.' + self.module_name)
        except Exception as e:
            self._log_exception(e)
        self.error_logger = logging.getLogger('error.' + self.module_name)
        self.unique_excs = []

    def _log_exception(self, e, halt=True):
        if halt:
            raise e
        else:
            if self.logger:
                self.logger.exception(e)

    async def getjson (self, level):
        ret = None
        if await self.table_exists(level) == False:
            return ret
        for row in await self.cf.getiterator(level):
            row = self.substitute_val(level, row)
            return json.dumps(row) 

    def substitute_val (self, level, row):
        if level in self.column_subs:
            column_sub_level = self.column_subs[level]
            for i in self.column_subs[level]:
                column_sub_i = column_sub_level[i]
                value = row[i]
                if value is not None:
                    if value in column_sub_i:
                        row[i] = column_sub_i[value]
        return row

    async def run_level (self, level):
        ret = await self.table_exists(level)
        if ret == False:
            return
        if level == 'variant':
            await self.cf.make_filtered_uid_table()
        elif level == 'gene':
            await self.cf.make_filtered_hugo_table()
            gene_summary_datas = {}
            for mi, o, cols in self.summarizing_modules:
                gene_summary_data = await o.get_gene_summary_data(self.cf)
                gene_summary_datas[mi.name] = [gene_summary_data, cols]
        self.write_preface(level)
        self.write_header(level)
        if level == 'variant':
            hugo_present = 'base__hugo' in self.colnos['variant']
        for row in await self.cf.get_filtered_iterator(level):
            row = list(row)
            if row is None:
                continue
            if level == 'variant':
                if self.nogenelevelonvariantlevel == False and hugo_present:
                    hugo = row[self.colnos['variant']['base__hugo']]
                    generow = await self.cf.get_gene_row(hugo)
                    for colname in self.var_added_cols:
                        if generow == None:
                            colval = None
                        else:
                            colval = generow[self.colnos['gene'][colname]]
                        row.append(colval)
            elif level == 'gene':
                hugo = row[0]
                for mi, _, _ in self.summarizing_modules:
                    module_name = mi.name
                    [gene_summary_data, cols] = gene_summary_datas[module_name]
                    if hugo in gene_summary_data:
                        row.extend([gene_summary_data[hugo][col['name']] for col in cols])
                    else:
                        row.extend([None for v in cols])
            row = self.substitute_val(level, row)
            if hasattr(self, 'keep_json_all_mapping') == False and level == 'variant':
                colno = self.colnos['variant']['base__all_mappings']
                all_map = json.loads(row[colno])
                newvals = []
                for hugo in all_map:
                    for maprow in all_map[hugo]:
                        [protid, protchange, so, transcript, rnachange] = maprow
                        if protid == None:
                            protid = '(na)'
                        if protchange == None:
                            protchange = '(na)'
                        if rnachange == None:
                            rnachange = '(na)'
                        newval = transcript + ':' + hugo + ':' + protid + ':' + so + ':' + protchange + ':' + rnachange
                        newvals.append(newval)
                newvals.sort()
                newcell = '; '.join(newvals)
                row[colno] = newcell
            newrow = []
            for colname in self.ord_cols[level]:
                colno = self.colnos[level][colname]
                value = row[colno]
                newrow.append(value)
            self.write_table_row(newrow)

    async def run (self, tab='all'):
        start_time = time.time()
        if not (hasattr(self, 'no_log') and self.no_log):
            self.logger.info('started: %s'%time.asctime(time.localtime(start_time)))
        if self.module_conf is not None:
            self.status_writer.queue_status_update('status', 'Started {} ({})'.format(self.module_conf['title'], self.module_name))
        if self.setup() == False:
            return
        if tab == 'all':
            for level in await self.cf.get_result_levels():
                if await self.table_exists(level):
                    await self.make_col_info(level)
            for level in await self.cf.get_result_levels():
                if await self.table_exists(level):
                    await self.run_level(level)
        else:
            if tab in ['variant', 'gene']:
                for level in ['variant', 'gene']:
                    if await self.table_exists(level):
                        await self.make_col_info(level)
            else:
                await self.make_col_info(tab)
            await self.run_level(tab)
        if self.module_conf is not None:
            self.status_writer.queue_status_update('status', 'Finished {} ({})'.format(self.module_conf['title'], self.module_name))
        end_time = time.time()
        if not (hasattr(self, 'no_log') and self.no_log):
            self.logger.info('finished: {0}'.format(time.asctime(time.localtime(end_time))))
            run_time = end_time - start_time
            self.logger.info('runtime: {0:0.3f}'.format(run_time))
        ret = self.end()
        return ret

    async def get_variant_colinfo (self):
        self.setup()
        level = 'variant'
        if await self.table_exists(level):
            await self.make_col_info(level)
        level = 'gene'
        if await self.table_exists(level):
            await self.make_col_info(level)
        return self.colinfo

    def setup (self):
        pass

    def end (self):
        pass

    def write_preface (self, level):
        pass

    def write_header (self, level):
        pass

    async def write_table_row (self, row):
        pass

    async def make_col_info (self, level):
        cravat_conf = self.conf.get_cravat_conf()
        if 'report_module_order' in cravat_conf:
            priority_colgroups = cravat_conf['report_module_order']
        else:
            priority_colgroups = ['base', 'hg19', 'hg18', 'tagsampler']
        # ordered column groups
        self.columngroups[level] = []
        sql = 'select name, displayname from ' + level + '_annotator'
        await self.cursor.execute(sql)
        rows = await self.cursor.fetchall()
        for priority_colgroup in priority_colgroups:
            for row in rows:
                colgroup = row[0]
                if colgroup == priority_colgroup:
                    (name, displayname) = row
                    self.columngroups[level].append(
                        {'name': name,
                         'displayname': displayname,
                         'count': 0})
        for row in rows:
            colgroup = row[0]
            if colgroup in priority_colgroups:
                pass
            else:
                (name, displayname) = row
                self.columngroups[level].append(
                    {'name': name,
                     'displayname': displayname,
                     'count': 0})
        # ordered column names
        sql = 'select * from ' + level + '_header'
        await self.cursor.execute(sql)
        columns = []
        unordered_rows = await self.cursor.fetchall()
        rows = []
        self.ord_cols[level] = []
        for group in priority_colgroups:
            for row in unordered_rows:
                [col_group, col_name] = row[0].split('__')
                if col_group == group:
                    rows.append(row)
                    self.ord_cols[level].append(row[0])
        for row in unordered_rows:
            [col_group, col_name] = row[0].split('__')
            if col_group not in priority_colgroups:
                rows.append(row)
                self.ord_cols[level].append(row[0])
        # unordered column numbers
        self.colnos[level] = {}
        colcount = 0
        for row in unordered_rows:
            self.colnos[level][row[0]] = colcount
            colcount += 1
        # ordered column details
        for row in rows:
            (colname, coltitle, col_type) = row[:3]
            col_cats = json.loads(row[3]) if len(row) > 3 and row[3] else []
            col_width = row[4] if len(row) > 4 else None
            col_desc = row[5] if len(row) > 5 else None
            col_hidden = bool(row[6]) if len(row) > 6 else False
            col_ctg = row[7] if len(row) > 7 else None
            if col_ctg in ['single', 'multi'] and len(col_cats) == 0:
                sql = 'select distinct {} from {}'.format(colname, level)
                await self.cursor.execute(sql)
                rs = await self.cursor.fetchall()
                for r in rs:
                    col_cats.append(r[0])
            col_filterable = bool(row[8]) if len(row) > 8 else True
            link_format = row[9] if len(row) > 9 else None
            column = {'col_name': colname,
                      'col_title': coltitle,
                      'col_type': col_type,
                      'col_cats': col_cats,
                      'col_width':col_width,
                      'col_desc':col_desc,
                      'col_hidden':col_hidden,
                      'col_ctg': col_ctg,
                      'col_filterable': col_filterable,
                      'link_format': link_format,
                      }
            columns.append(column)
            groupname = colname.split('__')[0]
            for columngroup in self.columngroups[level]:
                if columngroup['name'] == groupname:
                    columngroup['count'] += 1
        # adds gene level columns to variant level.
        if self.nogenelevelonvariantlevel == False and level == 'variant' and await self.table_exists('gene'):
            modules_to_add = []
            q = 'select name from gene_annotator'
            await self.cursor.execute(q)
            gene_annotators = [v[0] for v in await self.cursor.fetchall()]
            modules_to_add = [m for m in gene_annotators if m != 'base']
            for module in modules_to_add:
                if not module in gene_annotators:
                    continue
                mi = au.get_local_module_info(module)
                cols = mi.conf['output_columns']
                self.columngroups[level].append({'name': mi.name, 
                                     'displayname': mi.title,
                                     'count': len(cols)})
                for col in cols:
                    colname = mi.name + '__' + col['name']
                    self.colnos[level][colname] = colcount
                    self.ord_cols[level].append(colname)
                    colcount += 1
                    col_type = col['type']
                    col_cats = col.get('categories',[])
                    col_width = col.get('width')
                    col_desc = col.get('desc')
                    col_hidden = col.get('hidden',False)
                    col_ctg = col.get('category', None)
                    if col_ctg in ['category', 'multicategory'] and len(col_cats) == 0:
                        sql = 'select distinct {} from {}'.format(colname, level)
                        await self.cursor.execute(sql)
                        rs = await self.cursor.fetchall()
                        for r in rs:
                            col_cats.append(r[0])
                    col_filterable = col.get('filterable',True)
                    col_link_format = col.get('link_format')
                    column = {'col_name': colname,
                              'col_title': col['title'],
                              'col_type': col_type,
                              'col_cats': col_cats,
                              'col_width':col_width,
                              'col_desc':col_desc,
                              'col_hidden':col_hidden,
                              'col_ctg': col_ctg,
                              'col_filterable': col_filterable,
                              'col_link_format': col_link_format,
                              }
                    columns.append(column)
                    self.var_added_cols.append(colname)
        # Gene level summary columns
        if level == 'gene':
            q = 'select name from variant_annotator'
            await self.cursor.execute(q)
            done_var_annotators = [v[0] for v in await self.cursor.fetchall()]
            self.summarizing_modules = []
            local_modules = au.get_local_module_infos_of_type('annotator')
            for module_name in local_modules:
                mi = local_modules[module_name]
                conf = mi.conf
                if 'can_summarize_by_gene' in conf and module_name in done_var_annotators:
                    sys.path = sys.path + [os.path.dirname(mi.script_path)]
                    annot_cls = util.load_class('CravatAnnotator', mi.script_path)
                    annot = annot_cls([mi.script_path, '__dummy__'], {})
                    cols = conf['gene_summary_output_columns']
                    for col in cols:
                        col['name'] = col['name'] 
                    columngroup = {}
                    columngroup['name'] = conf['name']
                    columngroup['displayname'] = conf['title']
                    columngroup['count'] = len(cols)
                    self.columngroups[level].append(columngroup)
                    for col in cols:
                        col_type = col['type']
                        col_cats = col.get('categories', [])
                        col_ctg = col.get('category', None)
                        if col_type in ['category', 'multicategory'] and len(col_cats) == 0:
                            sql = 'select distinct {} from {}'.format(colname, level)
                            await self.cursor.execute(sql)
                            rs = await self.cursor.fetchall()
                            for r in rs:
                                col_cats.append(r[0])
                        col_filterable = col.get('filterable', True)
                        col_link_format = col.get('link_format')
                        column = {'col_name': conf['name'] + '__' + col['name'],
                                  'col_title': col['title'],
                                  'col_type': col_type,
                                  'col_cats': col_cats,
                                  'col_width':col.get('width'),
                                  'col_desc':col.get('desc'),
                                  'col_hidden':col.get('hidden',False),
                                  'col_ctg': col_ctg,
                                  'col_filterable': col_filterable,
                                  'col_link_format': col_link_format,
                                  }
                        columns.append(column)
                    self.summarizing_modules.append([mi, annot, cols])
                    for col in cols:
                        fullname = module_name+'__'+col['name']
                        self.ord_cols[level].append(fullname)
                        self.colnos[level][fullname] = len(self.colnos[level])
        colno = 0
        for colgroup in self.columngroups[level]:
            colno += colgroup['count']
            colgroup['lastcol'] = colno
        self.colinfo[level] = {'colgroups': self.columngroups[level], 'columns': columns}
        # report substitution
        if level in ['variant', 'gene']:
            reportsubtable = level + '_reportsub'
            if await self.table_exists(reportsubtable):
                q = 'select * from {}'.format(reportsubtable)
                await self.cursor.execute(q)
                rs = await self.cursor.fetchall()
                self.report_substitution = {}
                for r in rs:
                    module = r[0]
                    sub = json.loads(r[1])
                    self.report_substitution[module] = sub
                self.column_subs[level] = {}
                columns = self.colinfo[level]['columns']
                for i in range(len(columns)):
                    column = columns[i]
                    [module, col] = column['col_name'].split('__')
                    if module in self.report_substitution:
                        sub = self.report_substitution[module]
                        if col in sub:
                            self.column_subs[level][i] = sub[col]
                            self.colinfo[level]['columns'][i]['reportsub'] = sub[col]

    def parse_cmd_args (self, cmd_args):
        parser = argparse.ArgumentParser()
        parser.add_argument('dbpath',
                            help='Path to aggregator output')
        parser.add_argument('-f',
            dest='filterpath',
            default=None,
            help='Path to filter file')
        parser.add_argument('-F',
            dest='filtername',
            default=None,
            help='Name of filter (stored in aggregator output)')
        parser.add_argument('--filterstring',
            dest='filterstring',
            default=None,
            help='Filter in JSON')
        parser.add_argument('-s',
            dest='savepath',
            default=None,
            help='Path to save file')
        parser.add_argument('-c',
            dest='confpath',
            help='path to a conf file')
        parser.add_argument('-t',
            dest='reporttypes',
            nargs='+',
            default=None,
            help='report types')
        parser.add_argument('--module-name',
            dest='module_name',
            default=None,
            help='report module name')
        parser.add_argument('--nogenelevelonvariantlevel',
            dest='nogenelevelonvariantlevel',
            action='store_true',
            default=False,
            help='Use this option to prevent gene level result from being added to variant level result.')
        parser.add_argument('--confs',
            dest='confs',
            default='{}',
            help='Configuration string')
        parser.add_argument('--inputfiles',
            nargs='+',
            dest='inputfiles',
            default=None,
            help='Original input file path')
        parsed_args = parser.parse_args(cmd_args[1:])
        self.parsed_args = parsed_args
        self.dbpath = parsed_args.dbpath
        self.filterpath = parsed_args.filterpath
        self.filtername = parsed_args.filtername
        self.filterstring = parsed_args.filterstring
        self.savepath = parsed_args.savepath
        self.confpath = parsed_args.confpath
        self.conf = ConfigLoader(job_conf_path=self.confpath)
        self.module_name = parsed_args.module_name
        if self.conf is not None:
            self.module_conf = self.conf.get_module_conf(self.module_name)
        else:
            self.module_conf = None
        self.report_types = parsed_args.reporttypes
        self.output_basename = os.path.basename(self.dbpath)[:-7]
        self.output_dir = os.path.dirname(self.dbpath)
        status_fname = '{}.status.json'.format(self.output_basename)
        self.status_fpath = os.path.join(self.output_dir, status_fname)
        self.nogenelevelonvariantlevel = parsed_args.nogenelevelonvariantlevel
        self.confs = None
        if parsed_args.confs is not None:
            confs = parsed_args.confs.lstrip('\'').rstrip('\'').replace("'", '"')
            self.confs = json.loads(confs)
        self.args = parsed_args

    async def connect_db (self, dbpath=None):
        if dbpath != None:
            self.dbpath = dbpath
        if self.dbpath == None:
            sys.stderr.write('Provide a path to aggregator output')
            exit()
        if os.path.exists(self.dbpath) == False:
            sys.stderr.write(self.dbpath + ' does not exist.')
            exit()
        self.conn = await aiosqlite3.connect(self.dbpath)
        self.cursor = await self.conn.cursor()

    async def load_filter (self):
        self.cf = await CravatFilter.create(dbpath=self.dbpath)
        await self.cf.loadfilter(filterpath=self.filterpath, filtername=self.filtername, filterstring=self.filterstring)

    async def table_exists (self, tablename):
        sql = 'select name from sqlite_master where ' + \
            'type="table" and name="' + tablename + '"'
        await self.cursor.execute(sql)
        row = await self.cursor.fetchone()
        if row == None:
            ret = False
        else:
            ret = True
        return ret

def main ():
    if len(sys.argv) < 2:
        print('Please provide a sqlite file path')
        exit()
    parser = argparse.ArgumentParser()
    parser.add_argument('dbpath',
                        help='Path to aggregator output')
    parser.add_argument('-t',
        dest='reporttypes',
        nargs='+',
        default=None,
        help='report types')
    parsed_args = parser.parse_args(sys.argv[1:])
    dbpath = parsed_args.dbpath
    report_types = parsed_args.reporttypes
    run_name = os.path.basename(dbpath).rstrip('sqlite').rstrip('.')
    output_dir = os.path.dirname(dbpath)
    avail_reporters = au.get_local_module_infos_of_type('reporter')
    avail_reporter_names = [re.sub('reporter$', '', v) for v in avail_reporters.keys()]
    cmd = ['cravat', 'dummyinput', '-n', run_name, '-d', output_dir, '--skip', 'converter', 'mapper', 'annotator', 'aggregator', 'postaggregator', '--startat', 'reporter', '--repeat', 'reporter', '-t']
    if report_types is not None:
        cmd.extend(report_types)
    else:
        cmd.extend(avail_reporter_names)
    subprocess.run(cmd)
