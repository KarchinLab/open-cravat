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
from cravat.util import write_log_msg
import subprocess
import re
import logging
import time
import re
import aiosqlite
import types
from cravat import constants
import asyncio
import importlib
import cravat.cravat_class
from types import SimpleNamespace
import nest_asyncio

nest_asyncio.apply()
import sys
import oyaml as yaml

if sys.platform == "win32" and sys.version_info >= (3, 8):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class CravatReport:
    def __init__(self, *inargs, **inkwargs):
        self.cf = None
        self.filtertable = "filter"
        self.colinfo = {}
        self.colnos = {}
        self.newcolnos = {}
        self.var_added_cols = []
        self.summarizing_modules = []
        self.columngroups = {}
        self.column_subs = {}
        self.column_sub_allow_partial_match = {}
        self.colname_conversion = {}
        self.warning_msgs = []
        self.colnames_to_display = {}
        self.colnos_to_display = {}
        self.display_select_columns = {}
        self.extracted_cols = {}
        self.conn = None
        self.levels_to_write = None
        self.parse_cmd_args(inargs, inkwargs)
        global parser
        for ag in parser._action_groups:
            if ag.title == "optional arguments":
                for a in ag._actions:
                    if "-t" in a.option_strings:
                        ag._actions.remove(a)
        self._setup_logger()

    def parse_cmd_args(self, inargs, inkwargs):
        parsed_args = cravat.util.get_args(parser, inargs, inkwargs)
        self.parsed_args = parsed_args
        if parsed_args.md is not None:
            constants.custom_modules_dir = parsed_args.md
        self.dbpath = parsed_args.dbpath
        self.filterpath = parsed_args.filterpath
        self.filtername = parsed_args.filtername
        self.filterstring = parsed_args.filterstring
        self.filtersql = parsed_args.filtersql
        self.filter = parsed_args.filter
        self.confs = {}
        if parsed_args.output_dir is not None:
            self.output_dir = parsed_args.output_dir
        else:
            self.output_dir = os.path.dirname(self.dbpath)
        self.savepath = parsed_args.savepath
        if self.savepath is not None and os.path.dirname(self.savepath) == "":
            self.savepath = os.path.join(self.output_dir, self.savepath)
        self.confpath = parsed_args.confpath
        self.conf = ConfigLoader(job_conf_path=self.confpath)
        self.module_name = parsed_args.module_name
        if self.module_name in self.conf._all:
            self.confs.update(self.conf._all[self.module_name])
        if self.conf is not None:
            self.module_conf = self.conf.get_module_conf(self.module_name)
        else:
            self.module_conf = None
        if hasattr(parsed_args, "reporttypes"):
            self.report_types = parsed_args.reporttypes
        if hasattr(parsed_args, "conf") and parsed_args.conf is not None:
            self.confs.update(parsed_args.conf)
        if parsed_args.confs is not None:
            confs = parsed_args.confs.lstrip("'").rstrip("'").replace("'", '"')
            if self.confs is None:
                self.confs = json.loads(confs)
            else:
                self.confs.update(json.loads(confs))
        # Chooses filter.
        if self.filter is None:
            if self.confs is not None and "filter" in self.confs:
                self.filter = self.confs["filter"]
            local = au.mic.get_local()
            if (
                self.filter is None
                and self.filterpath is None
                and self.filtername is None
                and self.filterstring is None
                and parsed_args.package is not None
                and parsed_args.package in local
                and "filter" in local[parsed_args.package].conf
            ):
                self.filter = local[parsed_args.package].conf["filter"]
        self.output_basename = os.path.basename(self.dbpath)[:-7]
        status_fname = "{}.status.json".format(self.output_basename)
        self.status_fpath = os.path.join(self.output_dir, status_fname)
        self.nogenelevelonvariantlevel = parsed_args.nogenelevelonvariantlevel
        if parsed_args.inputfiles is None and parsed_args.dbpath is not None:
            db = sqlite3.connect(parsed_args.dbpath)
            c = db.cursor()
            q = 'select colval from info where colkey="_input_paths"'
            c.execute(q)
            r = c.fetchone()
            if r is not None:
                parsed_args.inputfiles = []
                s = r[0]
                if " " in s:
                    s = s.replace("'", '"')
                s = s.replace("\\", "\\\\\\\\")
                s = json.loads(s)
                for k in s:
                    input_path = s[k]
                    parsed_args.inputfiles.append(input_path)
            c.close()
            db.close()
        if hasattr(parsed_args, "status_writer"):
            self.status_writer = parsed_args.status_writer
        else:
            self.status_writer = None
        self.concise_report = parsed_args.concise_report
        self.extract_columns_multilevel = self.get_standardized_module_option(
            self.confs.get("extract-columns", {})
        )
        self.args = parsed_args

    def should_write_level(self, level):
        if self.levels_to_write is None:
            return True
        elif level in self.levels_to_write:
            return True
        else:
            return False

    async def prep(self):
        try:
            await self.connect_db()
            await self.load_filter()
        except Exception as e:
            if hasattr(self, "cf"):
                await self.cf.close_db()
            if not hasattr(e, "notraceback") or e.notraceback != True:
                import traceback
                traceback.print_exc()
                self.logger.error(e)
            else:
                if hasattr(self, "logger"):
                    write_log_msg(self.logger, e)
            e.handled = True
            raise

    def _setup_logger(self):
        if hasattr(self, "no_log") and self.no_log:
            return
        try:
            self.logger = logging.getLogger("cravat." + self.module_name)
        except Exception as e:
            self._log_exception(e)
        self.error_logger = logging.getLogger("error." + self.module_name)
        self.unique_excs = []

    async def get_db_conn(self):
        if self.dbpath is None:
            return None
        if self.conn is None:
            self.conn = await aiosqlite.connect(self.dbpath)
        return self.conn

    async def exec_db(self, func, *args, **kwargs):
        conn = await self.get_db_conn()
        cursor = await conn.cursor()
        try:
            ret = await func(*args, conn=conn, cursor=cursor, **kwargs)
        except:
            await cursor.close()
            raise
        await cursor.close()
        return ret

    def _log_exception(self, e, halt=True):
        if halt:
            raise e
        else:
            if self.logger:
                self.logger.exception(e)

    async def getjson(self, level):
        ret = None
        if await self.exec_db(self.table_exists, level) == False:
            return ret
        for row in await self.cf.exec_db(self.cf.getiterator, level):
            row = self.substitute_val(level, row)
            return json.dumps(row)

    def substitute_val(self, level, row):
        for sub in self.column_subs.get(level, []):
            value = row[sub.index]
            if value is None or value == "":
                continue
            if (
                level == "variant"
                and sub.module == "base"
                and sub.col == "all_mappings"
            ):
                mappings = json.loads(row[sub.index])
                for gene in mappings:
                    for i in range(len(mappings[gene])):
                        sos = mappings[gene][i][2].split(",")
                        sos = [sub.subs.get(so, so) for so in sos]
                        mappings[gene][i][2] = ",".join(sos)
                value = json.dumps(mappings)
            elif level == "gene" and sub.module == "base" and sub.col == "all_so":
                vals = []
                for i, so_count in enumerate(value.split(",")):
                    so = so_count[:3]
                    so = sub.subs.get(so, so)
                    so_count = so + so_count[3:]
                    vals.append(so_count)
                value = ",".join(vals)
            else:
                value = sub.subs.get(value, value)
            row[sub.index] = value
        return row

    def process_datarow(self, args):
        datarow = args[0]
        should_skip_some_cols = args[1]
        level = args[2]
        gene_summary_datas = args[3]
        if datarow is None:
            return None
        datarow = list(datarow)
        if should_skip_some_cols:
            datarow = [
                datarow[colno]
                for colno in range(num_total_cols)
                if colno not in colnos_to_skip
            ]
        if level == "variant":
            # adds gene level data to variant level.
            if self.nogenelevelonvariantlevel == False and hugo_present:
                hugo = datarow[self.colnos["variant"]["base__hugo"]]
                loop = asyncio.get_event_loop()
                future = asyncio.ensure_future(self.cf.get_gene_row(hugo), loop)
                generow = future.result()
                if generow is None:
                    datarow.extend([None for i in range(len(self.var_added_cols))])
                else:
                    datarow.extend(
                        [
                            generow[self.colnos["gene"][colname]]
                            for colname in self.var_added_cols
                        ]
                    )
        elif level == "gene":
            # adds summary data to gene level.
            hugo = datarow[0]
            for mi, _, _ in self.summarizing_modules:
                module_name = mi.name
                [gene_summary_data, cols] = gene_summary_datas[module_name]
                if (
                    hugo in gene_summary_data
                    and gene_summary_data[hugo] is not None
                    and len(gene_summary_data[hugo]) == len(cols)
                ):
                    datarow.extend(
                        [gene_summary_data[hugo][col["name"]] for col in cols]
                    )
                else:
                    datarow.extend([None for v in cols])
        # re-orders data row.
        new_datarow = []
        colnos = self.colnos[level]
        for colname in [col["col_name"] for col in self.colinfo[level]["columns"]]:
            if colname in self.colname_conversion[level]:
                newcolname = self.colname_conversion[level][colname]
                if newcolname in colnos:
                    colno = colnos[newcolname]
                else:
                    self.logger.info(
                        "column name does not exist in data: {}".format(colname)
                    )
                    continue
            else:
                colno = colnos[colname]
            value = datarow[colno]
            new_datarow.append(value)
        # does report substitution.
        new_datarow = self.substitute_val(level, new_datarow)
        if hasattr(self, "keep_json_all_mapping") == False and level == "variant":
            colno = self.colnos["variant"]["base__all_mappings"]
            all_map = json.loads(new_datarow[colno])
            newvals = []
            for hugo in all_map:
                for maprow in all_map[hugo]:
                    [protid, protchange, so, transcript, rnachange] = maprow
                    if protid == None:
                        protid = "(na)"
                    if protchange == None:
                        protchange = "(na)"
                    if rnachange == None:
                        rnachange = "(na)"
                    newval = (
                        transcript
                        + ":"
                        + hugo
                        + ":"
                        + protid
                        + ":"
                        + so
                        + ":"
                        + protchange
                        + ":"
                        + rnachange
                    )
                    newvals.append(newval)
            newvals.sort()
            newcell = "; ".join(newvals)
            new_datarow[colno] = newcell
        return new_datarow

    def get_extracted_header_columns(self, level):
        cols = []
        for col in self.colinfo[level]["columns"]:
            if col["col_name"] in self.colnames_to_display[level]:
                cols.append(col)
        return cols

    async def run_level(self, level):
        ret = await self.exec_db(self.table_exists, level)
        if ret == False:
            return
        if self.should_write_level(level) == False:
            return
        gene_summary_datas = {}
        if level == "variant":
            await self.cf.exec_db(self.cf.make_filtered_uid_table)
        elif level == "gene":
            await self.cf.exec_db(self.cf.make_filtered_hugo_table)
            for mi, o, cols in self.summarizing_modules:
                if hasattr(o, "build_gene_collection"):
                    msg = "Obsolete module [{}] for gene level summarization. Update the module to get correct gene level summarization.".format(
                        mi.name
                    )
                    self.warning_msgs.append(msg)
                    if self.args.silent == False:
                        print("===Warning: {}".format(msg))
                    gene_summary_data = {}
                else:
                    gene_summary_data = await o.get_gene_summary_data(self.cf)
                gene_summary_datas[mi.name] = [gene_summary_data, cols]
                for col in cols:
                    if "category" in col and col["category"] in ["single", "multi"]:
                        for i in range(len(self.colinfo[level]["columns"])):
                            colinfo_col = self.colinfo[level]["columns"][i]
                            if mi.name in ["hg38", "tagsampler"]:
                                grp_name = "base"
                            else:
                                grp_name = mi.name
                            if colinfo_col["col_name"] == grp_name + "__" + col["name"]:
                                break
                        cats = []
                        for hugo in gene_summary_data:
                            val = gene_summary_data[hugo][col["name"]]
                            if len(colinfo_col["reportsub"]) > 0:
                                if val in colinfo_col["reportsub"]:
                                    val = colinfo_col["reportsub"][val]
                            if val not in cats:
                                cats.append(val)
                        self.colinfo[level]["columns"][i]["col_cats"] = cats
        self.write_preface(level)
        self.extracted_cols[level] = self.get_extracted_header_columns(level)
        self.write_header(level)
        if level == "variant":
            hugo_present = "base__hugo" in self.colnos["variant"]
        datacols, datarows = await self.cf.exec_db(self.cf.get_filtered_iterator, level)
        num_total_cols = len(datacols)
        colnos_to_skip = []
        if level == "gene":
            for colno in range(len(datacols)):
                if datacols[colno] in constants.legacy_gene_level_cols_to_skip:
                    colnos_to_skip.append(colno)
        should_skip_some_cols = len(colnos_to_skip) > 0
        if level == "variant" and self.args.separatesample:
            write_variant_sample_separately = True
            sample_newcolno = self.newcolnos["variant"]["base__samples"]
        else:
            write_variant_sample_separately = False
        colnos = self.colnos[level]
        all_mappings_newcolno = self.newcolnos["variant"]["base__all_mappings"]
        cols = self.colinfo[level]["columns"]
        json_colnos = []
        for i in range(len(cols)):
            col = cols[i]
            if col["table"] == True:
                json_colnos.append(i)
        for datarow in datarows:
            if datarow is None:
                continue
            datarow = list(datarow)
            if should_skip_some_cols:
                datarow = [
                    datarow[colno]
                    for colno in range(num_total_cols)
                    if colno not in colnos_to_skip
                ]
            if level == "variant":
                # adds gene level data to variant level.
                if self.nogenelevelonvariantlevel == False and hugo_present:
                    hugo = datarow[self.colnos["variant"]["base__hugo"]]
                    generow = await self.cf.get_gene_row(hugo)
                    if generow is None:
                        datarow.extend([None for i in range(len(self.var_added_cols))])
                    else:
                        datarow.extend(
                            [
                                generow[self.colnos["gene"][colname]]
                                for colname in self.var_added_cols
                            ]
                        )
            elif level == "gene":
                # adds summary data to gene level.
                hugo = datarow[0]
                for mi, _, _ in self.summarizing_modules:
                    module_name = mi.name
                    [gene_summary_data, cols] = gene_summary_datas[module_name]
                    if (
                        hugo in gene_summary_data
                        and gene_summary_data[hugo] is not None
                        and len(gene_summary_data[hugo]) == len(cols)
                    ):
                        datarow.extend(
                            [gene_summary_data[hugo][col["name"]] for col in cols]
                        )
                    else:
                        datarow.extend([None for v in cols])
            # re-orders data row.
            new_datarow = []
            for colname in [col["col_name"] for col in self.colinfo[level]["columns"]]:
                if colname in self.colname_conversion[level]:
                    oldcolname = self.colname_conversion[level][colname]
                    if oldcolname in colnos:
                        colno = colnos[oldcolname]
                    else:
                        self.logger.info(
                            "column name does not exist in data: {}".format(oldcolname)
                        )
                        continue
                else:
                    colno = colnos[colname]
                value = datarow[colno]
                new_datarow.append(value)
            # does report substitution.
            new_datarow = self.substitute_val(level, new_datarow)
            if hasattr(self, "keep_json_all_mapping") == False and level == "variant":
                all_map = json.loads(new_datarow[all_mappings_newcolno])
                newvals = []
                for hugo in all_map:
                    for maprow in all_map[hugo]:
                        [protid, protchange, so, transcript, rnachange] = maprow
                        if protid == None:
                            protid = "(na)"
                        if protchange == None:
                            protchange = "(na)"
                        if rnachange == None:
                            rnachange = "(na)"
                        newval = (
                            transcript
                            + ":"
                            + hugo
                            + ":"
                            + protid
                            + ":"
                            + so
                            + ":"
                            + protchange
                            + ":"
                            + rnachange
                        )
                        newvals.append(newval)
                newvals.sort()
                newcell = "; ".join(newvals)
                new_datarow[all_mappings_newcolno] = newcell
            if write_variant_sample_separately:
                samples = new_datarow[sample_newcolno]
                if samples is not None:
                    samples = samples.split(";")
                    for sample in samples:
                        sample_datarow = new_datarow
                        sample_datarow[sample_newcolno] = sample
                        self.write_table_row(self.get_extracted_row(sample_datarow))
                else:
                    self.write_table_row(self.get_extracted_row(new_datarow))
            else:
                self.write_table_row(self.get_extracted_row(new_datarow))

    async def store_mapper(self, conn=None, cursor=None):
        # conn = await self.get_db_conn()
        # cursor = await conn.cursor()
        q = 'select colval from info where colkey="_mapper"'
        await cursor.execute(q)
        r = await cursor.fetchone()
        if r is None:
            self.mapper_name = "hg38"
        else:
            self.mapper_name = r[0].split(":")[0]
        # await cursor.close()
        # await conn.close()

    async def run(self, tab="all"):
        try:
            start_time = time.time()
            if not (hasattr(self, "no_log") and self.no_log):
                self.logger.info(
                    "started: %s" % time.asctime(time.localtime(start_time))
                )
                if self.cf.filter:
                    s = f"filter:\n{yaml.dump(self.filter)}"
                    self.logger.info(s)
            if self.module_conf is not None and self.status_writer is not None:
                if self.parsed_args.do_not_change_status == False:
                    self.status_writer.queue_status_update(
                        "status",
                        "Started {} ({})".format(
                            self.module_conf["title"], self.module_name
                        ),
                    )
            if self.setup() == False:
                await self.close_db()
                return
            if tab == "all":
                for level in await self.cf.exec_db(self.cf.get_result_levels):
                    self.level = level
                    if await self.exec_db(self.table_exists, level):
                        await self.exec_db(self.make_col_info, level)
                for level in await self.cf.exec_db(self.cf.get_result_levels):
                    self.level = level
                    if await self.exec_db(self.table_exists, level):
                        await self.run_level(level)
            else:
                if tab in ["variant", "gene"]:
                    for level in ["variant", "gene"]:
                        if await self.exec_db(self.table_exists, level):
                            await self.exec_db(self.make_col_info, level)
                else:
                    await self.exec_db(self.make_col_info, tab)
                self.level = level
                await self.run_level(tab)
            await self.close_db()
            if self.module_conf is not None and self.status_writer is not None:
                if self.parsed_args.do_not_change_status == False:
                    self.status_writer.queue_status_update(
                        "status",
                        "Finished {} ({})".format(
                            self.module_conf["title"], self.module_name
                        ),
                    )
            end_time = time.time()
            if not (hasattr(self, "no_log") and self.no_log):
                self.logger.info(
                    "finished: {0}".format(time.asctime(time.localtime(end_time)))
                )
                run_time = end_time - start_time
                self.logger.info("runtime: {0:0.3f}".format(run_time))
            ret = self.end()
        except:
            await self.close_db()
            if self.module_conf is not None and self.status_writer is not None:
                if self.parsed_args.do_not_change_status == False:
                    self.status_writer.queue_status_update(
                        "status",
                        "Failed {} ({})".format(
                            self.module_conf["title"], self.module_name
                        ),
                    )
            end_time = time.time()
            if not (hasattr(self, "no_log") and self.no_log):
                self.logger.info(
                    "finished: {0}".format(time.asctime(time.localtime(end_time)))
                )
                run_time = end_time - start_time
                self.logger.info("runtime: {0:0.3f}".format(run_time))
            raise
        return ret

    async def get_variant_colinfo(self):
        self.setup()
        level = "variant"
        if await self.exec_db(self.table_exists, level):
            await self.exec_db(self.make_col_info, level)
        level = "gene"
        if await self.exec_db(self.table_exists, level):
            await self.exec_db(self.make_col_info, level)
        return self.colinfo

    def setup(self):
        pass

    def end(self):
        pass

    def write_preface(self, level):
        pass

    def write_header(self, level):
        pass

    def write_table_row(self, row):
        pass

    def get_extracted_row(self, row):
        if self.display_select_columns[self.level]:
            filtered_row = [row[colno] for colno in self.colnos_to_display[self.level]]
        else:
            filtered_row = row
        return filtered_row

    def add_conditional_to_colnames_to_display(self, level, column, module_name):
        col_name = column["col_name"]
        if (
            level in self.extract_columns_multilevel
            and len(self.extract_columns_multilevel[level]) > 0
        ):
            if col_name in self.extract_columns_multilevel[level]:
                incl = True
            else:
                incl = False
        elif self.concise_report:
            if "col_hidden" in column and column["col_hidden"] == True:
                incl = False
            else:
                incl = True
        else:
            incl = True
        if incl and col_name not in self.colnames_to_display[level]:
            if module_name == self.mapper_name:
                self.colnames_to_display[level].append(
                    col_name.replace(module_name + "__", "base__")
                )
            elif module_name == "tagsampler":
                self.colnames_to_display[level].append(
                    col_name.replace(module_name + "__", "base__")
                )
            else:
                self.colnames_to_display[level].append(col_name)

    async def make_col_info(self, level, conn=None, cursor=None):
        self.colnames_to_display[level] = []
        await self.exec_db(self.store_mapper)
        cravat_conf = self.conf.get_cravat_conf()
        if "report_module_order" in cravat_conf:
            priority_colgroupnames = cravat_conf["report_module_order"]
        else:
            priority_colgroupnames = ["base", "hg38", "hg19", "hg18", "tagsampler"]
        # level-specific column groups
        self.columngroups[level] = []
        sql = "select name, displayname from " + level + "_annotator"
        await cursor.execute(sql)
        rows = await cursor.fetchall()
        for row in rows:
            (name, displayname) = row
            self.columngroups[level].append(
                {"name": name, "displayname": displayname, "count": 0}
            )
        # level-specific column names
        header_table = level + "_header"
        coldefs = []
        sql = "select col_def from " + header_table
        await cursor.execute(sql)
        for row in await cursor.fetchall():
            coljson = row[0]
            coldef = ColumnDefinition({})
            coldef.from_json(coljson)
            coldefs.append(coldef)
        columns = []
        self.colnos[level] = {}
        colcount = 0
        # level-specific column details
        for coldef in coldefs:
            self.colnos[level][coldef.name] = colcount
            colcount += 1
            if coldef.category in ["single", "multi"] and len(coldef.categories) == 0:
                sql = "select distinct {} from {}".format(coldef.name, level)
                await cursor.execute(sql)
                rs = await cursor.fetchall()
                for r in rs:
                    coldef.categories.append(r[0])
            [colgrpname, _] = coldef.name.split("__")
            column = coldef.get_colinfo()
            columns.append(column)
            self.add_conditional_to_colnames_to_display(level, column, colgrpname)
            for columngroup in self.columngroups[level]:
                if columngroup["name"] == colgrpname:
                    columngroup["count"] += 1
        # adds gene level columns to variant level.
        if (
            self.nogenelevelonvariantlevel == False
            and level == "variant"
            and await self.exec_db(self.table_exists, "gene")
        ):
            modules_to_add = []
            q = "select name from gene_annotator"
            await cursor.execute(q)
            gene_annotators = [v[0] for v in await cursor.fetchall()]
            modules_to_add = [m for m in gene_annotators if m != "base"]
            for module in modules_to_add:
                cols = []
                q = 'select col_def from gene_header where col_name like "{}__%"'.format(
                    module
                )
                await cursor.execute(q)
                rs = await cursor.fetchall()
                for r in rs:
                    cd = ColumnDefinition({})
                    cd.from_json(r[0])
                    cols.append(cd)
                q = 'select displayname from gene_annotator where name="{}"'.format(
                    module
                )
                await cursor.execute(q)
                r = await cursor.fetchone()
                displayname = r[0]
                self.columngroups[level].append(
                    {"name": module, "displayname": displayname, "count": len(cols)}
                )
                for coldef in cols:
                    self.colnos[level][coldef.name] = colcount
                    colcount += 1
                    if (
                        coldef.category in ["category", "multicategory"]
                        and len(coldef.categories) == 0
                    ):
                        sql = "select distinct {} from {}".format(coldef.name, level)
                        await cursor.execute(sql)
                        rs = await cursor.fetchall()
                        for r in rs:
                            coldef.categories.append(r[0])
                    column = coldef.get_colinfo()
                    columns.append(column)
                    self.add_conditional_to_colnames_to_display(level, column, module)
                    self.var_added_cols.append(coldef.name)
        # Gene level summary columns
        if level == "gene":
            q = "select name from variant_annotator"
            await cursor.execute(q)
            done_var_annotators = [v[0] for v in await cursor.fetchall()]
            self.summarizing_modules = []
            local_modules = au.get_local_module_infos_of_type("annotator")
            local_modules.update(au.get_local_module_infos_of_type("postaggregator"))
            summarizer_module_names = []
            for module_name in done_var_annotators:
                if module_name in [
                    "base",
                    "hg19",
                    "hg18",
                    "extra_vcf_info",
                    "extra_variant_info",
                ]:
                    continue
                if module_name not in local_modules:
                    if self.args.silent == False and module_name != 'original_input':
                        print(
                            "            [{}] module does not exist in the system. Gene level summary for this module is skipped.".format(
                                module_name
                            )
                        )
                    continue
                module = local_modules[module_name]
                if "can_summarize_by_gene" in module.conf:
                    summarizer_module_names.append(module_name)
            local_modules[self.mapper_name] = au.get_local_module_info(self.mapper_name)
            summarizer_module_names = [self.mapper_name] + summarizer_module_names
            for module_name in summarizer_module_names:
                mi = local_modules[module_name]
                sys.path = sys.path + [os.path.dirname(mi.script_path)]
                if module_name in done_var_annotators:
                    annot_cls = util.load_class(mi.script_path, "CravatAnnotator")
                elif module_name == self.mapper_name:
                    annot_cls = util.load_class(mi.script_path, "Mapper")
                cmd = {
                    "script_path": mi.script_path,
                    "input_file": "__dummy__",
                    "output_dir": self.output_dir,
                }
                annot = annot_cls(cmd)
                cols = mi.conf["gene_summary_output_columns"]
                columngroup = {
                    "name": mi.name,
                    "displayname": mi.title,
                    "count": len(cols),
                }
                self.columngroups[level].append(columngroup)
                for col in cols:
                    coldef = ColumnDefinition(col)
                    coldef.name = columngroup["name"] + "__" + coldef.name
                    coldef.genesummary = True
                    column = coldef.get_colinfo()
                    columns.append(column)
                    self.add_conditional_to_colnames_to_display(level, column, mi.name)
                self.summarizing_modules.append([mi, annot, cols])
                for col in cols:
                    fullname = module_name + "__" + col["name"]
                    self.colnos[level][fullname] = len(self.colnos[level])
        # re-orders columns groups.
        colgrps = self.columngroups[level]
        newcolgrps = []
        for priority_colgrpname in priority_colgroupnames:
            for colgrp in colgrps:
                if colgrp["name"] == priority_colgrpname:
                    if colgrp["name"] in [self.mapper_name, "tagsampler"]:
                        newcolgrps[0]["count"] += colgrp["count"]
                    else:
                        newcolgrps.append(colgrp)
                    break
        colpos = 0
        for colgrp in newcolgrps:
            colgrp["lastcol"] = colpos + colgrp["count"]
            colpos = colgrp["lastcol"]
        colgrpnames = [
            v["displayname"] for v in colgrps if v["name"] not in priority_colgroupnames
        ]
        colgrpnames.sort()
        for colgrpname in colgrpnames:
            for colgrp in colgrps:
                if colgrp["displayname"] == colgrpname:
                    colgrp["lastcol"] = colpos + colgrp["count"]
                    newcolgrps.append(colgrp)
                    colpos += colgrp["count"]
                    break
        # re-orders columns.
        self.colname_conversion[level] = {}
        new_columns = []
        self.newcolnos[level] = {}
        newcolno = 0
        new_colnames_to_display = []
        for colgrp in newcolgrps:
            colgrpname = colgrp["name"]
            for col in columns:
                colname = col["col_name"]
                [grpname, _] = colname.split("__")
                if colgrpname == "base" and grpname in [self.mapper_name, "tagsampler"]:
                    newcolname = "base__" + colname.split("__")[1]
                    self.colname_conversion[level][newcolname] = colname
                    col["col_name"] = newcolname
                    new_columns.append(col)
                    self.newcolnos[level][newcolname] = newcolno
                    if newcolname in self.colnames_to_display[level]:
                        new_colnames_to_display.append(newcolname)
                elif grpname == colgrpname:
                    new_columns.append(col)
                    self.newcolnos[level][colname] = newcolno
                    if colname in self.colnames_to_display[level]:
                        new_colnames_to_display.append(colname)
                else:
                    continue
                newcolno += 1
        self.colinfo[level] = {"colgroups": newcolgrps, "columns": new_columns}
        self.colnames_to_display[level] = new_colnames_to_display
        # report substitution
        if level in ["variant", "gene"]:
            reportsubtable = level + "_reportsub"
            if await self.exec_db(self.table_exists, reportsubtable):
                q = "select * from {}".format(reportsubtable)
                await cursor.execute(q)
                reportsub = {r[0]: json.loads(r[1]) for r in await cursor.fetchall()}
                self.column_subs[level] = []
                for i, column in enumerate(new_columns):
                    module, col = column["col_name"].split("__")
                    if module == self.mapper_name:
                        module = "base"
                    if module in reportsub and col in reportsub[module]:
                        self.column_subs[level].append(
                            SimpleNamespace(
                                module=module,
                                col=col,
                                index=i,
                                subs=reportsub[module][col],
                            )
                        )
                        new_columns[i]["reportsub"] = reportsub[module][col]
        # display_select_columns
        if (
            level in self.extract_columns_multilevel
            and len(self.extract_columns_multilevel[level]) > 0
        ) or self.concise_report:
            self.display_select_columns[level] = True
        else:
            self.display_select_columns[level] = False
        # column numbers to display
        colno = 0
        self.colnos_to_display[level] = []
        for colgroup in self.colinfo[level]["colgroups"]:
            count = colgroup["count"]
            if count == 0:
                continue
            for col in self.colinfo[level]["columns"][colno : colno + count]:
                module_col_name = col["col_name"]
                if module_col_name in self.colnames_to_display[level]:
                    include_col = True
                else:
                    include_col = False
                if include_col:
                    self.colnos_to_display[level].append(colno)
                colno += 1

    def get_standardized_module_option(self, v):
        tv = type(v)
        if tv == str:
            if ":" in v:
                v0 = {}
                for v1 in v.split("."):
                    if ":" in v1:
                        v1toks = v1.split(":")
                        if len(v1toks) == 2:
                            level = v1toks[0]
                            v2s = v1toks[1].split(",")
                            v0[level] = v2s
                v = v0
            elif "," in v:
                v = [val for val in v.split(",") if val != ""]
        if v == "true":
            v = True
        elif v == "false":
            v = False
        return v

    async def connect_db(self, dbpath=None):
        if dbpath != None:
            self.dbpath = dbpath
        if self.dbpath == None:
            sys.stderr.write("Provide a path to aggregator output")
            exit()
        if os.path.exists(self.dbpath) == False:
            sys.stderr.write(self.dbpath + " does not exist.")
            exit()

    async def close_db(self):
        if hasattr(self, "conn") and self.conn is not None:
            await self.conn.close()
            self.conn = None
        if self.cf is not None:
            await self.cf.close_db()
            self.cf = None

    async def load_filter(self):
        self.cf = await CravatFilter.create(dbpath=self.dbpath)
        await self.cf.exec_db(
            self.cf.loadfilter,
            filter=self.filter,
            filterpath=self.filterpath,
            filtername=self.filtername,
            filterstring=self.filterstring,
            filtersql=self.filtersql,
            includesample=self.args.includesample,
            excludesample=self.args.excludesample
        )

    async def table_exists(self, tablename, conn=None, cursor=None):
        sql = (
            "select name from sqlite_master where "
            + 'type="table" and name="'
            + tablename
            + '"'
        )
        await cursor.execute(sql)
        row = await cursor.fetchone()
        if row == None:
            ret = False
        else:
            ret = True
        return ret


def clean_args(cmd_args):
    if len(cmd_args[0]) == 0:
        cmd_args = cmd_args[1:]
    if cmd_args[0].endswith("oc") or cmd_args[0].endswith("oc.py"):
        cmd_args = cmd_args[1:]
        if cmd_args[0] == "report":
            cmd_args = cmd_args[1:]
    elif cmd_args[0] == "report":
        cmd_args = cmd_args[1:]
    elif cmd_args[0].endswith("cravat-report"):
        cmd_args = cmd_args[1:]
    elif cmd_args[0].endswith(".py"):
        cmd_args = cmd_args[1:]
    return cmd_args


def run_reporter(*inargs, **inkwargs):
    args = cravat.util.get_args(parser, inargs, inkwargs)
    global au
    dbpath = args.dbpath
    # Check if exists
    if not os.path.exists(dbpath):
        exit(f"{dbpath} not found")
    # Check if database
    try:
        with sqlite3.connect(dbpath) as db:
            db.execute("select * from info")
    except:
        exit(f"{dbpath} is not an OC database")
    compatible_version, db_version, oc_version = util.is_compatible_version(dbpath)
    if not compatible_version:
        if args.silent == False:
            print(
                f"DB version {db_version} of {dbpath} is not compatible with the current OpenCRAVAT ({oc_version})."
            )
            print(
                f'Consider running "oc util update-result {dbpath}" and running "oc gui {dbpath}" again.'
            )
        return
    report_types = args.reporttypes
    if args.md is not None:
        constants.custom_modules_dir = args.md
    local = au.mic.get_local()
    if len(report_types) == 0:
        if args.package is not None and args.package in local:
            package_conf = local[args.package].conf
            if "run" in package_conf and "reports" in package_conf["run"]:
                report_types = package_conf["run"]["reports"]
    if hasattr(args, "output_dir") and args.output_dir is not None:
        output_dir = args.output_dir
    else:
        output_dir = os.path.dirname(dbpath)
    if hasattr(args, "savepath") and args.savepath is None:
        run_name = os.path.basename(dbpath).rstrip("sqlite").rstrip(".")
        args.savepath = os.path.join(output_dir, run_name)
    else:
        savedir = os.path.dirname(args.savepath)
        if savedir != "":
            output_dir = savedir
    module_options = {}
    if args.module_option is not None:
        for opt_str in args.module_option:
            toks = opt_str.split("=")
            if len(toks) != 2:
                if not args.silent:
                    print(
                        "Ignoring invalid module option {opt_str}. module-option should be module_name.key=value."
                    )
                continue
            k = toks[0]
            if k.count(".") != 1:
                if not args.silent:
                    print(
                        "Ignoring invalid module option {opt_str}. module-option should be module_name.key=value."
                    )
                continue
            [module_name, key] = k.split(".")
            if module_name not in module_options:
                module_options[module_name] = {}
            v = toks[1]
            module_options[module_name][key] = v
    del args.module_option
    loop = asyncio.get_event_loop()
    response = {}
    for report_type in report_types:
        module_info = au.get_local_module_info(report_type + "reporter")
        if module_info is None:
            if args.silent == False:
                print(f"Report module for {report_type} does not exist. Skipping...")
            continue
        if args.silent == False:
            print(f"Generating {report_type} report... ", end="", flush=True)
        module_name = module_info.name
        spec = importlib.util.spec_from_file_location(
            module_name, module_info.script_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        args.module_name = module_name
        args.do_not_change_status = True
        if module_name in module_options:
            args.conf = module_options[module_name]
        reporter = module.Reporter(args)
        response_t = None
        try:
            loop.run_until_complete(reporter.prep())
            response_t = loop.run_until_complete(reporter.run())
            output_fns = None
            if args.silent == False:
                if type(response_t) == list:
                    output_fns = " ".join(response_t)
                else:
                    output_fns = response_t
                if output_fns is not None:
                    print(f"report created: {output_fns}")
        except Exception as e:
            if hasattr(reporter, "cf"):
                loop.run_until_complete(reporter.cf.close_db())
            if hasattr(e, "handled") and e.handled == True:
                if not hasattr(e, "notraceback") or e.notraceback != True:
                    import traceback
                    traceback.print_exc()
                else:
                    if hasattr(reporter, "logger"):
                        write_log_msg(self.logger, e)
            if args.silent == False:
                print("report generation failed for {} report.".format(report_type))
            response_t = None
        response[report_type] = response_t
    if len(report_types) == 1 and len(response) == 1:
        return response[list(response.keys())[0]]
    else:
        return response


def cravat_report_entrypoint():
    global parser
    clean_args(sys.argv)  # Unclear what this does. Does it edit sys.argv?
    parsed_args = parser.parse_args(sys.argv[1:])
    run_reporter(parsed_args)


parser = argparse.ArgumentParser(epilog="dbpath must be the first argument.")
parser.add_argument("dbpath", help="Path to aggregator output")
parser.add_argument(
    "-t",
    dest="reporttypes",
    nargs="+",
    default=[],
    help="report types",
)
parser.add_argument("-f", dest="filterpath", default=None, help="Path to filter file")
parser.add_argument("--filter", default=None, help=argparse.SUPPRESS)
parser.add_argument("--filtersql", default=None, help="Filter SQL")
parser.add_argument(
    "-F",
    dest="filtername",
    default=None,
    help="Name of filter (stored in aggregator output)",
)
parser.add_argument(
    "--filterstring", dest="filterstring", default=None, help=argparse.SUPPRESS
)
parser.add_argument("-s", dest="savepath", default=None, help="Path to save file")
parser.add_argument("-c", dest="confpath", help="path to a conf file")
parser.add_argument(
    "--module-name", dest="module_name", default=None, help="report module name"
)
parser.add_argument(
    "--nogenelevelonvariantlevel",
    dest="nogenelevelonvariantlevel",
    action="store_true",
    default=False,
    help="Use this option to prevent gene level result from being added to variant level result.",
)
parser.add_argument("--confs", dest="confs", default="{}", help="Configuration string")
parser.add_argument(
    "--inputfiles",
    nargs="+",
    dest="inputfiles",
    default=None,
    help="Original input file path",
)
parser.add_argument(
    "--separatesample",
    dest="separatesample",
    action="store_true",
    default=False,
    help="Write each variant-sample pair on a separate line",
)
parser.add_argument(
    "-d", dest="output_dir", default=None, help="directory for output files"
)
parser.add_argument(
    "--do-not-change-status",
    dest="do_not_change_status",
    action="store_true",
    default=False,
    help="Job status in status.json will not be changed",
)
parser.add_argument(
    "--silent",
    dest="silent",
    action="store_true",
    default=False,
    help="Suppress output to STDOUT",
)
parser.add_argument(
    "--system-option",
    dest="system_option",
    nargs="*",
    help="System option in key=value syntax. For example, --system-option modules_dir=/home/user/open-cravat/modules",
)
parser.add_argument(
    "--module-option",
    dest="module_option",
    nargs="*",
    help="Module-specific option in module_name.key=value syntax. For example, --module-option vcfreporter.type=separate",
)
parser.add_argument(
    "--concise-report",
    dest="concise_report",
    action="store_true",
    default=False,
    help="Generate concise report with default columns defined by annotation modules",
)
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
parser.add_argument("--package", help="Use filters and report types in a package")
parser.add_argument(
    "--md", 
    default=None, 
    help="Specify the root directory of OpenCRAVAT modules (annotators, etc)"
)
parser.set_defaults(func=run_reporter)
