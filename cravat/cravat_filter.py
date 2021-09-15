#!/usr/bin/env python3
import argparse
import os
import sys
import oyaml as yaml
import aiosqlite
import json
import re
import time
import asyncio
import platform
import sys
from cravat.exceptions import InvalidFilter

if sys.platform == "win32" and sys.version_info >= (3, 8):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class FilterColumn(object):

    test2sql = {
        "equals": "==",
        "lessThanEq": "<=",
        "lessThan": "<",
        "greaterThanEq": ">=",
        "greaterThan": ">",
        "hasData": "is not null",
        "noData": "is null",
        "stringContains": "like",
        "stringStarts": "like",  # Deprecated. Eliminate later
        "stringEnds": "like",  # Deprecated. Eliminate later
        "between": "between",
        "in": "in",
        "select": "in",
    }

    def __init__(self, d, parent_operator):
        self.column = d["column"]
        if self.column == "base__numsample":
            self.column = "tagsampler__numsample"
        self.test = d["test"]
        self.value = d.get("value")
        self.negate = d.get("negate", False)
        self.parent_operator = parent_operator

    def __repr__(self):
        return f"{self.column} {self.test} {self.value}"

    def get_sql(self):
        s = ""
        # TODO unify this to a single if/else on self.test
        if self.test == "multicategory":
            s = '{} like "%{}%"'.format(self.column, self.value[0])
            for v in self.value[1:]:
                s += ' or {} like "%{}%"'.format(self.column, v)
        elif self.test in ("select", "in"):
            ss = []
            for val in self.value:
                if type(val) == str:
                    val = '"{}"'.format(val)
                else:
                    val = str(val)
                ss.append(f"({self.column} = {val})")
            s = "(" + f" or ".join(ss) + ")"
        else:
            s = "{col} {opr}".format(col=self.column, opr=self.test2sql[self.test])
            sql_val = None
            if self.test == "equals":
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
                        sql_val += " OR {} == {}".format(self.column, v)
                else:
                    if type(self.value) is str:
                        sql_val = '"{}"'.format(self.value)
                    else:
                        sql_val = str(self.value)
            elif self.test == "stringContains":
                sql_val = '"%{}%"'.format(self.value)
            elif self.test == "stringStarts":
                sql_val = '"{}%"'.format(self.value)
            elif self.test == "stringEnds":
                sql_val = '"%{}"'.format(self.value)
            elif self.test == "between":
                sql_val = "{} and {}".format(self.value[0], self.value[1])
            elif self.test in (
                "lessThan",
                "lessThanEq",
                "greaterThan",
                "greaterThanEq",
            ):
                sql_val = str(self.value)
            if sql_val:
                s += " (" + sql_val + ")"
        if self.negate:
            s = "not(" + s + ")"
        return s


class FilterGroup(object):
    def __init__(self, d):
        self.operator = d.get("operator", "and")
        self.negate = d.get("negate", False)
        self.rules = []
        for rule in d.get("rules", []):
            if "operator" in rule:
                self.rules.append(FilterGroup(rule))
            else:
                self.rules.append(FilterColumn(rule, self.operator))
        # Backwards compatability, may remove later
        self.rules += [FilterGroup(x) for x in d.get("groups", [])]
        self.rules += [FilterColumn(x, self.operator) for x in d.get("columns", [])]
        self.column_prefixes = {}

    def add_prefixes(self, prefixes):
        self.column_prefixes.update(prefixes)
        for rule in self.rules:
            if isinstance(rule, FilterGroup):
                rule.add_prefixes(prefixes)
            elif isinstance(rule, FilterColumn):
                prefix = self.column_prefixes.get(rule.column)
                if prefix is not None:
                    rule.column = prefix + "." + rule.column

    def get_sql(self):
        clauses = []
        for operand in self.rules:
            clause = operand.get_sql()
            if clause:
                clauses.append(clause)
        s = ""
        if clauses:
            s += "("
            sql_operator = " " + self.operator + " "
            s += sql_operator.join(clauses)
            s += ")"
            if self.negate:
                s = "not" + s
        return s


class CravatFilter:
    @classmethod
    async def create(
        cls,
        dbpath=None,
        filterpath=None,
        filtername=None,
        filterstring=None,
        filter=None,
        mode="sub",
        filtersql=None,
        includesample=None,
        excludesample=None
    ):
        self = CravatFilter(
            dbpath=dbpath,
            filterpath=filterpath,
            filtername=filtername,
            filterstring=filterstring,
            filter=filter,
            mode=mode,
            filtersql=filtersql,
            includesample=includesample,
            excludesample=excludesample
        )
        await self.second_init()
        return self

    def __init__(
        self,
        dbpath=None,
        filterpath=None,
        filtername=None,
        filterstring=None,
        filter=None,
        filtersql=None,
        includesample=None,
        excludesample=None,
        mode="sub",
    ):
        self.mode = mode
        if self.mode == "main":
            self.stdout = True
        else:
            self.stdout = False
        self.dbpath = dbpath
        self.conn = None
        self.filterpath = filterpath
        self.cmd = None
        self.level = None
        self.filter = filter
        self.savefiltername = None
        self.filtername = None
        self.filterstring = filterstring
        self.filtersql = filtersql
        self.includesample = includesample
        self.excludesample = excludesample
        if filter != None:
            self.filter = filter
        else:
            if filterstring != None:
                self.filterstring = filterstring
            elif filtername != None:
                self.filtername = filtername
            elif filterpath != None:
                self.filterpath = filterpath
        self.filtertable = "filter"
        self.generows = {}
        # self.open_conns = {}

    # async def close_conns (self):
    #    for conn in self.open_conns.values():
    #        await conn.close()

    async def get_module_version_in_job(self, module_name, conn=None, cursor=None):
        if conn is None or cursor is None:
            return None
        q = 'select colval from info where colkey="_annotators"'
        await cursor.execute(q)
        anno_vers = await cursor.fetchone()
        if anno_vers is None:
            return None
        version = None
        for anno_ver in anno_vers[0].split(","):
            [mname, ver] = anno_ver.split(":")
            if mname == module_name:
                version = ver
                break
        return version

    async def exec_db(self, func, *args, **kwargs):
        conn = await self.get_db_conn()
        cursor = await conn.cursor()
        ret = await func(*args, conn=conn, cursor=cursor, **kwargs)
        await cursor.close()
        return ret

    async def second_init(self):
        if self.mode == "sub":
            if self.dbpath != None:
                await self.connect_db()
            await self.exec_db(self.loadfilter)

    async def run(self, cmd=None, args=None, dbpath=None, filter=None):
        if args != None:
            self.parse_args(args)
        if cmd != None:
            self.cmd = cmd

        if dbpath != None:
            self.dbpath = dbpath

        # Loads filter.
        if filter != None:
            self.filter = filter
        elif (
            self.filtername != None
            or self.filterpath != None
            or self.filterstring != None
            or self.filtersql != None
        ) and self.filter == None:
            await self.exec_db(self.loadfilter)

        ret = None
        if self.dbpath is not None:
            if self.cmd == "count":
                ret = await self.run_level_based_func(self.exec_db(self.getcount))
            elif self.cmd == "rows":
                ret = await self.run_level_based_func(self.exec_db(self.getrows))
            elif self.cmd == "pipe":
                ret = await self.run_level_based_func(self.exec_db(self.getiterator))
        elif self.dbpath is not None and self.cmd == "list":
            ret = self.exec_db(self.listfilter)

        # Saves filter.
        if self.filter != None:
            if self.cmd == "save" or self.savefiltername != None:
                ret = self.exec_db(self.savefilter)

        return ret

    async def run_level_based_func(self, cmd):
        ret = {}
        if self.level != None:
            ret[self.level] = await cmd(level=self.level)
        else:
            levels = ["variant", "gene"]
            ret = {}
            for level in levels:
                ret_onelevel = await cmd(level=level)
                ret[level] = ret_onelevel
        return ret

    def parse_args(self, args):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-d",
            dest="dbpath",
            required=True,
            help="Path of a result database file (.sqlite)",
        )
        parser.add_argument(
            "-f", dest="filterpath", help="Path of a filtering criteria file"
        )
        parser.add_argument(
            "-F",
            dest="filtername",
            help="Name of the filter to apply (saved in the database)",
        )
        parser.add_argument(
            "--filterstring", dest="filterstring", default=None, help="Filter in JSON"
        )
        parser.add_argument(
            "-l",
            dest="level",
            default=None,
            choices=["variant", "gene"],
            help="Analysis level to filter",
        )
        parser.add_argument(
            "-s",
            dest="savefiltername",
            help="Name to save the filter as (in the database)",
        )
        parser.add_argument(
            "--filtersql", 
            dest="filtersql", 
            default=None, 
            help="Filter SQL")
        parser.add_argument(
            '--includesample',
            dest='includesample',
            nargs='+',
            default=None,
            help='Sample IDs to include',
        )
        parser.add_argument(
            '--excludesample',
            dest='excludesample',
            nargs='+',
            default=None,
            help='Sample IDs to exclude',
        )
        if self.mode == "main":
            parser.add_argument(
                "command",
                choices=["uidpipe", "count", "rows", "pipe", "save", "list"],
                help="Command",
            )

        parsed_args = parser.parse_args(args)
        self.dbpath = parsed_args.dbpath
        self.filterpath = parsed_args.filterpath
        self.level = parsed_args.level
        if self.mode == "main":
            self.cmd = parsed_args.command
        self.savefiltername = parsed_args.savefiltername
        self.filtername = parsed_args.filtername
        self.filterstring = parsed_args.filterstring
        self.filtersql = parsed_args.filtersql

    async def get_db_conn(self):
        if self.dbpath is None:
            return None
        if self.conn is None:
            self.conn = await aiosqlite.connect(self.dbpath)
        return self.conn

    async def connect_db(self, dbpath=None):
        if dbpath != None:
            self.dbpath = dbpath
        conn = await self.get_db_conn()
        await conn.create_function("regexp", 2, regexp)
        await self.exec_db(self.set_aliases)

    async def set_aliases(self, conn=None, cursor=None):
        self.table_aliases = {"variant": "v", "gene": "g"}
        self.column_prefixes = {}
        q = "pragma table_info(variant)"
        await cursor.execute(q)
        self.column_prefixes.update(
            {row[1]: self.table_aliases["variant"] for row in await cursor.fetchall()}
        )
        q = "pragma table_info(gene)"
        await cursor.execute(q)
        self.column_prefixes.update(
            {row[1]: self.table_aliases["gene"] for row in await cursor.fetchall()}
        )

    async def close_db(self):
        if self.conn is not None:
            await self.conn.close()
            self.conn = None

    async def create_filtertable(self, conn=None, cursor=None):
        if conn is None:
            return
        sql = "create table " + self.filtertable + " (name text, criteria text)"
        await cursor.execute(sql)
        await conn.commit()

    async def filtertable_exists(self, conn=None, cursor=None):
        sql = f'select * from viewersetup where datatype="filter" and name="{self.filtername}"'
        await cursor.execute(sql)
        row = await cursor.fetchone()
        if row == None:
            ret = False
        else:
            ret = True
        return ret

    async def loadfilter(
        self,
        filterpath=None,
        filtername=None,
        filterstring=None,
        filtersql=None,
        filter=None,
        includesample=None,
        excludesample=None,
        conn=None,
        cursor=None,
    ):
        if filterpath != None:
            self.filterpath = filterpath
        if filtername != None:
            self.filtername = filtername
        if filterstring != None:
            self.filterstring = filterstring
        if filtersql != None:
            self.filtersql = filtersql
        if filter != None:
            self.filter = filter
        if includesample is not None:
            self.includesample = includesample
        if excludesample is not None:
            self.excludesample = excludesample
        filter_table_present = await self.exec_db(self.filtertable_exists)
        if self.filter:
            pass
        elif self.filtersql is not None:
            if os.path.exists(self.filtersql):
                with open(self.filtersql) as f:
                    self.filtersql = "".join(f.readlines())
            self.filter = {}
        elif self.filterstring is not None:
            self.filterstring = self.filterstring.replace("'", '"')
            self.filter = json.loads(self.filterstring)
        elif self.filtername is not None and filter_table_present and cursor is not None:
            await cursor.execute(
                "select viewersetup from viewersetup"
                + ' where datatype="filter" and name="'
                + self.filtername
                + '"'
            )
            criteria = await cursor.fetchone()
            if criteria != None:
                self.filter = json.loads(criteria[0])["filterSet"]
        elif self.filterpath is not None and os.path.exists(self.filterpath):
            with open(self.filterpath) as f:
                ftype = self.filterpath.split(".")[-1]
                if ftype in ["yml", "yaml"]:
                    self.filter = yaml.safe_load(f)
                elif ftype in ["json"]:
                    self.filter = json.load(f)
        if self.filter is None:
            self.filter = {}
        await self.verify_filter(cursor)

    async def verify_filter(self, cursor):
        wrong_samples = await self.verify_filter_sample(cursor)
        wrong_colnames = await self.verify_filter_module(cursor)
        if len(wrong_samples) > 0 or len(wrong_colnames) > 0:
            raise InvalidFilter(wrong_samples, wrong_colnames)

    async def check_sample_name(self, sample_id, cursor):
        await cursor.execute("select base__sample_id from sample where base__sample_id=\"" + sample_id + "\" limit 1")
        ret = await cursor.fetchone()
        return ret is not None

    async def verify_filter_sample(self, cursor):
        if "sample" not in self.filter:
            return []
        ft = self.filter["sample"]
        wrong_samples = set()
        if "require" in ft:
            for rq in ft["require"]:
                if await self.check_sample_name(rq, cursor) == False:
                    wrong_samples.add(rq)
        if "reject" in ft:
            for rq in ft["reject"]:
                if await self.check_sample_name(rq, cursor) == False:
                    wrong_samples.add(rq)
        return wrong_samples

    async def col_name_exists(self, colname, cursor):
        await cursor.execute("select col_def from variant_header where col_name=\"" + colname + "\" limit 1")
        ret = await cursor.fetchone()
        if ret is None:
            await cursor.execute("select col_def from gene_header where col_name=\"" + colname + "\" limit 1")
            ret = await cursor.fetchone()
        return ret is not None

    async def extract_filter_columns(self, rules, colset, cursor):
        for rule in rules:
            if "column" in rule:
                if await self.col_name_exists(rule["column"], cursor) == False:
                    colset.add(rule["column"])
            elif "rules" in rule:
                await self.extract_filter_columns(rule["rules"], colset, cursor)

    async def verify_filter_module(self, cursor):
        if "variant" not in self.filter:
            return []
        wrong_modules = set()
        if "rules" in self.filter["variant"]:
            await self.extract_filter_columns(self.filter["variant"]["rules"], wrong_modules, cursor)
        return wrong_modules

    async def delete_filtered_uid_table(self, conn=None, cursor=None):
        await cursor.execute("pragma synchronous=0")
        q = "drop table if exists variant_filtered"
        await cursor.execute(q)
        q = "drop table if exists gene_filtered"
        await cursor.execute(q)
        await conn.commit()
        await cursor.execute("pragma synchronous=2")

    def getwhere(self, level):
        where = ""
        if self.filter is not None and level in self.filter:
            criteria = self.filter[level]
            main_group = FilterGroup(criteria)
            main_group.add_prefixes(self.column_prefixes)
            sql = main_group.get_sql()
            if sql:
                where = "where " + sql
        return where

    def getvariantcount(self):
        loop = asyncio.get_event_loop()
        count = loop.run_until_complete(self.exec_db(self.getcount, "variant"))
        return count

    def getgenecount(self):
        loop = asyncio.get_event_loop()
        count = loop.run_until_complete(self.exec_db(self.getcount, "gene"))
        return count

    async def getcount(self, level="variant", conn=None, cursor=None):
        bypassfilter = self.filter == {} and self.filtersql is None and self.includesample is None and self.excludesample is None
        level = "variant"
        await self.exec_db(self.make_filtered_uid_table)
        if bypassfilter:
            ftable = level
        else:
            ftable = level + "_filtered"
        q = "select count(*) from " + ftable
        await cursor.execute(q)
        for row in await cursor.fetchone():
            n = row
        if self.stdout == True:
            print("#" + level)
            print(str(n))
        return n

    def getvariantrows(self):
        loop = asyncio.get_event_loop()
        rows = loop.run_until_complete(self.exec_db(self.getrows, "variant"))
        return rows

    def getgenerows(self):
        loop = asyncio.get_event_loop()
        rows = loop.run_until_complete(self.exec_db(self.getrows, "gene"))
        return rows

    async def getrows(self, level="variant", conn=None, cursor=None):
        if level != "variant":
            return
        where = self.getwhere(level)
        await self.exec_db(self.make_filtered_sample_table)
        await self.exec_db(self.make_gene_list_table)
        await conn.commit()
        q = f"select v.* from variant as v join fsample as s on v.base__uid=s.base__uid"
        if isinstance(self.filter, dict) and len(self.filter.get("genes", [])) > 0:
            q += " join gene_list as gl on v.base__hugo=gl.base__hugo"
        if "g." in where:
            q += " join gene as g on v.base__hugo=g.base__hugo"
        await cursor.execute(q)
        ret = [list(v) for v in await cursor.fetchall()]
        if self.stdout == True:
            print("#" + level)
            for row in ret:
                print("\t".join([str(v) for v in row]))
        return ret

    async def make_generows(self, conn=None, cursor=None):
        t = time.time()
        q = "select * from gene"
        await cursor.execute(q)
        rows = await cursor.fetchall()
        self.generows = {}
        for row in rows:
            hugo = row[0]
            self.generows[hugo] = row

    async def get_gene_row(self, hugo):
        if hugo is None:
            return None
        if bool(self.generows) == False:
            await self.exec_db(self.make_generows)
        row = self.generows.get(hugo)
        return row

    def getvariantiterator(self):
        loop = asyncio.get_event_loop()
        iterator = loop.run_until_complete(self.exec_db(self.getiterator, "variant"))
        return iterator

    def getgeneiterator(self):
        loop = asyncio.get_event_loop()
        iterator = loop.run_until_complete(self.exec_db(self.getiterator, "gene"))
        return iterator

    async def getiterator(self, level="variant", conn=None, cursor=None):
        (sample_needed, tag_needed, include_where, exclude_where) = self.getwhere(level)
        sql = (
            "select *  from "
            + level
            + include_where
            + " except select * from "
            + level
            + exclude_where
        )
        await cursor.execute(sql)
        it = await cursor.fetchall()
        return it

    async def get_filtered_iterator(self, level="variant", conn=None, cursor=None):
        bypassfilter = self.filter == {} and self.filtersql is None and self.includesample is None and self.excludesample is None
        if level == "variant":
            kcol = "base__uid"
            if bypassfilter:
                ftable = "variant"
            else:
                ftable = "variant_filtered"
        elif level == "gene":
            kcol = "base__hugo"
            if bypassfilter:
                ftable = "gene"
            else:
                ftable = "gene_filtered"
        elif level == "sample":
            kcol = "base__uid"
            if bypassfilter:
                ftable = "variant"
            else:
                ftable = "variant_filtered"
        elif level == "mapping":
            kcol = "base__uid"
            if bypassfilter:
                ftable = "variant"
            else:
                ftable = "variant_filtered"
        table = level
        if level in ["variant", "gene", "sample", "mapping"]:
            if level == "gene" and bypassfilter:
                sql = "pragma table_info(gene)"
                await cursor.execute(sql)
                rs = await cursor.fetchall()
                colnames = ["gene." + r[1] for r in rs if r[1] != "base__hugo"]
                sql = "select distinct variant.base__hugo, {} from variant inner join gene on variant.base__hugo==gene.base__hugo".format(
                    ", ".join(colnames)
                )
            else:
                sql = "select v.* from " + table + " as v"
                if bypassfilter == False:
                    sql += " inner join " + ftable + " as f on v." + kcol + "=f." + kcol
        await cursor.execute(sql)
        cols = [v[0] for v in cursor.description]
        rows = await cursor.fetchall()
        return cols, rows

    async def make_filtered_sample_table(self, conn=None, cursor=None):
        q = "drop table if exists fsample"
        await cursor.execute(q)
        await conn.commit()
        req = []
        rej = []
        if "sample" in self.filter:
            if "require" in self.filter["sample"]:
                req = self.filter["sample"]["require"]
            if "reject" in self.filter["sample"]:
                rej = self.filter["sample"]["reject"]
        if self.includesample is not None:
            req = self.includesample
        if self.excludesample is not None:
            rej = self.excludesample
        if len(req) > 0 or len(rej) > 0:
            q = "create table fsample as select distinct base__uid from sample"
            if req:
                q += " where base__sample_id in ({})".format(
                    ", ".join(['"{}"'.format(sid) for sid in req])
                )
            for s in rej:
                q += ' except select base__uid from sample where base__sample_id="{}"'.format(
                    s
                )
            await cursor.execute(q)
            await conn.commit()
            return True
        else:
            return False

    async def make_filter_where(self, conn=None, cursor=None):
        q = ""
        if len(self.filter) == 0:
            if self.includesample is not None or self.excludesample is not None:
                fsample_made = await self.exec_db(self.make_filtered_sample_table)
            else:
                fsample_made = False
            if self.filtersql is not None:
                if "g." in self.filtersql:
                    q += " join gene as g on v.base__hugo=g.base__hugo"
                if "s." in self.filtersql:
                    q += " join sample as s on v.base__uid=s.base__uid"
                q += " where " + self.filtersql
            if fsample_made:
                q += " and (v.base__uid in (select base__uid from fsample))"
        else:
            where = self.getwhere("variant")
            fsample_made = await self.exec_db(self.make_filtered_sample_table)
            gene_list_made = await self.exec_db(self.make_gene_list_table)
            if gene_list_made:
                if (
                    isinstance(self.filter, dict)
                    and len(self.filter.get("genes", [])) > 0
                ):
                    q += " join gene_list as gl on v.base__hugo=gl.base__hugo"
            if "g." in where:
                q += " join gene as g on v.base__hugo=g.base__hugo"
            q += " " + where
            if fsample_made:
                q += " and (v.base__uid in (select base__uid from fsample))"
        return q

    async def make_filtered_uid_table(self, conn=None, cursor=None):
        t = time.time()
        bypassfilter = self.filter == {} and self.filtersql is None and self.includesample is None and self.excludesample is None
        if bypassfilter == False:
            level = "variant"
            vtable = level
            vftable = level + "_filtered"
            q = "drop table if exists " + vftable
            await cursor.execute(q)
            q = f"create table {vftable} as select v.base__uid from variant as v"
            if len(self.filter) == 0:
                if self.includesample is not None or self.excludesample is not None:
                    fsample_made = await self.exec_db(self.make_filtered_sample_table)
                else:
                    fsample_made = False
                if self.filtersql is not None:
                    if "g." in self.filtersql:
                        q += " join gene as g on v.base__hugo=g.base__hugo"
                    if "s." in self.filtersql:
                        q += " join sample as s on v.base__uid=s.base__uid"
                    q += " where " + self.filtersql
                if fsample_made:
                    if " where " in q:
                        q += " and "
                    else:
                        q += " where "
                    q += "(v.base__uid in (select base__uid from fsample))"
            else:
                where = self.getwhere(level)
                fsample_made = await self.exec_db(self.make_filtered_sample_table)
                gene_list_made = await self.exec_db(self.make_gene_list_table)
                if gene_list_made:
                    if (
                        isinstance(self.filter, dict)
                        and len(self.filter.get("genes", [])) > 0
                    ):
                        q += " join gene_list as gl on v.base__hugo=gl.base__hugo"
                if "g." in where:
                    q += " join gene as g on v.base__hugo=g.base__hugo"
                q += " " + where
                if fsample_made:
                    if " where " in q:
                        q += " and "
                    else:
                        q += " where "
                    q += "(v.base__uid in (select base__uid from fsample))"
            await cursor.execute(q)
            await conn.commit()
            t = time.time() - t

    async def make_gene_list_table(self, conn=None, cursor=None):
        tname = "gene_list"
        q = "drop table if exists {}".format(tname)
        await cursor.execute(q)
        await conn.commit()
        if isinstance(self.filter, dict) and "genes" in self.filter:
            tdata = [(hugo,) for hugo in self.filter["genes"]]
        else:
            tdata = []
        if len(tdata) > 0:
            q = "create table {} (base__hugo text)".format(tname)
            await cursor.execute(q)
            q = "insert into {} (base__hugo) values (?)".format(tname)
            await cursor.executemany(q, tdata)
            await conn.commit()
            return True
        else:
            return False

    async def make_filtered_hugo_table(self, conn=None, cursor=None):
        bypassfilter = self.filter == {} and self.filtersql is None and self.includesample is None and self.excludesample is None
        if bypassfilter == False:
            await cursor.execute("pragma synchronous=0")
            level = "gene"
            vtable = "variant"
            vftable = vtable + "_filtered"
            gftable = level + "_filtered"
            q = "drop table if exists " + gftable
            await cursor.execute(q)
            q = (
                "create table "
                + gftable
                + " as select distinct v.base__hugo from "
                + vtable
                + " as v"
                " inner join " + vftable + " as vf on vf.base__uid=v.base__uid"
                " where v.base__hugo is not null"
            )
            await cursor.execute(q)
            await cursor.execute("pragma synchronous=2")

    async def savefilter(self, name=None, conn=None, cursor=None):
        if conn is None or self.filter is None:
            return
        if name == None:
            if self.savefiltername != None:
                name = self.savefiltername
            else:
                name = "default"
        # Creates filter save table if not exists.
        await cursor.execute(
            "select name from sqlite_master where "
            + 'type="table" and name="'
            + self.filtertable
            + '"'
        )
        for ret in await cursor.fetchone():
            if ret == None:
                await cursor.execute(
                    "create table "
                    + self.filtertable
                    + " (name text unique, criteria text)"
                )
        # Saves the filter.
        filterstr = json.dumps(self.filter)
        sql = (
            "insert or replace into "
            + self.filtertable
            + ' values ("'
            + name
            + "\", '"
            + filterstr
            + "')"
        )
        await cursor.execute(sql)
        await conn.commit()

    async def listfilter(self, name=None, conn=None, cursor=None):
        if name == None:
            if self.savefiltername != None:
                name = self.savefiltername
            else:
                name = "default"
        # Creates filter save table if not exists.
        await cursor.execute(
            "select name from sqlite_master where "
            + 'type="table" and name="'
            + self.filtertable
            + '"'
        )
        for ret in await cursor.fetchone():
            if ret == None:
                await cursor.execute(
                    "create table " + self.filtertable + " (name text, criteria text)"
                )
        sql = "select name, criteria from " + self.filtertable
        await cursor.execute(sql)
        ret = {}
        for row in await cursor.fetchall():
            name = row[0]
            criteria = json.loads(row[1])
            ret[name] = criteria
            if self.stdout:
                print("#" + name)
                for level in criteria:
                    print("    " + level + ":")
                    for column in criteria[level]:
                        print("        " + column + ": " + criteria[level][column])
        return ret

    def addvariantfilter(self, column, condition):
        self.addfilter(column, condition, "variant")

    def addgenefilter(self, column, condition):
        self.addcriterion(column, condition, "gene")

    def addfilter(self, column, condition, level="variant"):
        if self.filter == None:
            self.filter = {}
        if level not in self.filter:
            self.filter[level] = {}
        self.filter[level][column] = condition

    def removevariantfilter(self, column):
        self.removefilter(column, "variant")

    def removegenefilter(self, column):
        self.removefilter(column, "gene")

    def removefilter(self, column, level="variant"):
        if self.filter == None:
            return
        if level in self.filter and column in self.filter[level]:
            del self.filter[level][column]

    async def table_exists(self, table, conn=None, cursor=None):
        sql = (
            'select name from sqlite_master where type="table" and '
            + 'name="'
            + table
            + '"'
        )
        await cursor.execute(sql)
        for row in await cursor.fetchone():
            if row == None:
                return False
            else:
                return True

    async def get_variant_iterator_filtered_uids_cols(
        self, cols, conn=None, cursor=None
    ):
        if cols[0] == "base__uid":
            cols[0] = "v." + cols[0]
        bypassfilter = self.filter == {} and self.filtersql is None and self.includesample is None and self.excludesample is None
        q = "select " + ",".join(cols) + " from variant as v"
        if bypassfilter == False:
            q += " inner join variant_filtered as f on v.base__uid=f.base__uid"
        await cursor.execute(q)
        rows = await cursor.fetchall()
        for row in rows:
            d = {}
            for i in range(len(row)):
                d[cols[i].split("__")[1]] = row[i]
            yield d

    async def get_filtered_hugo_list(self, conn=None, cursor=None):
        bypassfilter = self.filter == {} and self.filtersql is None and self.includesample is None and self.excludesample is None
        if bypassfilter:
            q = "select distinct variant.base__hugo from gene, variant where gene.base__hugo==variant.base__hugo"
        else:
            q = "select base__hugo from gene_filtered"
        await cursor.execute(q)
        rows = await cursor.fetchall()
        hugos = [row[0] for row in rows]
        return hugos

    async def get_variant_data_for_cols(self, cols, conn=None, cursor=None):
        bypassfilter = self.filter == {} and self.filtersql is None and self.includesample is None and self.excludesample is None
        if cols[0] == "base__uid":
            cols[0] = "v.base__uid"
        q = "select {},base__hugo from variant as v".format(",".join(cols))
        if bypassfilter == False:
            q += " inner join variant_filtered as f on v.base__uid=f.base__uid"
        if cols[0] == "v.base__uid":
            cols[0] = "base__uid"
        await cursor.execute(q)
        rows = await cursor.fetchall()
        return rows

    async def get_variant_data_for_hugo(self, hugo, cols, conn=None, cursor=None):
        bypassfilter = self.filter == {} and self.filtersql is None and self.includesample is None and self.excludesample is None
        if cols[0] == "base__uid":
            cols[0] = "v.base__uid"
        q = "select {} from variant as v".format(",".join(cols))
        if bypassfilter == False:
            q += ' inner join variant_filtered as f on v.base__uid=f.base__uid and v.base__hugo="{}"'.format(
                hugo
            )
        if cols[0] == "v.base__uid":
            cols[0] = "base__uid"
        await cursor.execute(q)
        rows = await cursor.fetchall()
        return rows

    async def get_result_levels(self, conn=None, cursor=None):
        q = (
            'select name from sqlite_master where type="table" and '
            + 'name like "%_header"'
        )
        await cursor.execute(q)
        table_names = []
        for row in await cursor.fetchall():
            table_names.append(row[0].replace("_header", ""))
        return table_names

    async def get_stored_output_columns(self, module_name, conn=None, cursor=None):
        q = f'select col_def from variant_header where col_name like "{module_name}\\_\\_%" escape "\\"'
        await cursor.execute(q)
        output_columns = []
        for row in await cursor.fetchall():
            d = json.loads(row[0])
            d["name"] = d["name"].replace(f"{module_name}__", "")
            output_columns.append(d)
        return output_columns


def regexp(y, x, search=re.search):
    if x is None:
        return 0
    return 1 if search(y, x) else 0


def main():
    loop = asyncio.new_event_loop()
    cv = loop.run_until_complete(CravatFilter.create(mode="main"))
    loop.run_until_complete(cv.run(args=sys.argv[1:]))
    loop.close()
