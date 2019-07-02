#!/usr/bin/env python3
import argparse
import os
import sys
import oyaml as yaml
import aiosqlite3
import json
import re
import time

class FilterColumn(object):

    test2sql = {
        'equals': '==',
        'lessThanEq': '<=',
        'lessThan': '<',
        'greaterThanEq': '>=',
        'greaterThan': '>',
        'hasData': 'is not null',
        'noData': 'is null',
        'stringContains': 'like',
        'stringStarts': 'like', # Deprecated. Eliminate later
        'stringEnds': 'like', # Deprecated. Eliminate later
        'between': 'between',
        'in': 'in',
        'select': 'in',
    }

    def __init__(self, d, parent_operator):
        self.column = d['column']
        self.test = d['test']
        self.value = d.get('value')
        self.negate = d.get('negate', False)
        self.parent_operator = parent_operator

    def get_sql(self):
        incexc = 'include'
        s = ''
        if self.column == 'tagsampler__samples':
            if type(self.value) == list:
                s = 's.base__sample_id="' + self.value[0] + '"'
                for v in self.value[1:]:
                    s += ' or s.base__sample_id="' + v + '"'
            elif type(self.value) == str:
                s = 's.base__sample_id="' + self.value + '"'
            if self.negate and self.parent_operator == 'AND':
                incexc = 'exclude'
        elif self.column == 'tagsampler__tags':
            if type(self.value) == list:
                s = 'm.base__tags="' + self.value[0] + '"'
                for v in self.value[1:]:
                    s += ' or m.base__tags="' + v + '"'
            elif type(self.value) == str:
                s = 'm.base__tags="' + self.value + '"'
            if self.negate and self.parent_operator == 'AND':
                incexc = 'exclude'
        elif self.test == 'multicategory':
            s = 't.{} like "%{}%"'.format(self.column, self.value[0])
            for v in self.value[1:]:
                s += ' or t.{} like "%{}%"'.format(self.column, v)
        else:
            s = 't.{col} {opr}'.format(col=self.column, opr=self.test2sql[self.test])
            sql_val = None
            if self.test == 'equals':
                if type(self.value) is list:
                    v = self.value[0]
                    if type(v) is str:
                        sql_val = '"' + v + '"'
                    else:
                        sql_val = str(v)
                    for v in self.value[1:]:
                        if type(v) is str:
                            v = '"' + v + '"'
                        else:
                            v = str(v)
                        sql_val += ' OR {} == {}'.format(self.column, v)
                else:
                    if type(self.value) is str:
                        sql_val = '"{}"'.format(self.value)
                    else:
                        sql_val = str(self.value)
            elif self.test == 'stringContains':
                sql_val = '"%{}%"'.format(self.value)
            elif self.test == 'stringStarts':
                sql_val = '"{}%"'.format(self.value)
            elif self.test == 'stringEnds':
                sql_val = '"%{}"'.format(self.value)
            elif self.test in ('select','in'):
                str_toks = []
                for val in self.value:
                    if type(val) == str:
                        str_toks.append('"{}"'.format(val))
                    else:
                        str_toks.append(str(val))
                sql_val = '(' + ', '.join(str_toks) + ')'
            elif self.test == 'between':
                sql_val = '{} and {}'.format(self.value[0], self.value[1])
            elif self.test in ('lessThan','lessThanEq','greaterThan','greaterThanEq'):
                sql_val = str(self.value)
            if sql_val:
                s += ' '+sql_val
        if self.negate and incexc != 'exclude':
            s = 'not('+s+')'
        return s, incexc

class FilterGroup(object):
    def __init__(self, d):
        self.operator = d.get('operator', 'and')
        self.negate = d.get('negate',False)
        self.groups = [FilterGroup(x) for x in d.get('groups',[])]
        self.columns = [FilterColumn(x, self.operator) for x in d.get('columns', [])]

    def get_sql(self):
        all_operands = self.groups + self.columns
        if len(all_operands) == 0:
            return '', ''
        include_sqls = []
        exclude_sqls = []
        for operand in all_operands:
            if type(operand) == FilterColumn:
                sql, incexc = operand.get_sql()
                if sql == '':
                    continue
                if incexc == 'include':
                    include_sqls.append(sql)
                elif incexc == 'exclude':
                    exclude_sqls.append(sql)
            elif type(operand) == FilterGroup:
                g_inc_sqls, g_exc_sqls = operand.get_sql()
                if g_inc_sqls != '':
                    include_sqls.append(g_inc_sqls)
                if g_exc_sqls != '':
                    exclude_sqls.append(g_exc_sqls)
        s = '('
        sql_operator = ' ' + self.operator + ' '
        s += sql_operator.join([sql for sql in include_sqls])
        s += ')'
        if self.negate:
            s = 'not'+s
        if s == '()' or s == 'not()':
            s = ''
        include_sql = s
        s = '('
        sql_operator = ' ' + self.operator + ' '
        s += sql_operator.join([sql for sql in exclude_sqls])
        s += ')'
        if self.negate:
            s = 'not'+s
        if s == '()' or s == 'not()':
            s = ''
        exclude_sql = s
        return include_sql, exclude_sql

class CravatFilter ():
    
    @classmethod
    async def create (cls, dbpath=None, filterpath=None, filtername=None,
            filterstring=None, filter=None, mode="sub"):
        self = CravatFilter(dbpath=dbpath, filterpath=filterpath, filtername=filtername,
            filterstring=filterstring, filter=filter, mode=mode)
        await self.second_init()
        return self

    def __init__ (self, dbpath=None, filterpath=None, filtername=None, 
            filterstring=None, filter=None, mode='sub'):
        self.mode = mode
        if self.mode == 'main':
            self.stdout = True
        else:
            self.stdout = False
        self.dbpath = dbpath
        self.filterpath = None
        self.cmd = None
        self.level = None
        self.filter = None
        self.savefiltername = None
        self.filtername = None
        self.filterstring = None
        self.conn = None
        self.cursor = None
        if filter != None:
            self.filter = filter
        else:
            if filterstring != None:
                self.filterstring = filterstring
            elif filtername != None:
                self.filtername = filtername
            elif filterpath != None:
                self.filterpath = filterpath
        self.filtertable = 'filter'
        self.generows = {}

    async def second_init (self):
        if self.mode == 'sub':
            if self.dbpath != None:
                await self.connect_db()
            await self.loadfilter()

    async def run (self, cmd=None, args=None, dbpath=None, filter=None):
        if args != None:
            self.parse_args(args)
        if cmd != None:
            self.cmd = cmd

        if dbpath != None:
            self.dbpath = dbpath
            await self.connect_db()
        elif self.dbpath != None and self.cursor == None:
            await self.connect_db()

        # Loads filter.
        if filter != None:
            self.filter = filter
        elif (self.filtername != None or self.filterpath != None or 
            self.filterstring != None) and self.filter == None:
            self.loadfilter()

        ret = None
        if self.cursor != None and self.filter != None:
            if self.cmd == 'uidpipe':
                ret = self.run_level_based_func(self.getuiditerator)
            elif self.cmd == 'count':
                ret = self.run_level_based_func(self.getcount)
            elif self.cmd == 'rows':
                ret = self.run_level_based_func(self.getrows)
            elif self.cmd == 'pipe':
                ret = self.run_level_based_func(self.getiterator)
        elif self.cursor != None and self.cmd == 'list':
            ret = self.listfilter()

        # Saves filter.
        if self.filter != None:
            if self.cmd == 'save' or self.savefiltername != None:
                ret = self.savefilter()

        return ret

    def run_level_based_func (self, cmd):
        ret = {}
        if self.level != None:
            ret[self.level] = cmd(level=self.level)
        else:
            levels = ['variant', 'gene']
            ret = {}
            for level in levels:
                ret_onelevel = cmd(level=level)
                ret[level] = ret_onelevel
        return ret

    def parse_args (self, args):
        parser = argparse.ArgumentParser()
        parser.add_argument('-d',
            dest='dbpath',
            required=True,
            help='Path of a result database file (.sqlite)')
        parser.add_argument('-f',
            dest='filterpath',
            help='Path of a filtering criteria file')
        parser.add_argument('-F',
            dest='filtername',
            help='Name of the filter to apply (saved in the database)')
        parser.add_argument('--filterstring',
            dest='filterstring',
            default=None,
            help='Filter in JSON')
        parser.add_argument('-l',
            dest='level',
            default=None,
            choices=['variant', 'gene'],
            help='Analysis level to filter')
        parser.add_argument('-s',
            dest='savefiltername',
            help='Name to save the filter as (in the database)')
        if self.mode == 'main':
            parser.add_argument('command', 
            choices=['uidpipe', 'count', 'rows', 'pipe', 'save', 'list'],
            help='Command')

        parsed_args = parser.parse_args(args)
        self.dbpath = parsed_args.dbpath
        self.filterpath = parsed_args.filterpath
        self.level = parsed_args.level
        if self.mode == 'main':
            self.cmd = parsed_args.command
        self.savefiltername = parsed_args.savefiltername
        self.filtername = parsed_args.filtername
        self.filterstring = parsed_args.filterstring

    async def connect_db (self, dbpath=None):
        if dbpath != None:
            self.dbpath = dbpath
        self.conn = await aiosqlite3.connect(self.dbpath)
        self.cursor = await self.conn.cursor()
        self.conn.create_function('regexp', 2, regexp)

    async def close_db (self):
        await self.cursor.close()
        self.conn.close()

    async def create_filtertable (self):
        if self.cursor == None:
            return
        sql = 'create table ' + self.filtertable + ' (name text, criteria text)'
        await self.cursor.execute(sql)
        self.conn.commit()

    async def filtertable_exists (self):
        sql = 'select name from sqlite_master where ' +\
            'type="table" and name="' + self.filtertable + '"'
        await self.cursor.execute(sql)
        for row in await self.cursor.fetchone():
            if row == None:
                ret = False
            else:
                ret = True
        return ret

    async def loadfilter (self, filterpath=None, filtername=None, 
            filterstring=None, filter=None):
        if filterpath != None:
            self.filterpath = filterpath
        if filtername != None:
            self.filtername = filtername
        if filterstring != None:
            self.filterstring = filterstring
        if filter != None:
            self.filter = filter
        if self.filterstring != None:
            self.filterstring = self.filterstring.replace("'", '"')
            self.filter = json.loads(self.filterstring)
        elif self.filtername != None and self.filtertable_exists():
            await self.cursor.execute('select criteria from ' + self.filtertable +
                ' where name="' + self.filtername + '"')
            criteria = await self.cursor.fetchone()
            if criteria != None:
                self.filter = json.loads(criteria[0])
        elif self.filterpath != None and os.path.exists(self.filterpath):
            with open(self.filterpath) as f:
                ftype = self.filterpath.split('.')[-1]
                if ftype in ['yml','yaml']:
                    self.filter = yaml.load(f)
                elif ftype in ['json']:
                    self.filter = json.load(f)

    async def delete_filtered_uid_table (self):
        await self.cursor.execute('pragma synchronous=0')
        q = 'drop table if exists variant_filtered'
        await self.cursor.execute(q)
        q = 'drop table if exists gene_filtered'
        await self.cursor.execute(q)
        self.conn.commit()
        await self.cursor.execute('pragma synchronous=2')

    def getwhere (self, level):
        if self.filter == None:
            sample_needed = False
            tag_needed = False
            include_where = ''
            exclude_where = ''
        else:
            if level not in self.filter:
                sample_needed = False
                tag_needed = False
                include_where = ''
                exclude_where = ''
            else:
                criteria = self.filter[level]
                main_group = FilterGroup(criteria)
                include_sql, exclude_sql = main_group.get_sql()
                if include_sql == '':
                    include_where = ''
                else:
                    include_where = ' where ' + include_sql
                if exclude_sql == '':
                    exclude_where = ''
                else:
                    exclude_where = ' where ' + exclude_sql
                sample_needed = 's.base__sample_id' in include_where or 's.base__sample_id' in exclude_where
                tag_needed = 'm.base__tags' in include_where or 'm.base__tags' in exclude_where
        return (sample_needed, tag_needed, include_where, exclude_where)

    def getvariantcount (self):
        return self.getcount('variant')

    def getgenecount (self):
        return self.getcount('gene')

    async def getcount (self, level='variant'):
        level = 'variant'
        await self.make_filtered_uid_table()
        ftable = level + '_filtered'
        q = 'select count(*) from ' + ftable
        await self.cursor.execute(q)
        for row in await self.cursor.fetchone():
            n = row
        if self.stdout == True:
            print('#' + level)
            print(str(n))
        return n

    def getvariantrows (self):
        return self.getrows('variant')

    def getgenerows (self):
        return self.getrows('gene')

    async def getrows (self, level='variant'):
        (sample_needed, tag_needed, include_where, exclude_where) = self.getwhere(level)
        q = 'select *  from ' + level + include_where + ' except select * from ' + level + exclude_where
        await self.cursor.execute(q)
        ret = [list(v) for v in await self.cursor.fetchall()]
        if self.stdout == True:
            print('#' + level)
            for row in ret:
                print('\t'.join([str(v) for v in row]))
        return ret

    async def make_generows (self):
        t = time.time()
        q = 'select * from gene'
        await self.cursor.execute(q)
        rows = await self.cursor.fetchall()
        self.generows = {}
        for row in rows:
            hugo = row[0]
            self.generows[hugo] = row

    async def get_gene_row (self, hugo):
        if hugo is None:
            return None
        if bool(self.generows) == False:
            await self.make_generows()
        row = self.generows[hugo]
        return row

    def getvariantiterator (self):
        return self.getiterator('variant')

    def getgeneiterator (self):
        return self.getiterator('gene')

    async def getiterator (self, level='variant'):
        (sample_needed, tag_needed, include_where, exclude_where) = self.getwhere(level)
        sql = 'select *  from ' + level + include_where + ' except select * from ' + level + exclude_where
        await self.cursor.execute(sql)
        it = await self.cursor.fetchall()
        return it

    async def get_filtered_iterator (self, level='variant'):
        if level == 'variant':
            kcol = 'base__uid'
            ftable = 'variant_filtered'
        elif level == 'gene':
            kcol = 'base__hugo'
            ftable = 'gene_filtered'
        elif level == 'sample':
            kcol = 'base__uid'
            ftable = 'variant_filtered'
        elif level == 'mapping':
            kcol = 'base__uid'
            ftable = 'variant_filtered'
        table = level
        if level in ['variant', 'gene', 'sample', 'mapping']:
            sql = 'select t.* from ' + table + ' as t inner join ' + ftable +\
                ' as f on t.' + kcol + '=f.' + kcol
        await self.cursor.execute(sql)
        it = await self.cursor.fetchall()
        return it

    async def make_filtered_uid_table (self):
        t = time.time()
        await self.cursor.execute('pragma synchronous=0')
        level = 'variant'
        vtable = level
        vftable = level + '_filtered'
        q = 'drop table if exists ' + vftable
        await self.cursor.execute(q)
        (sample_needed, tag_needed, include_where, exclude_where) = self.getwhere(level)
        q = 'create table {} as select t.base__uid from {} as t'.format(vftable, level) 
        if sample_needed:
            q += ', sample as s '
        if tag_needed:
            q += ', mapping as m '
        q += include_where
        if sample_needed:
            q += ' and s.base__uid=t.base__uid'
        if tag_needed:
            q += ' and m.base__uid=t.base__uid'
        if exclude_where != '':
            q += ' except select t.base__uid from {} as t'.format(level)
            if sample_needed:
                q += ', sample as s '
            if tag_needed:
                q += ', mapping as m '
            q += exclude_where
            if sample_needed:
                q += ' and s.base__uid=t.base__uid'
            if tag_needed:
                q += ' and m.base__uid=t.base__uid'
        await self.cursor.execute(q)
        t = time.time() - t
        await self.cursor.execute('pragma synchronous=2')

    async def make_filtered_hugo_table (self):
        await self.cursor.execute('pragma synchronous=0')
        level = 'gene'
        vtable = 'variant'
        vftable = vtable + '_filtered'
        gftable = level + '_filtered'
        q = 'drop table if exists ' + gftable
        await self.cursor.execute(q)
        q = 'create table ' + gftable +\
            ' as select distinct v.base__hugo from ' + vtable + ' as v'\
            ' inner join ' + vftable + ' as vf on vf.base__uid=v.base__uid'\
            ' where v.base__hugo is not null'
        await self.cursor.execute(q)
        await self.cursor.execute('pragma synchronous=2')

    async def savefilter (self, name=None):
        if self.cursor == None or self.filter == None:
            return

        if name == None:
            if self.savefiltername != None:
                name = self.savefiltername
            else:
                name = 'default'

        # Creates filter save table if not exists.
        await self.cursor.execute('select name from sqlite_master where ' +
            'type="table" and name="' + self.filtertable + '"')
        for ret in await self.cursor.fetchone():
            if ret == None:
                await self.cursor.execute('create table ' + self.filtertable +
                    ' (name text unique, criteria text)')

        # Saves the filter.
        filterstr = json.dumps(self.filter)
        sql = 'insert or replace into ' + self.filtertable +\
            ' values ("' + name + '", \'' + filterstr + '\')'
        await self.cursor.execute(sql)
        self.conn.commit()

    async def listfilter (self, name=None):
        if name == None:
            if self.savefiltername != None:
                name = self.savefiltername
            else:
                name = 'default'

        # Creates filter save table if not exists.
        await self.cursor.execute('select name from sqlite_master where ' +
            'type="table" and name="' + self.filtertable + '"')
        for ret in await self.cursor.fetchone():
            if ret == None:
                await self.cursor.execute('create table ' + self.filtertable +
                    ' (name text, criteria text)')

        sql = 'select name, criteria from ' + self.filtertable
        await self.cursor.execute(sql)
        ret = {}
        for row in await self.cursor.fetchall():
            name = row[0]
            criteria = json.loads(row[1])
            ret[name] = criteria
            if self.stdout:
                print('#' + name)
                for level in criteria:
                    print('    ' + level + ':')
                    for column in criteria[level]:
                        print('        ' + column + ': ' + 
                              criteria[level][column])

        return ret

    def addvariantfilter (self, column, condition):
        self.addfilter(column, condition, 'variant')

    def addgenefilter (self, column, condition):
        self.addcriterion(column, condition, 'gene')

    def addfilter (self, column, condition, level='variant'):
        if self.filter == None:
            self.filter = {}
        if level not in self.filter:
            self.filter[level] = {}
        self.filter[level][column] = condition

    def removevariantfilter (self, column):
        self.removefilter(column, 'variant')

    def removegenefilter (self, column):
        self.removefilter(column, 'gene')

    def removefilter (self, column, level='variant'):
        if self.filter == None:
            return
        if level in self.filter and column in self.filter[level]:
            del self.filter[level][column]

    async def table_exists (self, table):
        sql = 'select name from sqlite_master where type="table" and ' +\
            'name="' + table + '"'
        await self.cursor.execute(sql)
        for row in await self.cursor.fetchone():
            if row == None:
                return False
            else:
                return True

    async def get_variant_iterator_filtered_uids_cols (self, cols):
        q = 'select ' + ','.join(cols) + ' from variant as v ' +\
            'inner join variant_filtered as f on v.base__uid=f.base__uid'
        await self.cursor.execute(q)
        rows = await self.cursor.fetchall()
        for row in rows:
            d = {}
            for i in range(len(row)):
                d[cols[i].split('__')[1]] = row[i]
            yield d

    async def get_result_levels (self):
        q = 'select name from sqlite_master where type="table" and ' +\
            'name like "%_header"'
        await self.cursor.execute(q)
        table_names = []
        for row in await self.cursor.fetchall():
            table_names.append(row[0].replace('_header', ''))
        return table_names

def regexp (y, x, search=re.search):
    if x is None:
        return 0
    return 1 if search(y, x) else 0

def main ():
    cv = CravatFilter.create(mode='main')
    cv.run(args=sys.argv[1:])
