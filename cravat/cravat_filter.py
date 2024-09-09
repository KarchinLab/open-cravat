#!/usr/bin/env python3
import argparse
import os
import sys
import oyaml as yaml
import json
import re
import time
import asyncio
import platform
import sys
import sqlite3
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
    def create(
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
        self.second_init()
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

    def get_module_version_in_job(self, module_name, conn=None, cursor=None):
        if conn is None or cursor is None:
            return None
        q = 'select colval from info where colkey="_annotators"'
        cursor.execute(q)
        anno_vers = cursor.fetchone()
        if anno_vers is None:
            return None
        version = None
        for anno_ver in anno_vers[0].split(","):
            [mname, ver] = anno_ver.split(":")
            if mname == module_name:
                version = ver
                break
        return version

    def exec_db(self, func, *args, **kwargs):
        conn = self.get_db_conn()
        cursor = conn.cursor()
        ret = func(*args, conn=conn, cursor=cursor, **kwargs)
        cursor.close()
        return ret

    def second_init(self):
        if self.mode == "sub":
            if self.dbpath != None:
                self.connect_db()
            self.exec_db(self.loadfilter)

    def run(self, cmd=None, args=None, dbpath=None, filter=None):
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
            self.exec_db(self.loadfilter)

        ret = None
        if self.dbpath is not None:
            if self.cmd == "count":
                ret = self.run_level_based_func(self.exec_db(self.getcount))
            elif self.cmd == "rows":
                ret = self.run_level_based_func(self.exec_db(self.getrows))
            elif self.cmd == "pipe":
                ret = self.run_level_based_func(self.exec_db(self.getiterator))
        elif self.dbpath is not None and self.cmd == "list":
            ret = self.exec_db(self.listfilter)

        # Saves filter.
        if self.filter != None:
            if self.cmd == "save" or self.savefiltername != None:
                ret = self.exec_db(self.savefilter)

        return ret

    def run_level_based_func(self, cmd):
        ret = {}
        if self.level != None:
            ret[self.level] = cmd(level=self.level)
        else:
            levels = ["variant", "gene"]
            ret = {}
            for level in levels:
                ret_onelevel = cmd(level=level)
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

    def get_db_conn(self):
        if self.dbpath is None:
            return None
        if self.conn is None:
            self.conn = sqlite3.connect(self.dbpath)
        return self.conn

    def connect_db(self, dbpath=None):
        if dbpath != None:
            self.dbpath = dbpath
        conn = self.get_db_conn()
        conn.create_function("regexp", 2, regexp)
        self.exec_db(self.set_aliases)

    def set_aliases(self, conn=None, cursor=None):
        self.table_aliases = {"variant": "v", "gene": "g"}
        self.column_prefixes = {}
        q = "pragma table_info(variant)"
        cursor.execute(q)
        self.column_prefixes.update(
            {row[1]: self.table_aliases["variant"] for row in cursor.fetchall()}
        )
        q = "pragma table_info(gene)"
        cursor.execute(q)
        self.column_prefixes.update(
            {row[1]: self.table_aliases["gene"] for row in cursor.fetchall()}
        )

    def close_db(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def create_filtertable(self, conn=None, cursor=None):
        if conn is None:
            return
        sql = "create table " + self.filtertable + " (name text, criteria text)"
        cursor.execute(sql)
        conn.commit()

    def filtertable_exists(self, conn=None, cursor=None):
        sql = f'select * from viewersetup where datatype="filter" and name="{self.filtername}"'
        cursor.execute(sql)
        row = cursor.fetchone()
        if row == None:
            ret = False
        else:
            ret = True
        return ret

    def loadfilter(
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
        filter_table_present = self.exec_db(self.filtertable_exists)
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
            cursor.execute(
                "select viewersetup from viewersetup"
                + ' where datatype="filter" and name="'
                + self.filtername
                + '"'
            )
            criteria = cursor.fetchone()
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
        self.verify_filter(cursor)

    def verify_filter(self, cursor):
        wrong_samples = self.verify_filter_sample(cursor)
        wrong_colnames = self.verify_filter_module(cursor)
        if len(wrong_samples) > 0 or len(wrong_colnames) > 0:
            raise InvalidFilter(wrong_samples, wrong_colnames)

    def check_sample_name(self, sample_id, cursor):
        cursor.execute("select base__sample_id from sample where base__sample_id=\"" + sample_id + "\" limit 1")
        ret = cursor.fetchone()
        return ret is not None

    def verify_filter_sample(self, cursor):
        if "sample" not in self.filter:
            return []
        ft = self.filter["sample"]
        wrong_samples = set()
        if "require" in ft:
            for rq in ft["require"]:
                if self.check_sample_name(rq, cursor) == False:
                    wrong_samples.add(rq)
        if "reject" in ft:
            for rq in ft["reject"]:
                if self.check_sample_name(rq, cursor) == False:
                    wrong_samples.add(rq)
        return wrong_samples

    def col_name_exists(self, colname, cursor):
        cursor.execute("select col_def from variant_header where col_name=\"" + colname + "\" limit 1")
        ret = cursor.fetchone()
        if ret is None:
            cursor.execute("select col_def from gene_header where col_name=\"" + colname + "\" limit 1")
            ret = cursor.fetchone()
        return ret is not None

    def extract_filter_columns(self, rules, colset, cursor):
        for rule in rules:
            if "column" in rule:
                if self.col_name_exists(rule["column"], cursor) == False:
                    colset.add(rule["column"])
            elif "rules" in rule:
                self.extract_filter_columns(rule["rules"], colset, cursor)

    def verify_filter_module(self, cursor):
        if "variant" not in self.filter:
            return []
        wrong_modules = set()
        if "rules" in self.filter["variant"]:
            self.extract_filter_columns(self.filter["variant"]["rules"], wrong_modules, cursor)
        return wrong_modules

    def delete_filtered_uid_table(self, conn=None, cursor=None):
        cursor.execute("pragma synchronous=0")
        q = "drop table if exists variant_filtered"
        cursor.execute(q)
        q = "drop table if exists gene_filtered"
        cursor.execute(q)
        conn.commit()
        cursor.execute("pragma synchronous=2")

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

    def getcount(self, level="variant", conn=None, cursor=None):
        bypassfilter = not(self.filter or self.filtersql or self.includesample or self.excludesample)
        level = "variant"
        self.exec_db(self.make_filtered_uid_table)
        if bypassfilter:
            ftable = level
        else:
            ftable = level + "_filtered"
        n = self.exec_db(self.get_filtered_count, level=level)
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

    def getrows(self, level="variant", conn=None, cursor=None):
        if level != "variant":
            return
        where = self.getwhere(level)
        self.exec_db(self.make_filtered_sample_table)
        self.exec_db(self.make_gene_list_table)
        conn.commit()
        q = f"select v.* from variant as v join fsample as s on v.base__uid=s.base__uid"
        if isinstance(self.filter, dict) and len(self.filter.get("genes", [])) > 0:
            q += " join gene_list as gl on v.base__hugo=gl.base__hugo"
        if "g." in where:
            q += " join gene as g on v.base__hugo=g.base__hugo"
        cursor.execute(q)
        ret = [list(v) for v in cursor.fetchall()]
        if self.stdout == True:
            print("#" + level)
            for row in ret:
                print("\t".join([str(v) for v in row]))
        return ret

    def make_generows(self, conn=None, cursor=None):
        t = time.time()
        q = "select * from gene"
        cursor.execute(q)
        rows = cursor.fetchall()
        self.generows = {}
        for row in rows:
            hugo = row[0]
            self.generows[hugo] = row

    def get_gene_row(self, hugo):
        if hugo is None:
            return None
        if bool(self.generows) == False:
            self.exec_db(self.make_generows)
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

    def getiterator(self, level="variant", conn=None, cursor=None):
        (sample_needed, tag_needed, include_where, exclude_where) = self.getwhere(level)
        sql = (
            "select *  from "
            + level
            + include_where
            + " except select * from "
            + level
            + exclude_where
        )
        cursor.execute(sql)
        it = cursor.fetchall()
        return it

    @staticmethod
    def reaggregate_column(base_alias, meta):
        column = meta['name']
        function = meta.get('filter_reagg_function', None)
        reagg_args = meta.get('filter_reagg_function_args', [])
        reagg_source = meta.get('filter_reagg_source_column', None)

        if not function:
            return "{}.{}".format(base_alias, column)

        reagg_template = "{}({}{}) OVER (PARTITION BY {}.base__uid ORDER BY sample.base__sample_id ROWS BETWEEN UNBOUNDED PRECEDING and UNBOUNDED FOLLOWING) {}"
        quoted_args = ["'{}'".format(x) for x in reagg_args]
        formatted_args = ",{}".format(",".join(quoted_args)) if reagg_args else ""
        return reagg_template.format(function, reagg_source, formatted_args, base_alias, column)

    @staticmethod
    def level_column_definitions(cursor, level):
        cursor.execute("select col_name, col_def from {}_header".format(level))
        return {k: json.loads(v) for k, v in cursor.fetchall()}

    def make_sample_filter_group(self, cursor, sample_filter):
        sample_columns = self.level_column_definitions(cursor, 'sample')
        prefixes = {k: 'sample' for k in sample_columns.keys()}
        filter_group = FilterGroup(sample_filter)
        filter_group.add_prefixes(prefixes)
        return filter_group

    def get_filtered_iterator(self, level="variant", conn=None, cursor=None):
        sql = self.build_base_sql(cursor, level)

        if level == 'variant' and self.filter and 'samplefilter' in self.filter and len(self.filter['samplefilter']['rules']) > 0:
            sample_filter = self.filter['samplefilter']
            variant_columns = self.level_column_definitions(cursor, 'variant')

            reaggregated_columns = [self.reaggregate_column('v', meta) for col, meta in variant_columns.items()]
            sample_filters = self.build_sample_exclusions()
            filter_group = self.make_sample_filter_group(cursor, sample_filter)

            sql = """
                with base_variant as ({}),
                scoped_sample as (
                    select * 
                    from sample 
                    where 1=1
                    {}
                )
                select distinct {}
                from base_variant v
                join scoped_sample sample on sample.base__uid = v.base__uid
                where {}
            """.format(sql, sample_filters, ",".join(reaggregated_columns), filter_group.get_sql())

        cursor.execute(sql)
        cols = [v[0] for v in cursor.description]
        rows = cursor.fetchall()

        return cols, rows
    
    def get_filtered_count(self, level="variant", conn=None, cursor=None):

        if level == 'variant' and self.filter and 'samplefilter' in self.filter and len(self.filter['samplefilter']['rules']) > 0:
            sql = self.build_base_sql(cursor, level)
            sample_filter = self.filter['samplefilter']
            variant_columns = self.level_column_definitions(cursor, 'variant')

            reaggregated_columns = [self.reaggregate_column('v', meta) for col, meta in variant_columns.items()]
            sample_filters = self.build_sample_exclusions()
            filter_group = self.make_sample_filter_group(cursor, sample_filter)

            sql = """
                with base_variant as ({}),
                scoped_sample as (
                    select * 
                    from sample 
                    where 1=1
                    {}
                )
                select count(distinct v.base__uid)
                from base_variant v
                join scoped_sample sample on sample.base__uid = v.base__uid
                where {}
            """.format(sql, sample_filters, filter_group.get_sql())
        else:
            sql = self.build_base_sql(cursor, level, count=True)
        cursor.execute(sql)
        rows = cursor.fetchall()

        return rows[0][0]

    def build_sample_exclusions(self):
        # this is needed because joining back to the sample table causes
        # re-inclusion of sample data that was excluded at the variant level.
        sample_filters = ""
        req, rej = self.required_and_rejected_samples()
        if req:
            sample_filters += "and base__sample_id in ({})".format(
                ", ".join(["'{}'".format(sid) for sid in req]))
        if rej:
            sample_filters += "and base__sample_id not in ({})".format(
                ", ".join(["'{}'".format(sid) for sid in rej]))
        return sample_filters

    def build_base_sql(self, cursor, level, count=False):
        bypassfilter = not (self.filter or self.filtersql or self.includesample or self.excludesample)
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
                cursor.execute(sql)
                rs = cursor.fetchall()
                colnames = ["gene." + r[1] for r in rs if r[1] != "base__hugo"]
                sql = "select distinct variant.base__hugo, {} from variant inner join gene on variant.base__hugo==gene.base__hugo".format(
                    ", ".join(colnames)
                )
            else:
                if not count:
                    sql = "select v.* from " + table + " as v"
                else:
                    sql = "select count(v.base__uid) from " + table + " as v"
                if bypassfilter == False:
                    sql += " inner join " + ftable + " as f on v." + kcol + "=f." + kcol

        return sql

    def make_filtered_sample_table(self, conn=None, cursor=None):
        q = "drop table if exists fsample"
        cursor.execute(q)
        conn.commit()
        req, rej = self.required_and_rejected_samples()
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
            cursor.execute(q)
            conn.commit()
            return True
        else:
            return False

    def required_and_rejected_samples(self):
        sample = self.filter.get("sample", {})
        req = sample.get("require", self.includesample or [])
        rej = sample.get("reject",  self.excludesample or [])

        return req, rej

    def make_filter_where(self, conn=None, cursor=None):
        q = ""
        if len(self.filter) == 0:
            if self.includesample is not None or self.excludesample is not None:
                fsample_made = self.exec_db(self.make_filtered_sample_table)
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
            fsample_made = self.exec_db(self.make_filtered_sample_table)
            gene_list_made = self.exec_db(self.make_gene_list_table)
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

    def make_filtered_uid_table(self, conn=None, cursor=None):
        t = time.time()
        bypassfilter = not(self.filter or self.filtersql or self.includesample or self.excludesample)
        if bypassfilter == False:
            level = "variant"
            vtable = level
            vftable = level + "_filtered"
            q = "drop table if exists " + vftable
            cursor.execute(q)
            q = f"create table {vftable} as select v.base__uid from variant as v"
            if len(self.filter) == 0:
                if self.includesample is not None or self.excludesample is not None:
                    fsample_made = self.exec_db(self.make_filtered_sample_table)
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
                fsample_made = self.exec_db(self.make_filtered_sample_table)
                gene_list_made = self.exec_db(self.make_gene_list_table)
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
            cursor.execute(q)
            conn.commit()
            t = time.time() - t

    def make_gene_list_table(self, conn=None, cursor=None):
        tname = "gene_list"
        q = "drop table if exists {}".format(tname)
        cursor.execute(q)
        conn.commit()
        if isinstance(self.filter, dict) and "genes" in self.filter:
            tdata = [(hugo,) for hugo in self.filter["genes"]]
        else:
            tdata = []
        if len(tdata) > 0:
            q = "create table {} (base__hugo text)".format(tname)
            cursor.execute(q)
            q = "insert into {} (base__hugo) values (?)".format(tname)
            cursor.executemany(q, tdata)
            conn.commit()
            return True
        else:
            return False

    def make_filtered_hugo_table(self, conn=None, cursor=None):
        bypassfilter = not(self.filter or self.filtersql or self.includesample or self.excludesample)
        if bypassfilter == False:
            cursor.execute("pragma synchronous=0")
            level = "gene"
            vtable = "variant"
            vftable = vtable + "_filtered"
            gftable = level + "_filtered"
            q = "drop table if exists " + gftable
            cursor.execute(q)
            q = (
                "create table "
                + gftable
                + " as select distinct v.base__hugo from "
                + vtable
                + " as v"
                " inner join " + vftable + " as vf on vf.base__uid=v.base__uid"
                " where v.base__hugo is not null"
            )
            cursor.execute(q)
            cursor.execute("pragma synchronous=2")

    def savefilter(self, name=None, conn=None, cursor=None):
        if conn is None or self.filter is None:
            return
        if name == None:
            if self.savefiltername != None:
                name = self.savefiltername
            else:
                name = "default"
        # Creates filter save table if not exists.
        cursor.execute(
            "select name from sqlite_master where "
            + 'type="table" and name="'
            + self.filtertable
            + '"'
        )
        for ret in cursor.fetchone():
            if ret == None:
                cursor.execute(
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
        cursor.execute(sql)
        conn.commit()

    def listfilter(self, name=None, conn=None, cursor=None):
        if name == None:
            if self.savefiltername != None:
                name = self.savefiltername
            else:
                name = "default"
        # Creates filter save table if not exists.
        cursor.execute(
            "select name from sqlite_master where "
            + 'type="table" and name="'
            + self.filtertable
            + '"'
        )
        for ret in cursor.fetchone():
            if ret == None:
                cursor.execute(
                    "create table " + self.filtertable + " (name text, criteria text)"
                )
        sql = "select name, criteria from " + self.filtertable
        cursor.execute(sql)
        ret = {}
        for row in cursor.fetchall():
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

    def table_exists(self, table, conn=None, cursor=None):
        sql = (
            'select name from sqlite_master where type="table" and '
            + 'name="'
            + table
            + '"'
        )
        cursor.execute(sql)
        for row in cursor.fetchone():
            if row == None:
                return False
            else:
                return True

    def get_variant_iterator_filtered_uids_cols(
        self, cols, conn=None, cursor=None
    ):
        if cols[0] == "base__uid":
            cols[0] = "v." + cols[0]
        bypassfilter = not(self.filter or self.filtersql or self.includesample or self.excludesample)
        q = "select " + ",".join(cols) + " from variant as v"
        if bypassfilter == False:
            q += " inner join variant_filtered as f on v.base__uid=f.base__uid"
        cursor.execute(q)
        rows = cursor.fetchall()
        for row in rows:
            d = {}
            for i in range(len(row)):
                d[cols[i].split("__")[1]] = row[i]
            yield d

    def get_filtered_hugo_list(self, conn=None, cursor=None):
        bypassfilter = not(self.filter or self.filtersql or self.includesample or self.excludesample)
        if bypassfilter:
            q = "select distinct variant.base__hugo from gene, variant where gene.base__hugo==variant.base__hugo"
        else:
            q = "select base__hugo from gene_filtered"
        cursor.execute(q)
        rows = cursor.fetchall()
        hugos = [row[0] for row in rows]
        return hugos

    def get_variant_data_for_cols(self, cols, conn=None, cursor=None):
        bypassfilter = not(self.filter or self.filtersql or self.includesample or self.excludesample)
        if cols[0] == "base__uid":
            cols[0] = "v.base__uid"
        q = "select {},base__hugo from variant as v".format(",".join(cols))
        if bypassfilter == False:
            q += " inner join variant_filtered as f on v.base__uid=f.base__uid"
        if cols[0] == "v.base__uid":
            cols[0] = "base__uid"
        cursor.execute(q)
        rows = cursor.fetchall()
        return rows

    def get_variant_data_for_hugo(self, hugo, cols, conn=None, cursor=None):
        bypassfilter = not(self.filter or self.filtersql or self.includesample or self.excludesample)
        if cols[0] == "base__uid":
            cols[0] = "v.base__uid"
        q = "select {} from variant as v".format(",".join(cols))
        if bypassfilter == False:
            q += ' inner join variant_filtered as f on v.base__uid=f.base__uid and v.base__hugo="{}"'.format(
                hugo
            )
        if cols[0] == "v.base__uid":
            cols[0] = "base__uid"
        cursor.execute(q)
        rows = cursor.fetchall()
        return rows

    def get_result_levels(self, conn=None, cursor=None):
        q = (
            'select name from sqlite_master where type="table" and '
            + 'name like "%_header"'
        )
        cursor.execute(q)
        table_names = []
        for row in cursor.fetchall():
            table_names.append(row[0].replace("_header", ""))
        return table_names

    def get_stored_output_columns(self, module_name, conn=None, cursor=None):
        q = f'select col_def from variant_header where col_name like "{module_name}\\_\\_%" escape "\\"'
        cursor.execute(q)
        output_columns = []
        for row in cursor.fetchall():
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
