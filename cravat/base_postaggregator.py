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
from cravat.inout import ColumnDefinition
import json


class BasePostAggregator(object):

    cr_type_to_sql = {"string": "text", "int": "integer", "float": "real"}

    def __init__(self, cmd_args, status_writer):
        self.status_writer = status_writer
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

    def check(self):
        """
        Return boolean indicating whether main 'annotate' loop should be run.
        Should be overridden in sub-classes.
        """
        return True

    def fix_col_names(self):
        for col in self.conf["output_columns"]:
            col["name"] = self.module_name + "__" + col["name"]

    def _log_exception(self, e, halt=True):
        if halt:
            raise e
        else:
            if self.logger:
                self.logger.exception(e)

    def _define_cmd_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-n", dest="run_name", help="name of cravat run")
        parser.add_argument(
            "-d",
            dest="output_dir",
            help="Output directory. " + "Default is input file directory.",
        )
        parser.add_argument(
            "-l",
            dest="level",
            default="variant",
            help="Summarize level. " + "Default is variant.",
        )
        parser.add_argument(
            "--confs", dest="confs", default="{}", help="Configuration string"
        )
        self.cmd_arg_parser = parser

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
        self.dbpath = os.path.join(self.output_dir, self.run_name + ".sqlite")
        self.confs = None
        if parsed_args.confs is not None:
            confs = parsed_args.confs.lstrip("'").rstrip("'").replace("'", '"')
            self.confs = json.loads(confs)

    def run(self):
        if not self.should_run_annotate:
            self.base_cleanup()
            return
        start_time = time.time()
        self.status_writer.queue_status_update(
            "status", "Started {} ({})".format(self.conf["title"], self.module_name)
        )
        last_status_update_time = time.time()
        self.logger.info(
            "started: {0}".format(time.asctime(time.localtime(start_time)))
        )
        self.base_setup()
        lnum = 0
        json_colnames = []
        table_headers = {}
        output_columns = self.conf["output_columns"]
        for col in output_columns:
            if "table" in col and col["table"] == True:
                json_colnames.append(col["name"])
                table_headers[col["name"]] = []
                for h in col["table_header"]:
                    table_headers[col["name"]].append(h["name"])
        for input_data in self._get_input():
            try:
                output_dict = self.annotate(input_data)
                if output_dict is None:
                    continue
                # Handles table-format column data.
                delflag = False
                for colname in json_colnames:
                    json_data = output_dict.get(colname, None)
                    if json_data is None and "__" in colname:
                        shortcolname = colname.split("__")[1]
                        json_data = output_dict.get(shortcolname, None)
                        delflag = json_data is not None
                    if json_data is not None:
                        if type(json_data) is list:
                            for rowidx in range(len(json_data)):
                                row = json_data[rowidx]
                                if type(row) is list:
                                    pass
                                elif type(row) is dict:
                                    tmp = []
                                    for i in range(len(table_headers[colname])):
                                        h = table_headers[colname][i]
                                        if h in row:
                                            v = row[h]
                                        else:
                                            v = None
                                        tmp.append(v)
                                    json_data[rowidx] = tmp
                        json_data = json.dumps(json_data)
                        out = json_data
                    else:
                        out = None
                    output_dict[colname] = out
                    if delflag:
                        del output_dict[shortcolname]
                fixed_output = {}
                self.write_output(input_data, output_dict)
                cur_time = time.time()
                lnum += 1
                if lnum % 10000 == 0 or cur_time - last_status_update_time > 3:
                    self.status_writer.queue_status_update(
                        "status",
                        "Running {} ({}): row {}".format(
                            self.conf["title"], self.module_name, lnum
                        ),
                    )
                    last_status_update_time = cur_time
            except Exception as e:
                self._log_runtime_exception(input_data, e)
        self.fill_categories()
        self.dbconn.commit()
        self.base_cleanup()
        end_time = time.time()
        run_time = end_time - start_time
        self.logger.info("finished: {0}".format(time.asctime(time.localtime(end_time))))
        self.logger.info("runtime: {0:0.3f}".format(run_time))
        self.status_writer.queue_status_update(
            "status", "Finished {} ({})".format(self.conf["title"], self.module_name)
        )

    def fill_categories(self):
        for col_d in self.conf["output_columns"]:
            col_def = ColumnDefinition(col_d)
            if col_def.category not in ["single", "multi"]:
                continue
            col_name = col_def.name
            q = "select distinct {} from {}".format(col_name, self.level)
            self.cursor.execute(q)
            col_cats = []
            for r in self.cursor:
                col_cat_str = r[0] if r[0] is not None else ""
                for col_cat in col_cat_str.split(";"):
                    if col_cat not in col_cats:
                        col_cats.append(col_cat)
            col_cats.sort()
            col_def.categories = col_cats
            q = "update {}_header set col_def=? where col_name=?".format(self.level)
            self.cursor.execute(q, [col_def.get_json(), col_def.name])

    def write_output(self, input_data, output_dict):
        q = ""
        for col_def in self.conf["output_columns"]:
            col_name = col_def["name"]
            shortcol_name = col_name.split("__")[1]
            if shortcol_name in output_dict:
                val = output_dict[shortcol_name]
                if val is None:
                    continue
                col_type = col_def["type"]
                if col_type in ["string"]:
                    val = '\'' + val + '\''
                else:
                    val = str(val)
                q += col_name + "=" + val + ","
        q = q.rstrip(",")
        if q == "":
            return
        q = "update " + self.level + " set " + q
        q += " where "
        if self.levelno == VARIANT:
            q += "base__uid=" + str(input_data["base__uid"])
        elif self.levelno == GENE:
            q += 'base__hugo="' + input_data["base__hugo"] + '"'
        self.cursor_w.execute(q)

    def _log_runtime_exception(self, input_data, e):
        try:
            err_str = traceback.format_exc().rstrip()
            if err_str not in self.unique_excs:
                self.unique_excs.append(err_str)
                self.logger.error(err_str)
            self.error_logger.error(
                "\nINPUT:{}\nERROR:{}\n#".format(str(input_data), str(e))
            )
        except Exception as e:
            self._log_exception(e, halt=False)

    # Setup function for the base_annotator, different from self.setup()
    # which is intended to be for the derived annotator.
    def base_setup(self):
        self._alter_tables()
        self.setup()

    def _open_db_connection(self):
        self.db_path = os.path.join(self.output_dir, self.run_name + ".sqlite")
        if os.path.exists(self.db_path):
            self.dbconn = sqlite3.connect(self.db_path)
            self.cursor = self.dbconn.cursor()
            self.cursor_w = self.dbconn.cursor()
            self.cursor_w.execute('pragma journal_mode="wal"')
        else:
            msg = self.db_path + " not found"
            if self.logger:
                self.logger.error(msg)
            sys.exit(msg)

    def _close_db_connection(self):
        self.cursor.close()
        self.cursor_w.close()
        self.dbconn.close()

    def _alter_tables(self):
        # annotator table
        q = 'insert or replace into {:} values ("{:}", "{:}", "{}")'.format(
            self.level + "_annotator",
            self.module_name,
            self.conf["title"],
            self.conf["version"],
        )
        self.cursor_w.execute(q)
        # data table and header table
        header_table_name = self.level + "_header"
        for col_d in self.conf["output_columns"]:
            col_def = ColumnDefinition(col_d)
            colname = col_def.name
            coltype = col_def.type
            # data table
            try:
                self.cursor.execute(f"select {colname} from {self.level} limit 1")
            except:
                q = (
                    "alter table "
                    + self.level
                    + " add column "
                    + colname
                    + " "
                    + self.cr_type_to_sql[coltype]
                )
                self.cursor_w.execute(q)
            # header table
            # use prepared statement to allow " characters in colcats and coldesc
            q = "insert or replace into {} values (?, ?)".format(header_table_name)
            self.cursor_w.execute(q, [colname, col_def.get_json()])
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
            self.logger = logging.getLogger("cravat." + self.module_name)
        except Exception as e:
            self._log_exception(e)
        self.error_logger = logging.getLogger("error." + self.module_name)
        self.unique_excs = []

    def _get_input(self):
        dbconnloop = sqlite3.connect(self.db_path)
        cursorloop = dbconnloop.cursor()
        q = "select * from " + self.level
        cursorloop.execute(q)
        for row in cursorloop:
            try:
                input_data = {}
                for i in range(len(row)):
                    input_data[cursorloop.description[i][0]] = row[i]
                yield input_data
            except Exception as e:
                self._log_runtime_exception(row, e)

    def annotate(self, input_data):
        raise NotImplementedError()
