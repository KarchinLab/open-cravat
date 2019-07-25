import argparse
import sys
import sqlite3
import os
import json
from cravat.cravat_filter import CravatFilter
from cravat import admin_util as au
from cravat.config_loader import ConfigLoader
from cravat import util
from cravat.inout import ColumnDefinition
import subprocess
import re
import logging
import time
import cravat.cravat_util as cu
import re
import aiosqlite3
import types

class CravatReport:

    def __init__ (self, cmd_args, status_writer):
        self.status_writer = status_writer
        self.parse_cmd_args(cmd_args)
        self.cursor = None
        self.cf = None
        self.filtertable = 'filter'
        self.colinfo = {}
        self.colnos = {}
        self.var_added_cols = []
        self.summarizing_modules = []
        self.columngroups = {}
        self.column_subs = {}
        self.column_sub_allow_partial_match = {}
        self.colname_conversion = {}
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
            column_sub_dict = self.column_subs[level]
            column_sub_allow_partial_match = self.column_sub_allow_partial_match[level]
            for colno in column_sub_dict:
                column_sub = column_sub_dict[colno]
                value = row[colno]
                if value is not None:
                    if column_sub_allow_partial_match[colno] == True:
                        for target in column_sub:
                            value = re.sub('\\b' + target + '\\b', column_sub[target], value)
                    else:
                        if value in column_sub:
                            value = column_sub[value]
                    row[colno] = value
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
        datacols, datarows = await self.cf.get_filtered_iterator(level)
        for datarow in datarows:
            if datarow is None:
                continue
            datarow = list(datarow)
            if level == 'variant':
                # adds gene level data to variant level.
                if self.nogenelevelonvariantlevel == False and hugo_present:
                    hugo = datarow[self.colnos['variant']['base__hugo']]
                    generow = await self.cf.get_gene_row(hugo)
                    if generow is None:
                        datarow.extend([None for i in range(len(self.var_added_cols))])
                    else:
                        datarow.extend([generow[self.colnos['gene'][colname]] for colname in self.var_added_cols])
            elif level == 'gene':
                # adds summary data to gene level.
                hugo = datarow[0]
                for mi, _, _ in self.summarizing_modules:
                    module_name = mi.name
                    [gene_summary_data, cols] = gene_summary_datas[module_name]
                    if hugo in gene_summary_data and gene_summary_data[hugo] is not None and len(gene_summary_data[hugo]) == len(cols):
                        datarow.extend([gene_summary_data[hugo][col['name']] for col in cols])
                    else:
                        datarow.extend([None for v in cols])
            # does report substitution.
            datarow = self.substitute_val(level, datarow)
            if hasattr(self, 'keep_json_all_mapping') == False and level == 'variant':
                colno = self.colnos['variant']['base__all_mappings']
                all_map = json.loads(datarow[colno])
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
                datarow[colno] = newcell
            # re-orders data row.
            new_datarow = []
            colnos = self.colnos[level]
            for colname in [col['col_name'] for col in self.colinfo[level]['columns']]:
                #if colname not in colnos:
                if colname in self.colname_conversion[level]:
                    newcolname = self.colname_conversion[level][colname]
                    #newcolname = self.mapper_name + '__' + colname.split('__')[1]
                    if newcolname in colnos:
                        colno = colnos[newcolname]
                    else:
                        self.logger.info('column name does not exist in data: {}'.format(colname))
                        continue
                else:
                    colno = colnos[colname]
                value = datarow[colno]
                new_datarow.append(value)
            self.write_table_row(new_datarow)

    async def store_mapper (self):
        q = 'select colval from info where colkey="_mapper"'
        await self.cursor.execute(q)
        r = await self.cursor.fetchone()
        if r is None:
            self.mapper_name = 'hg38'
        else:
            self.mapper_name = r[0].split(':')[0]

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
        await self.store_mapper()
        cravat_conf = self.conf.get_cravat_conf()
        if 'report_module_order' in cravat_conf:
            priority_colgroupnames = cravat_conf['report_module_order']
        else:
            priority_colgroupnames = ['base', 'hg38', 'hg19', 'hg18', 'tagsampler']
        # level-specific column groups
        self.columngroups[level] = []
        sql = 'select name, displayname from ' + level + '_annotator'
        await self.cursor.execute(sql)
        rows = await self.cursor.fetchall()
        for row in rows:
            (name, displayname) = row
            self.columngroups[level].append(
                {'name': name, 'displayname': displayname, 'count': 0}
            )
        # level-specific column names
        header_table = level+'_header'
        sql = 'pragma table_info("{}")'.format(header_table)
        await self.cursor.execute(sql)
        header_cols = [row[1] for row in await self.cursor.fetchall()]
        select_order = [cname for cname in ColumnDefinition.column_order if cname in header_cols]
        sql = 'select {} from {}'.format(
            ', '.join(select_order),
            header_table
        )
        # sql = 'select * from ' + level + '_header'
        await self.cursor.execute(sql)
        columns = []
        column_headers = await self.cursor.fetchall()
        # level-specific column numbers
        self.colnos[level] = {}
        colcount = 0
        for column_header in column_headers:
            self.colnos[level][column_header[0]] = colcount
            colcount += 1
        # level-specific column details
        for column_header in column_headers:
            coldef = ColumnDefinition({})
            coldef.from_row(column_header, order=select_order)
            if coldef.category in ['single', 'multi'] and len(coldef.categories) == 0:
                sql = 'select distinct {} from {}'.format(coldef.name, level)
                await self.cursor.execute(sql)
                rs = await self.cursor.fetchall()
                for r in rs:
                    coldef.categories.append(r[0])
            [colgrpname, colonlyname] = coldef.name.split('__')
            column = coldef.get_colinfo()
            columns.append(column)
            for columngroup in self.columngroups[level]:
                if columngroup['name'] == colgrpname:
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
                    coldef = ColumnDefinition(col)
                    coldef.name = mi.name + '__' + coldef.name
                    self.colnos[level][coldef.name] = colcount
                    colcount += 1
                    if coldef.category in ['category', 'multicategory'] and len(coldef.categories) == 0:
                        sql = 'select distinct {} from {}'.format(coldef.name, level)
                        await self.cursor.execute(sql)
                        rs = await self.cursor.fetchall()
                        for r in rs:
                            coldef.categories.append(r[0])
                    column = coldef.get_colinfo()
                    columns.append(column)
                    self.var_added_cols.append(coldef.name)
        # Gene level summary columns
        if level == 'gene':
            q = 'select name from variant_annotator'
            await self.cursor.execute(q)
            done_var_annotators = [v[0] for v in await self.cursor.fetchall()]
            self.summarizing_modules = []
            local_modules = au.get_local_module_infos_of_type('annotator')
            summarizer_module_names = []
            for module_name in done_var_annotators:
                if module_name == 'base' or module_name not in local_modules:
                    continue
                module = local_modules[module_name]
                if 'can_summarize_by_gene' in module.conf:
                    summarizer_module_names.append(module_name)
            local_modules[self.mapper_name] = au.get_local_module_info(self.mapper_name)
            summarizer_module_names = [self.mapper_name] + summarizer_module_names
            for module_name in summarizer_module_names:
                mi = local_modules[module_name]
                conf = mi.conf
                sys.path = sys.path + [os.path.dirname(mi.script_path)]
                if module_name in done_var_annotators:
                    annot_cls = util.load_class('CravatAnnotator', mi.script_path)
                elif module_name == self.mapper_name:
                    annot_cls = util.load_class('Mapper', mi.script_path)
                annot = annot_cls([mi.script_path, '__dummy__'], {})
                cols = conf['gene_summary_output_columns']
                columngroup = {}
                columngroup['name'] = conf['name']
                columngroup['displayname'] = conf['title']
                columngroup['count'] = len(cols)
                self.columngroups[level].append(columngroup)
                for col in cols:
                    coldef = ColumnDefinition(col)
                    coldef.name = conf['name']+'__'+coldef.name
                    coldef.genesummary = True
                    if coldef.type in ['category', 'multicategory'] and len(coldef.categories) == 0:
                        sql = 'select distinct {} from {}'.format(colname, level)
                        await self.cursor.execute(sql)
                        rs = await self.cursor.fetchall()
                        for r in rs:
                            coldef.categories.append(r[0])
                    column = coldef.get_colinfo()
                    columns.append(column)
                self.summarizing_modules.append([mi, annot, cols])
                for col in cols:
                    fullname = module_name+'__'+col['name']
                    self.colnos[level][fullname] = len(self.colnos[level])
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
                self.column_sub_allow_partial_match[level] = {}
                for i in range(len(columns)):
                    column = columns[i]
                    [module, col] = column['col_name'].split('__')
                    if module in [self.mapper_name]:
                        module = 'base'
                    if module in self.report_substitution:
                        sub = self.report_substitution[module]
                        if col in sub:
                            self.column_subs[level][i] = sub[col]
                            if module in ['base', self.mapper_name] and col in ['all_mappings', 'all_so']:
                                allow_partial_match = True
                            else:
                                allow_partial_match = False
                            self.column_sub_allow_partial_match[level][i] = allow_partial_match
                            columns[i]['reportsub'] = sub[col]
        # re-orders columns groups.
        colgrps = self.columngroups[level]
        newcolgrps = []
        for priority_colgrpname in priority_colgroupnames:
            for colgrp in colgrps:
                if colgrp['name'] == priority_colgrpname:
                    if colgrp['name'] in [self.mapper_name, 'tagsampler']:
                        newcolgrps[0]['count'] += colgrp['count']
                    else:
                        newcolgrps.append(colgrp)
                    break
        colpos = 0
        for colgrp in newcolgrps:
            colgrp['lastcol'] = colpos + colgrp['count']
            colpos = colgrp['lastcol']
        colgrpnames = [v['name'] for v in colgrps if v['name'] not in priority_colgroupnames]
        colgrpnames.sort()
        for colgrpname in colgrpnames:
            for colgrp in colgrps:
                if colgrp['name'] == colgrpname:
                    colgrp['lastcol'] = colpos + colgrp['count']
                    newcolgrps.append(colgrp)
                    colpos += colgrp['count']
                    break
        # re-orders columns.
        self.colname_conversion[level] = {}
        new_columns = []
        for colgrp in newcolgrps:
            colgrpname = colgrp['name']
            for col in columns:
                [grpname, oricolname] = col['col_name'].split('__')
                if grpname in [self.mapper_name, 'tagsampler']:
                    newcolname = 'base__' + col['col_name'].split('__')[1]
                    self.colname_conversion[level][newcolname] = col['col_name']
                    col['col_name'] = newcolname
                    new_columns.append(col)
                elif grpname == colgrpname:
                    new_columns.append(col)
        self.colinfo[level] = {'colgroups': newcolgrps, 'columns': new_columns}

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
        self.confs = None
        if parsed_args.confs is not None:
            confs = parsed_args.confs.lstrip('\'').rstrip('\'').replace("'", '"')
            self.confs = json.loads(confs)
            if 'filter' in self.confs:
                self.filter = self.confs['filter']
            else:
                self.filter = None
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
        await self.cf.loadfilter(filter=self.filter, filterpath=self.filterpath, filtername=self.filtername, filterstring=self.filterstring)

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
