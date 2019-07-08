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
        s = ''
        #TODO unify this to a single if/else on self.test
        if self.test == 'multicategory':
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
        if self.negate:
            s = 'not('+s+')'
        return s

class FilterGroup(object):
    def __init__(self, d):
        self.operator = d.get('operator', 'and')
        self.negate = d.get('negate',False)
        self.rules = []
        for rule in d.get('rules',[]):
            if 'operator' in rule:
                self.rules.append(FilterGroup(rule))
            else:
                self.rules.append(FilterColumn(rule,self.operator))
        # Backwards compatability, may remove later
        self.rules += [FilterGroup(x) for x in d.get('groups',[])]
        self.rules += [FilterColumn(x, self.operator) for x in d.get('columns', [])]

    def get_sql(self):
        clauses = []
        for operand in self.rules:
            clause = operand.get_sql()
            if clause:
                clauses.append(clause)
        s = ''
        if clauses:
            s += '('
            sql_operator = ' ' + self.operator + ' '
            s += sql_operator.join(clauses)
            s += ')'
            if self.negate:
                s = 'not'+s
        return s

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
        where = ''
        if self.filter is not None and level in self.filter:
            criteria = self.filter[level]
            main_group = FilterGroup(criteria)
            sql = main_group.get_sql()
            if sql:
                where = 'where '+sql
        return where

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

    async def get_gene_row (self, hugo):
        q = 'select * from gene where base__hugo=?'
        await self.cursor.execute(q, [hugo])
        row = await self.cursor.fetchone()
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

    async def make_filtered_sample_table (self):
        q = 'drop table if exists fsample'
        print(q) #debug
        await self.cursor.execute(q)
        try: #TODO: always have these fields
            req = self.filter['sample']['require']
            rej = self.filter['sample']['reject']
        except:
            req = []
            rej = []
        q = 'create table fsample as select distinct base__uid from sample'
        if req:
            q += ' where base__sample_id in ({})'.format(
                ', '.join(['"{}"'.format(sid) for sid in req])
            )
        # for s in req:
        #     q += ' union select base__uid from sample where base__sample_id="{}"'.format(s)
        for s in rej:
           q += ' except select base__uid from sample where base__sample_id="{}"'.format(s)
        print(q) #debug
        await self.cursor.execute(q)
        await self.conn.commit()

    async def make_filtered_uid_table (self):
        t = time.time()
        await self.make_filtered_sample_table()
        await self.make_gene_list_table()
        await self.conn.commit()
        level = 'variant'
        vtable = level
        vftable = level + '_filtered'
        q = 'drop table if exists ' + vftable
        await self.cursor.execute(q)
        where = self.getwhere(level)
        q = 'create table {} as select t.base__uid from {} as t'.format(vftable, level)
        q += ' join fsample as s on t.base__uid=s.base__uid'
        if 'genes' in self.filter and len(self.filter['genes']) > 0:
            q += ' join gene_list as g on t.base__hugo=g.base__hugo'
        q += ' '+where
        print(q) #debug
        await self.cursor.execute(q)
        self.conn.commit()
        t = time.time() - t
    
    async def make_gene_list_table (self):
        tname = 'gene_list'
        q = 'drop table if exists {}'.format(tname)
        print(q) #debug
        await self.cursor.execute(q)
        q = 'create table {} (base__hugo text)'.format(tname)
        print(q) #debug
        await self.cursor.execute(q)
        if 'genes' in self.filter:
            tdata = [(hugo,) for hugo in self.filter['genes']]
        else:
            tdata = []
        if tdata:
            q = 'insert into {} (base__hugo) values (?)'.format(tname)
            print(q) #debug
            await self.cursor.executemany(q, tdata)
        else:
            q = 'insert into {} select base__hugo from gene'.format(tname)
            print(q) #debug
            await self.cursor.execute(q)
        await self.conn.commit()
    
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
