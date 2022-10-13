import time
import argparse
import os
import sys
from cravat import admin_util as au
from cravat import util
from cravat.config_loader import ConfigLoader
from cravat.util import write_log_msg
import aiosqlite
import datetime
from types import SimpleNamespace
from cravat import constants
import json
import logging
import traceback
from cravat.mp_runners import init_worker, annot_from_queue, mapper_runner
import multiprocessing as mp
import multiprocessing.managers
from logging.handlers import QueueListener
from cravat.aggregator import Aggregator
from cravat.exceptions import *
import oyaml as yaml
import cravat.cravat_util as cu
import collections
import asyncio
import sqlite3
from cravat.inout import CravatWriter
from cravat.inout import CravatReader
import glob
import nest_asyncio

nest_asyncio.apply()
import re
import sys

if sys.platform == "win32" and sys.version_info >= (3, 8):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import shutil

# Custom system conf
pre_parser = argparse.ArgumentParser(add_help=False)
pre_parser.add_argument(
    "--system-option", dest="system_option", nargs="*", default=None
)
args, unknown_args = pre_parser.parse_known_args(sys.argv[1:])
if args.system_option is not None:
    custom_system_conf = {}
    for kv in args.system_option:
        if "=" not in kv:
            continue
        toks = kv.split("=")
        if len(toks) != 2:
            continue
        [k, v] = toks
        try:
            v = int(v)
        except ValueError:
            pass
        custom_system_conf[k] = v
    au.custom_system_conf = custom_system_conf
    au.update_mic()
else:
    au.custom_system_conf = {}

cravat_cmd_parser = argparse.ArgumentParser(
    prog="cravat input_file_path_1 input_file_path_2 ...",
    description="Open-CRAVAT genomic variant interpreter. https://github.com/KarchinLab/open-cravat. Use input_file_path arguments before any option or define them in a conf file (option -c).",
    epilog="inputs should be the first option",
)
cravat_cmd_parser.add_argument(
    "inputs",
    nargs="*",
    default=None,
    help="Input file(s). One or more variant files in a supported format like VCF.  "
    + "See the -i/--input-format flag for supported formats. In the special case "
    + "where you want to add annotations to an existing open-cravat analysis, "
    + "provide the output sqlite database from the previous run as input instead of a variant input file.",
)
cravat_cmd_parser.add_argument(
    "-a", nargs="+", dest="annotators", default=[], help="Annotator module names or directories. If --package is used also, annotator modules defined with -a will be added."
)
cravat_cmd_parser.add_argument(
    "-A", nargs="+", dest="annotators_replace", default=[], help="Annotator module names or directories. If --package is used also, annotator modules defined with -A will replace those defined with --package. -A has priority over -a."
)
cravat_cmd_parser.add_argument(
    "-e", nargs="+", dest="excludes", default=[], help="annotators to exclude"
)
cravat_cmd_parser.add_argument("-n", dest="run_name", help="name of cravat run")
cravat_cmd_parser.add_argument(
    "-d", dest="output_dir", default=None, help="directory for output files"
)
cravat_cmd_parser.add_argument(
    "--startat",
    dest="startat",
    choices=[
        "converter",
        "mapper",
        "annotator",
        "aggregator",
        "postaggregator",
        "reporter",
    ],
    default=None,
    help="starts at given stage",
)
cravat_cmd_parser.add_argument(
    "--endat",
    dest="endat",
    choices=[
        "converter",
        "mapper",
        "annotator",
        "aggregator",
        "postaggregator",
        "reporter",
    ],
    default=None,
    help="ends after given stage.",
)
cravat_cmd_parser.add_argument(
    "--skip",
    dest="skip",
    nargs="+",
    choices=[
        "converter",
        "mapper",
        "annotator",
        "aggregator",
        "postaggregator",
        "reporter",
    ],
    default=None,
    help="skips given stage(s).",
)
cravat_cmd_parser.add_argument(
    "-c", dest="conf", default="oc.yml", help="path to a conf file"
)
cravat_cmd_parser.add_argument(
    "--cs", dest="confs", default=None, help="configuration string"
)
cravat_cmd_parser.add_argument(
    "-v", dest="verbose", action="store_true", default=None, help="verbose"
)
cravat_cmd_parser.add_argument(
    "-t",
    nargs="+",
    dest="reports",
    default=[],
    help="Reporter types or reporter module directories"
)
cravat_cmd_parser.add_argument(
    "-l",
    "--liftover",
    dest="genome",
    choices=constants.assembly_choices,
    default=None,
    help="reference genome of input. CRAVAT will lift over to hg38 if needed.",
)
cravat_cmd_parser.add_argument(
    "-x",
    dest="cleandb",
    action="store_true",
    help="deletes the existing result database and creates a new one.",
)
cravat_cmd_parser.add_argument(
    "--newlog",
    dest="newlog",
    action="store_true",
    default=None,
    help="deletes the existing log file and creates a new one.",
)
cravat_cmd_parser.add_argument(
    "--note",
    dest="note",
    default=None,
    help="note will be written to the run status file (.status.json)",
)
cravat_cmd_parser.add_argument(
    "--mp", dest="mp", default=None, help="number of processes to use to run annotators"
)
cravat_cmd_parser.add_argument(
    "-i",
    "--input-format",
    dest="forcedinputformat",
    default=None,
    choices=au.input_formats(),
    help="Force input format",
)
cravat_cmd_parser.add_argument(
    "--temp-files",
    dest="temp_files",
    action="store_true",
    default=None,
    help="Leave temporary files after run is complete.",
)
cravat_cmd_parser.add_argument(
    "--writeadmindb",
    dest="writeadmindb",
    action="store_true",
    default=None,
    help="Write job information to admin db after job completion",
)
cravat_cmd_parser.add_argument(
    "--jobid", dest="jobid", default=None, help="Job ID for server version"
)
cravat_cmd_parser.add_argument(
    "--version",
    dest="show_version",
    action="store_true",
    default=None,
    help="Shows open-cravat version.",
)
cravat_cmd_parser.add_argument(
    "--separatesample",
    dest="separatesample",
    action="store_true",
    default=None,
    help="Separate variant results by sample",
)
cravat_cmd_parser.add_argument(
    "--unique-variants",
    dest="unique_variants",
    action="store_true",
    default=None,
    help=argparse.SUPPRESS,
)
cravat_cmd_parser.add_argument(
    "--primary-transcript",
    dest="primary_transcript",
    nargs="*",
    default=["mane"],
    help='"mane" for MANE transcripts as primary transcripts, or a path to a file of primary transcripts. MANE is default.',
)
cravat_cmd_parser.add_argument(
    "--cleanrun",
    dest="clean_run",
    action="store_true",
    default=None,
    help="Deletes all previous output files for the job and generate new ones.",
)
cravat_cmd_parser.add_argument(
    "--do-not-change-status",
    dest="do_not_change_status",
    action="store_true",
    default=None,
    help="Job status in status.json will not be changed",
)
cravat_cmd_parser.add_argument(
    "--module-option",
    dest="module_option",
    nargs="*",
    help="Module-specific option in module_name.key=value syntax. For example, --module-option vcfreporter.type=separate",
)
cravat_cmd_parser.add_argument(
    "--system-option",
    dest="system_option",
    nargs="*",
    help="System option in key=value syntax. For example, --system-option modules_dir=/home/user/open-cravat/modules",
)
cravat_cmd_parser.add_argument(
    "--silent", dest="silent", action="store_true", default=None, help="Runs silently."
)
cravat_cmd_parser.add_argument(
    "--concise-report",
    dest="concise_report",
    action="store_true",
    default=None,
    help="Generate concise reports with default columns defined by each annotation module",
)
cravat_cmd_parser.add_argument(
    "--package", dest="package", default=None, help="Use package"
)
cravat_cmd_parser.add_argument("--filtersql", default=None, help="Filter SQL")
cravat_cmd_parser.add_argument("--includesample", nargs='+', default=None, help="Sample IDs to include")
cravat_cmd_parser.add_argument("--excludesample", nargs='+', default=None, help="Sample IDs to exclude")
cravat_cmd_parser.add_argument("--filter", default=None, help=argparse.SUPPRESS)
cravat_cmd_parser.add_argument("-f", dest="filterpath", default=None, help="Path to a filter file")
cravat_cmd_parser.add_argument("--md", default=None, help="Specify the root directory of OpenCRAVAT modules (annotators, etc)")
cravat_cmd_parser.add_argument("-m", dest="mapper_name", nargs="+", default=[], help="Mapper module name or mapper module directory")
cravat_cmd_parser.add_argument("-p", nargs="+", dest="postaggregators", default=[], help="Postaggregators to run. Additionally, tagsampler, casecontrol, varmeta, and vcfinfo will automatically run depending on conditions.")

def run(cmd_args):
    au.ready_resolution_console()
    module = Cravat(**vars(cmd_args))
    loop = asyncio.get_event_loop()
    response = loop.run_until_complete(module.main())
    return response


def run_cravat_job(**kwargs):
    module = Cravat(**kwargs)
    loop = asyncio.get_event_loop()
    response = loop.run_until_complete(module.main())
    return response


cravat_cmd_parser.set_defaults(func=run)


class MyManager(multiprocessing.managers.SyncManager):
    pass


class Cravat(object):
    def __init__(self, **kwargs):
        self.runlevels = {
            "converter": 1,
            "mapper": 2,
            "annotator": 3,
            "aggregator": 4,
            "postaggregator": 5,
            "reporter": 6,
        }
        self.should_run_converter = False
        self.should_run_genemapper = False
        self.should_run_annotators = True
        self.should_run_aggregator = True
        self.should_run_reporter = True
        self.pythonpath = sys.executable
        self.annotators = {}
        self.append_mode = False
        self.pipeinput = False
        try:
            self.make_args_namespace(kwargs)
            if self.args.clean_run:
                if not self.args.silent:
                    print("Deleting previous output files...")
                self.delete_output_files()
            self.get_logger()
            self.start_time = time.time()
            self.logger.info(f'{" ".join(sys.argv)}')
            self.logger.info(
                "started: {0}".format(time.asctime(time.localtime(self.start_time)))
            )
            if self.run_conf_path != "":
                self.logger.info("conf file: {}".format(self.run_conf_path))
            self.modules_conf = self.conf.get_modules_conf()
            self.write_initial_status_json()
            self.unique_logs = {}
            self.manager = MyManager()
            self.manager.register("StatusWriter", StatusWriter)
            self.manager.start()
            self.status_writer = self.manager.StatusWriter(self.status_json_path)
        except Exception as e:
            self.handle_exception(e)

    def check_valid_modules(self, module_names):
        for module_name in module_names:
            if au.module_exists_local(module_name) == False:
                raise InvalidModule(module_name)

    def write_initial_status_json(self):
        status_fname = "{}.status.json".format(self.run_name)
        self.status_json_path = os.path.join(self.output_dir, status_fname)
        if os.path.exists(self.status_json_path) == True:
            with open(self.status_json_path) as f:
                try:
                    self.status_json = json.load(f)
                    self.pkg_ver = self.status_json["open_cravat_version"]
                except:
                    self.pkg_ver = au.get_current_package_version()
            if self.status_json["status"] == "Submitted":
                self.status_json["job_dir"] = self.output_dir
                self.status_json["id"] = os.path.basename(
                    os.path.normpath(self.output_dir)
                )
                self.status_json["run_name"] = self.run_name
                self.status_json["assembly"] = self.input_assembly
                self.status_json["db_path"] = os.path.join(
                    self.output_dir, self.run_name + ".sqlite"
                )
                self.status_json["orig_input_fname"] = [
                    os.path.basename(x) for x in self.inputs
                ]
                self.status_json["orig_input_path"] = self.inputs
                self.status_json[
                    "submission_time"
                ] = datetime.datetime.now().isoformat()
                self.status_json["viewable"] = False
                self.status_json["note"] = self.args.note
                self.status_json["status"] = "Starting"
                self.status_json["reports"] = (
                    self.args.reports if self.args.reports != None else []
                )
                self.pkg_ver = au.get_current_package_version()
                self.status_json["open_cravat_version"] = self.pkg_ver
                annot_names = list(self.annotators.keys())
                annot_names.sort()
                if "original_input" in annot_names:
                    annot_names.remove("original_input")
                self.status_json["annotators"] = annot_names
                with open(self.status_json_path, "w") as wf:
                    wf.write(json.dumps(self.status_json, indent=2, sort_keys=True))
        else:
            self.status_json = {}
            self.status_json["job_dir"] = self.output_dir
            self.status_json["id"] = os.path.basename(os.path.normpath(self.output_dir))
            self.status_json["run_name"] = self.run_name
            self.status_json["assembly"] = self.input_assembly
            self.status_json["db_path"] = os.path.join(
                self.output_dir, self.run_name + ".sqlite"
            )
            self.status_json["orig_input_fname"] = [
                os.path.basename(x) for x in self.inputs
            ]
            self.status_json["orig_input_path"] = self.inputs
            self.status_json["submission_time"] = datetime.datetime.now().isoformat()
            self.status_json["viewable"] = False
            self.status_json["note"] = self.args.note
            self.status_json["status"] = "Starting"
            self.status_json["reports"] = (
                self.args.reports if self.args.reports != None else []
            )
            self.pkg_ver = au.get_current_package_version()
            self.status_json["open_cravat_version"] = self.pkg_ver
            annot_names = list(self.annotators.keys())
            annot_names.sort()
            self.status_json["annotators"] = annot_names
            with open(self.status_json_path, "w") as wf:
                wf.write(json.dumps(self.status_json, indent=2, sort_keys=True))

    def get_logger(self):
        if self.args.newlog == True:
            self.logmode = "w"
        else:
            self.logmode = "a"
        self.logger = logging.getLogger("cravat")
        self.logger.setLevel("INFO")
        self.log_path = os.path.join(self.output_dir, self.run_name + ".log")
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
        self.log_handler = logging.FileHandler(self.log_path, mode=self.logmode)
        formatter = logging.Formatter(
            "%(asctime)s %(name)-20s %(message)s", "%Y/%m/%d %H:%M:%S"
        )
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
        # individual input line error log
        self.error_logger = logging.getLogger("error")
        self.error_logger.setLevel("INFO")
        error_log_path = os.path.join(self.output_dir, self.run_name + ".err")
        if os.path.exists(error_log_path):
            os.remove(error_log_path)
        self.error_log_handler = logging.FileHandler(error_log_path, mode=self.logmode)
        formatter = logging.Formatter("SOURCE:%(name)-20s %(message)s")
        self.error_log_handler.setFormatter(formatter)
        self.error_logger.addHandler(self.error_log_handler)

    def close_logger(self):
        self.log_handler.close()
        self.logger.removeHandler(self.log_handler)
        self.error_log_handler.close()
        self.error_logger.removeHandler(self.error_log_handler)
        logging.shutdown()

    def update_status(self, status, force=False):
        if self.args.do_not_change_status != True:
            self.status_writer.queue_status_update("status", status, force=force)

    def run(self):
        import asyncio

        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(self.main())
        loop.close()
        return response

    def delete_output_files(self):
        fns = glob.glob(glob.escape(os.path.join(self.output_dir, self.run_name) + ".*"))
        for fn in fns:
            if not self.args.silent:
                print(f"  Removing {fn}")
            os.remove(fn)

    def log_versions(self):
        self.logger.info(f"version: open-cravat {au.get_current_package_version()} {os.path.dirname(os.path.abspath(__file__))}")
        if self.package_conf is not None and len(self.package_conf) > 0:
            self.logger.info(
                f'package: {self.args.package} {self.package_conf["version"]}'
            )
        for mname, module in self.annotators.items():
            self.logger.info(f"version: {module.name} {module.conf['version']} {os.path.dirname(module.script_path)}")
        if "mapper" not in self.args.skip:
            module = self.mapper
            self.logger.info(f'version: {module.name} {module.conf["version"]} {os.path.dirname(module.script_path)}')
        for mname, module in self.reports.items():
            self.logger.info(f"version: {module.name} {module.conf['version']} {os.path.dirname(module.script_path)}")

    async def main(self):
        no_problem_in_run = True
        report_response = None
        try:
            self.aggregator_ran = False
            self.update_status("Started cravat", force=True)
            if self.pipeinput == False:
                input_files_str = ", ".join(self.inputs)
            else:
                input_files_str = "stdin"
            if not self.args.silent:
                print("Input file(s): {}".format(input_files_str))
                print("Genome assembly: {}".format(self.input_assembly))
            self.logger.info("input files: {}".format(input_files_str))
            self.logger.info("input assembly: {}".format(self.input_assembly))
            self.log_versions()
            self.set_and_check_input_files()
            converter_ran = False
            if (
                self.endlevel >= self.runlevels["converter"]
                and self.startlevel <= self.runlevels["converter"]
                and not "converter" in self.args.skip
            ):
                if not self.args.silent:
                    print("Running converter...")
                stime = time.time()
                self.run_converter()
                rtime = time.time() - stime
                if not self.args.silent:
                    print("finished in {0:.3f}s".format(rtime))
                converter_ran = True
                if self.numinput == 0:
                    msg = "No variant found in input"
                    if not self.args.silent:
                        print(msg)
                    self.logger.info(msg)
                    exit()
            self.mapper_ran = False
            if (
                self.endlevel >= self.runlevels["mapper"]
                and self.startlevel <= self.runlevels["mapper"]
                and not "mapper" in self.args.skip
            ):
                if not self.args.silent:
                    print(f'Running gene mapper...{" "*18}', end="", flush=True)
                stime = time.time()
                multicore_mapper_mode = self.conf.get_cravat_conf()[
                    "multicore_mapper_mode"
                ]
                if multicore_mapper_mode:
                    self.run_genemapper_mp()
                else:
                    self.run_genemapper()
                rtime = time.time() - stime
                if not self.args.silent:
                    print("finished in {0:.3f}s".format(rtime))
                self.mapper_ran = True
            self.annotator_ran = False
            self.done_annotators = {}
            self.populate_secondary_annotators()
            for mname, module in self.annotators.items():
                if self.check_module_output(module) is not None:
                    self.done_annotators[mname] = module
            self.run_annotators = {
                aname: self.annotators[aname]
                for aname in set(self.annotators) - set(self.done_annotators)
            }
            if (
                self.endlevel >= self.runlevels["annotator"]
                and self.startlevel <= self.runlevels["annotator"]
                and not "annotator" in self.args.skip
                and (self.mapper_ran or len(self.run_annotators) > 0)
            ):
                if not self.args.silent:
                    print("Running annotators...")
                stime = time.time()
                self.run_annotators_mp()
                rtime = time.time() - stime
                if not self.args.silent:
                    print("\tannotator(s) finished in {0:.3f}s".format(rtime))
            if (
                self.endlevel >= self.runlevels["aggregator"]
                and self.startlevel <= self.runlevels["aggregator"]
                and not "aggregator" in self.args.skip
                and (
                    self.mapper_ran
                    or self.annotator_ran
                    or self.startlevel == self.runlevels["aggregator"]
                )
            ):
                if not self.args.silent:
                    print("Running aggregator...")
                self.result_path = self.run_aggregator()
                await self.write_job_info()
                self.write_smartfilters()
                self.aggregator_ran = True
            if (
                self.endlevel >= self.runlevels["postaggregator"]
                and self.startlevel <= self.runlevels["postaggregator"]
                and not "postaggregator" in self.args.skip
            ):
                if not self.args.silent:
                    print("Running postaggregators...")
                self.run_postaggregators()
            if (
                self.endlevel >= self.runlevels["reporter"]
                and self.startlevel <= self.runlevels["reporter"]
                and not "reporter" in self.args.skip
                and self.aggregator_ran
                and self.reports
            ):
                if not self.args.silent:
                    print("Running reporter...")
                no_problem_in_run, report_response = await self.run_reporter()
            self.update_status("Finished", force=True)
        except Exception as e:
            self.handle_exception(e)
            no_problem_in_run = False
        finally:
            end_time = time.time()
            display_time = time.asctime(time.localtime(end_time))
            runtime = end_time - self.start_time
            if no_problem_in_run:
                self.logger.info("finished: {0}".format(display_time))
                self.logger.info("runtime: {0:0.3f}s".format(runtime))
                if not self.args.silent:
                    print("Finished normally. Runtime: {0:0.3f}s".format(runtime))
            else:
                self.logger.info("finished with an exception: {0}".format(display_time))
                self.logger.info("runtime: {0:0.3f}s".format(runtime))
                if not self.args.silent:
                    print(
                        "Finished with an exception. Runtime: {0:0.3f}s".format(runtime)
                    )
                    print("Check {}".format(self.log_path))
                self.update_status("Error", force=True)
            self.close_logger()
            if self.args.do_not_change_status != True:
                self.status_writer.flush()
            if no_problem_in_run and not self.args.temp_files and self.aggregator_ran:
                self.clean_up_at_end()
            if self.args.writeadmindb:
                await self.write_admin_db(runtime, self.numinput)
            if (
                report_response is not None
                and type(report_response) == list
                and len(report_response) == 1
            ):
                return report_response[list(report_response.keys())[0]]
            else:
                return report_response

    async def write_admin_db(self, runtime, numinput):
        if runtime is None or numinput is None:
            return
        if os.path.exists(constants.admindb_path) == False:
            s = "{} does not exist.".format(constants.admindb_path)
            self.logger.info(s)
            if not self.args.silent:
                print(s)
            return
        db = await aiosqlite.connect(constants.admindb_path)
        cursor = await db.cursor()
        q = 'update jobs set runtime={}, numinput={} where jobid="{}"'.format(
            runtime, numinput, self.args.jobid
        )
        await cursor.execute(q)
        await db.commit()
        await cursor.close()
        await db.close()

    def write_smartfilters(self):
        if not self.args.silent:
            print("Indexing")
        dbpath = os.path.join(self.output_dir, self.run_name + ".sqlite")
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        q = "create table if not exists smartfilters (name text primary key, definition text)"
        cursor.execute(q)
        ins_template = (
            "insert or replace into smartfilters (name, definition) values (?, ?);"
        )
        cols_to_index = set()
        for sf in constants.base_smartfilters:
            cols_to_index |= util.filter_affected_cols(sf["filter"])
        if self.annotator_ran:
            for linfo in self.annotators.values():
                if linfo.smartfilters is not None:
                    for sf in linfo.smartfilters:
                        cols_to_index |= util.filter_affected_cols(sf["filter"])
                    mname = linfo.name
                    json_info = json.dumps(linfo.smartfilters)
                    cursor.execute(ins_template, (mname, json_info))
        cursor.execute("pragma table_info(variant)")
        variant_cols = {row[1] for row in cursor}
        cursor.execute("pragma table_info(gene)")
        gene_cols = {row[1] for row in cursor}
        cursor.execute('select name from sqlite_master where type="index"')
        existing_indices = {row[0] for row in cursor}
        for col in cols_to_index:
            if col in variant_cols:
                index_name = f"sf_variant_{col}"
                if index_name not in existing_indices:
                    q = f"create index if not exists {index_name} on variant ({col})"
                    if not self.args.silent:
                        print(f"\tvariant {col}", end="", flush=True)
                    st = time.time()
                    cursor.execute(q)
                    if not self.args.silent:
                        print(f"\tfinished in {time.time()-st:.3f}s")
            if col in gene_cols:
                index_name = f"sf_gene_{col}"
                if index_name not in existing_indices:
                    q = f"create index if not exists {index_name} on gene ({col})"
                    if not self.args.silent:
                        print(f"\tgene {col}", end="", flush=True)
                    st = time.time()
                    cursor.execute(q)
                    if not self.args.silent:
                        print(f"\tfinished in {time.time()-st:.3f}s")

        # Package filter
        if hasattr(self.args, "filter") and self.args.filter is not None:
            q = "create table if not exists viewersetup (datatype text, name text, viewersetup text, unique (datatype, name))"
            cursor.execute(q)
            filter_set = json.dumps({"filterSet": self.args.filter})
            q = f'insert or replace into viewersetup values ("filter", "quicksave-name-internal-use", \'{filter_set}\')'
            cursor.execute(q)
        conn.commit()
        cursor.close()
        conn.close()

    def handle_exception(self, e):
        exc_str = traceback.format_exc()
        exc_class = e.__class__
        if exc_class == InvalidModule:
            if hasattr(self, 'logger'):
                self.logger.error(str(e))
            if not self.args.silent:
                print(e)
            exit()
        elif exc_class == InvalidData:
            pass
        elif exc_class == ExpectedException:
            self.logger.exception("An expected exception occurred.")
            self.logger.error(e)
        else:
            self.logger.exception("An unexpected exception occurred.")
            if not self.args.silent:
                print(exc_str)

    def set_package_conf(self, supplied_args):
        if "package" in supplied_args:
            package_name = supplied_args["package"]
            del supplied_args["package"]
            if package_name in au.mic.get_local():
                self.package_conf = au.mic.get_local()[package_name].conf
            else:
                self.package_conf = {}
        else:
            self.package_conf = {}

    def make_self_args_considering_package_conf(self, supplied_args):
        full_args = util.get_argument_parser_defaults(cravat_cmd_parser)
        # package
        if "run" in self.package_conf:
            package_conf_run = {k: v for k, v in self.package_conf['run'].items() if v is not None}
            full_args.update(package_conf_run)
        # command-line arguments
        supplied_args_no_none = {k: v for k, v in supplied_args.items() if v is not None}
        if 'inputs' in full_args and full_args['inputs'] is not None and 'inputs' in supplied_args_no_none:
            del supplied_args_no_none['inputs']
        # -a and -A regarding --package
        annos_pkg = full_args['annotators']
        annos_add = supplied_args_no_none.get('annotators')
        annos_repl = supplied_args_no_none.get('annotators_replace')
        if len(annos_pkg) > 0:
            if len(annos_repl) > 0:
                full_args['annotators'] = annos_repl
            elif len(annos_add) > 0:
                full_args['annotators'] = list(set(full_args['annotators']).union(set(annos_add)))
        else:
            if len(annos_repl) > 0:
                full_args['annotators'] = annos_repl
            elif len(annos_add) > 0:
                full_args['annotators'] = annos_add
        # other command-line arguments
        for k, v in supplied_args_no_none.items():
            if k in ['annotators', 'annotators_replace']:
                continue
            if full_args.get(k, None) is not None:
                fv = full_args[k]
                if fv is None or (type(fv) == list and len(fv) == 0):
                    full_args[k] = v
            else:
                full_args[k] = v
        self.args = SimpleNamespace(**full_args)
        self.make_run_conf_path()
        self.make_self_conf()
        self.process_module_options()
        self.cravat_conf = self.conf.get_cravat_conf()
        self.run_conf = self.conf._all
        args_keys = self.args.__dict__.keys()
        for arg_key in args_keys:
            if self.args.__dict__[arg_key] is None and arg_key in self.run_conf:
                self.args.__dict__[arg_key] = self.run_conf[arg_key]

    def make_run_conf_path(self):
        self.run_conf_path = ""
        if hasattr(self.args, "conf") and os.path.exists(self.args.conf):
            self.run_conf_path = self.args.conf

    def make_self_conf(self):
        self.conf = ConfigLoader(job_conf_path=self.run_conf_path)
        if self.args.confs != None:
            conf_bak = self.conf
            try:
                confs_conf = json.loads(self.args.confs.replace("'", '"'))
                self.conf.override_all_conf(confs_conf)
            except Exception as e:
                if not self.args.silent:
                    print("Error in processing cs option. --cs option was not applied.")
                self.conf = conf_bak

    def process_module_options(self):
        if self.args.module_option is not None:
            for opt_str in self.args.module_option:
                toks = opt_str.split("=")
                if len(toks) != 2:
                    if not self.args.silent:
                        print(
                            "Ignoring invalid module option {opt_str}. module-option should be module_name.key=value."
                        )
                    continue
                k = toks[0]
                if k.count(".") != 1:
                    if not self.args.silent:
                        print(
                            "Ignoring invalid module option {opt_str}. module-option should be module_name.key=value."
                        )
                    continue
                [module_name, key] = k.split(".")
                if module_name not in self.conf._all:
                    self.conf._all[module_name] = {}
                v = toks[1]
                self.conf._all[module_name][key] = v

    def set_self_inputs(self):
        if self.args.inputs is not None and len(self.args.inputs) == 0:
            if "inputs" in self.run_conf:
                if type(self.run_conf["inputs"]) == list:
                    self.args.inputs = self.run_conf["inputs"]
                else:
                    if not self.args.silent:
                        print("inputs in conf file is invalid")
            else:
                cravat_cmd_parser.print_help()
                print("\nNo input file was given.")
                exit()
        self.process_url_and_pipe_inputs()
        self.num_input = len(self.inputs)

    def download_url_input(self, input_no):
        ip = self.inputs[input_no]
        if " " in ip:
            print(f"Space is not allowed in input file paths ({ip})")
            exit()
        if util.is_url(ip):
            import requests
            if not self.args.silent:
                print(f"Fetching {ip}... ")
            try:
                r = requests.head(ip)
                r = requests.get(ip, stream=True)
                fn = os.path.basename(ip)
                fpath = fn
                cur_size = 0.0
                num_total_star = 40.0
                total_size = float(r.headers["content-length"])
                with open(fpath, "wb") as wf:
                    for chunk in r.iter_content(chunk_size=8192):
                        wf.write(chunk)
                        cur_size += float(len(chunk))
                        perc = cur_size / total_size
                        cur_star = int(perc * num_total_star)
                        rem_stars = int(num_total_star - cur_star)
                        cur_prog = "*" * cur_star
                        rem_prog = " " * rem_stars
                        print(
                            f"[{cur_prog}{rem_prog}] {util.humanize_bytes(cur_size)} / {util.humanize_bytes(total_size)} ({perc * 100.0:.0f}%)",
                            end="\r",
                            flush=True,
                        )
                        if cur_size == total_size:
                            print("\n")
                self.inputs[input_no] = os.path.abspath(fpath)
            except:
                print(f"File downloading unsuccessful. Exiting.")
                exit()
            return None
        else:
            return ip

    def process_url_and_pipe_inputs(self):
        self.first_non_url_input = None
        if (
            self.args.inputs is not None
            and len(self.args.inputs) == 1
            and self.args.inputs[0] == "-"
        ):
            self.pipeinput = True
        if self.args.inputs is not None:
            self.inputs = [
                os.path.abspath(x) if not util.is_url(x) and x != "-" else x
                for x in self.args.inputs
            ]
            for input_no in range(len(self.inputs)):
                if self.download_url_input(input_no) is not None and self.first_non_url_input is None:
                    self.first_non_url_input = self.inputs[input_no]
        else:
            self.inputs = []

    def set_run_name(self):
        self.run_name = self.args.run_name
        if self.run_name == None:
            if self.num_input == 0 or self.pipeinput:
                self.run_name = "cravat_run"
            else:
                self.run_name = os.path.basename(self.inputs[0])
                if self.num_input > 1:
                    self.run_name += "_and_" + str(len(self.inputs) - 1) + "_files"

    def set_append_mode(self):
        if self.num_input > 0 and self.inputs[0].endswith(".sqlite"):
            self.append_mode = True
            if self.args.skip is None:
                self.args.skip = ["converter", "mapper"]
            else:
                if "converter" not in self.args.skip:
                    self.args.skip.append("converter")
                if "mapper" not in self.args.skip:
                    self.args.skip.append("mapper")
            if self.args.output_dir:
                if self.run_name.endswith(".sqlite"):
                    target_name = self.run_name
                else:
                    target_name = self.run_name + ".sqlite"
                target_path = os.path.join(self.args.output_dir, target_name)
                shutil.copyfile(self.inputs[0], target_path)
                self.inputs[0] = target_path
            if self.run_name.endswith(".sqlite"):
                self.run_name = self.run_name[:-7]

    def set_output_dir(self):
        self.output_dir = self.args.output_dir
        if self.output_dir == None:
            if self.num_input == 0 or self.first_non_url_input is None:
                self.output_dir = os.getcwd()
            else:
                self.output_dir = os.path.dirname(os.path.abspath(self.first_non_url_input))
        else:
            self.output_dir = os.path.abspath(self.output_dir)
        if os.path.exists(self.output_dir) == False:
            os.mkdir(self.output_dir)

    def set_genome_assembly(self):
        if self.args.genome is None:
            if constants.default_assembly_key in self.cravat_conf:
                self.input_assembly = self.cravat_conf[constants.default_assembly_key]
            else:
                msg = "Genome assembly should be given (as one of {}) with -l option or a default genome assembly should be defined in {} as default_assembly.".format(", ".join(constants.assembly_choices), constants.main_conf_path,)
                print(msg)
                exit()
        else:
            self.input_assembly = self.args.genome

    def set_start_end_levels(self):
        if self.append_mode and self.args.endat is None:
            self.args.endat = "aggregator"
        try:
            self.startlevel = self.runlevels[self.args.startat]
        except KeyError:
            self.startlevel = 0
        try:
            self.endlevel = self.runlevels[self.args.endat]
        except KeyError:
            self.endlevel = max(self.runlevels.values())

    def make_args_namespace(self, supplied_args):
        self.set_package_conf(supplied_args)
        self.make_self_args_considering_package_conf(supplied_args)
        if self.args.show_version:
            au.show_cravat_version()
            exit()
        self.set_self_inputs()
        self.set_output_dir()
        self.set_run_name()
        self.set_append_mode()
        if self.args.skip is None:
            self.args.skip = []
        self.set_md()
        self.set_mapper()
        self.set_annotators()
        self.set_postaggregators()
        self.set_reporters()
        self.verbose = self.args.verbose == True
        self.set_genome_assembly()
        self.set_start_end_levels()
        self.cleandb = self.args.cleandb
        if self.args.note == None:
            self.args.note = ""

    def set_md(self):
        if self.args.md is not None:
            constants.custom_modules_dir = self.args.md

    def set_annotators(self):
        self.excludes = self.args.excludes
        if len(self.args.annotators) > 0:
            if self.args.annotators == ["all"]:
                self.annotator_names = sorted(list(au.get_local_module_infos_of_type("annotator").keys()))
            else:
                self.annotator_names = self.args.annotators
        elif self.package_conf is not None and "run" in self.package_conf and "annotators" in self.package_conf["run"]:
            self.annotator_names = self.package_conf["run"]["annotators"]
        else:
            self.annotator_names = []
        if "annotator" in self.args.skip:
            self.annotator_names = []
        elif len(self.excludes) > 0:
            if "all" in self.excludes:
                self.annotator_names = []
            else:
                for m in self.excludes:
                    if m in self.annotator_names:
                        self.annotator_names.remove(m)
        self.check_valid_modules(self.annotator_names)
        self.annotators = au.get_local_module_infos_by_names(self.annotator_names)

    def set_mapper(self):
        if len(self.args.mapper_name) > 0:
            self.mapper_name = self.args.mapper_name[0]
        elif self.package_conf is not None and "run" in self.package_conf and "mapper" in self.package_conf["run"]:
            self.mapper_name = self.package_conf["run"]["mapper"]
        else:
            self.mapper_name = self.conf.get_cravat_conf()["genemapper"]
        self.check_valid_modules([self.mapper_name])
        self.mapper = au.get_local_module_info_by_name(self.mapper_name)

    def set_postaggregators(self):
        if len(self.args.postaggregators) > 0:
            self.postaggregator_names = self.args.postaggregators
        elif self.package_conf is not None and "run" in self.package_conf and "postaggregators" in self.package_conf["run"]:
            self.postaggregator_names = sorted(list(au.get_local_module_infos_by_names(self.package_conf["run"]["postaggregators"])))
        else:
            self.postaggregator_names = []
        if "postaggregator" in self.args.skip:
            self.postaggregators = {}
        else:
            self.postaggregator_names = sorted(list(set(self.postaggregator_names).union(set(constants.default_postaggregator_names))))
            if 'casecontrol' in self.postaggregator_names:
                if au.module_exists_local('casecontrol') == False:
                    self.postaggregator_names.remove('casecontrol')
            self.check_valid_modules(self.postaggregator_names)
            self.postaggregators = au.get_local_module_infos_by_names(self.postaggregator_names)

    def set_reporters(self):
        if len(self.args.reports) > 0:
            self.report_names = self.args.reports
        elif self.package_conf is not None and "run" in self.package_conf and "reports" in self.package_conf["run"]:
            self.report_names = self.package_conf["run"]["reports"]
        else:
            self.report_names = []
        if "reporter" in self.args.skip:
            self.reports = {}
        else:
            self.reporter_names = [v + 'reporter' for v in self.report_names]
            self.check_valid_modules(self.reporter_names)
            self.reports = au.get_local_module_infos_by_names(self.reporter_names)

    def set_and_check_input_files(self):
        self.crvinput = os.path.join(self.output_dir, self.run_name + ".crv")
        self.crxinput = os.path.join(self.output_dir, self.run_name + ".crx")
        self.crginput = os.path.join(self.output_dir, self.run_name + ".crg")
        if os.path.exists(self.crvinput):
            self.crv_present = True
        else:
            self.crv_present = False
        if os.path.exists(self.crxinput):
            self.crx_present = True
        else:
            self.crx_present = False
        if os.path.exists(self.crginput):
            self.crg_present = True
        else:
            self.crg_present = False

        if self.append_mode:
            self.regenerate_from_db()

    def regenerate_from_db(self):
        dbpath = self.inputs[0]
        db = sqlite3.connect(dbpath)
        c = db.cursor()
        # Variant
        if not self.crv_present:
            crv = CravatWriter(self.crvinput, columns=constants.crv_def)
            crv.write_definition()
        else:
            crv = None
        if not self.crx_present:
            crx = CravatWriter(self.crxinput, columns=constants.crx_def)
            crx.write_definition()
        else:
            crx = None
        if crv or crx:
            colnames = [x["name"] for x in constants.crx_def]
            sel_cols = ", ".join(["base__" + x for x in colnames])
            q = f"select {sel_cols} from variant"
            c.execute(q)
            for r in c:
                rd = {x[0]: x[1] for x in zip(colnames, r)}
                if crv:
                    crv.write_data(rd)
                if crx:
                    crx.write_data(rd)
            if crv:
                crv.close()
            if crx:
                crx.close()
            self.crv_present = True
            self.crx_present = True
        # Gene
        if not self.crg_present:
            crg = CravatWriter(self.crginput, columns=constants.crg_def)
            crg.write_definition()
            colnames = [x["name"] for x in constants.crg_def]
            sel_cols = ", ".join(["base__" + x for x in colnames])
            q = f"select {sel_cols} from gene"
            c.execute(q)
            for r in c:
                rd = {x[0]: x[1] for x in zip(colnames, r)}
                crg.write_data(rd)
            crg.close()
            self.crg_present = True
        c.close()
        db.close()

    def populate_secondary_annotators(self):
        secondaries = {}
        for module in self.annotators.values():
            self._find_secondary_annotators(module, secondaries)
        self.annotators.update(secondaries)
        annot_names = [v.name for v in self.annotators.values()]
        annot_names = list(set(annot_names))
        filenames = os.listdir(self.output_dir)
        for filename in filenames:
            toks = filename.split(".")
            if len(toks) == 3:
                extension = toks[2]
                if toks[0] == self.run_name and (
                    extension == "var" or extension == "gen"
                ):
                    annot_name = toks[1]
                    if annot_name not in annot_names:
                        annot_names.append(annot_name)
        annot_names.sort()
        if self.startlevel <= self.runlevels["annotator"]:
            self.status_writer.queue_status_update(
                "annotators", annot_names, force=True
            )
        self.annot_names = annot_names

    def _find_secondary_annotators(self, module, ret):
        sannots = self.get_secondary_modules(module)
        for sannot in sannots:
            ret[sannot.name] = sannot
            self._find_secondary_annotators(sannot, ret)

    def get_module_output_path(self, module):
        if module.level == "variant":
            postfix = ".var"
        elif module.level == "gene":
            postfix = ".gen"
        else:
            return None
        path = os.path.join(
            self.output_dir, self.run_name + "." + module.name + postfix
        )
        return path

    def check_module_output(self, module):
        path = self.get_module_output_path(module)
        if os.path.exists(path):
            return path
        else:
            None

    def get_secondary_modules(self, primary_module):
        secondary_modules = [
            au.get_local_module_info(module_name)
            for module_name in primary_module.secondary_module_names
        ]
        return secondary_modules

    def run_converter(self):
        converter_path = os.path.join(os.path.dirname(__file__), "cravat_convert.py")
        module = SimpleNamespace(
            title="Converter", name="converter", script_path=converter_path
        )
        arg_dict = {
            "path": module.script_path,
            "inputs": self.inputs,
            "name": self.run_name,
            "output_dir": self.output_dir,
            "genome": self.input_assembly,
        }
        arg_dict["conf"] = {}
        for mn in self.conf._all:
            if mn.endswith("-converter"):
                arg_dict["conf"][mn] = self.conf._all[mn]
        if "run" in self.conf._all:
            for mn in self.conf._all["run"]:
                if mn.endswith("-converter"):
                    arg_dict["conf"][mn] = self.conf._all[mn]
        if module.name in self.cravat_conf:
            if module.name in self.modules_conf:
                confs = json.dumps(self.modules_conf[module.name])
                confs = "'" + confs.replace("'", '"') + "'"
                arg_dict["confs"] = confs
        if self.args.forcedinputformat is not None:
            arg_dict["format"] = self.args.forcedinputformat
        if self.args.unique_variants:
            arg_dict["unique_variants"] = True
        self.announce_module(module)
        if self.verbose:
            if not self.args.silent:
                print(" ".join([str(k) + "=" + str(v) for k, v in arg_dict.items()]))
        arg_dict["status_writer"] = self.status_writer
        converter_class = util.load_class(module.script_path, "MasterCravatConverter")
        converter = converter_class(arg_dict)
        self.numinput, self.converter_format = converter.run()

    def run_genemapper(self):
        module = au.get_local_module_info(self.cravat_conf["genemapper"])
        self.genemapper = module
        cmd = [
            module.script_path,
            self.crvinput,
            "-n",
            self.run_name,
            "-d",
            self.output_dir,
        ]
        if self.args.primary_transcript is not None:
            if "mane" not in self.args.primary_transcript:
                self.args.primary_transcript.append("mane")
            cmd.extend(["--primary-transcript"])
            cmd.extend(self.args.primary_transcript)
        if module.name in self.cravat_conf:
            confs = json.dumps(self.cravat_conf[module.name])
            confs = "'" + confs.replace("'", '"') + "'"
            cmd.extend(["--confs", confs])
        if self.verbose:
            if not self.args.silent:
                print(" ".join(cmd))
        genemapper_class = util.load_class(module.script_path, "Mapper")
        genemapper = genemapper_class(cmd, self.status_writer)
        genemapper.run()

    def run_genemapper_mp(self):
        num_workers = au.get_max_num_concurrent_annotators_per_job()
        if self.args.mp is not None:
            try:
                self.args.mp = int(self.args.mp)
                if self.args.mp >= 1:
                    num_workers = self.args.mp
            except:
                self.logger.exception("error handling mp argument:")
        self.logger.info("num_workers: {}".format(num_workers))
        reader = CravatReader(self.crvinput)
        num_lines, chunksize, poss, len_poss, max_num_lines = reader.get_chunksize(
            num_workers
        )
        self.logger.info(
            f"input line chunksize={chunksize} total number of input lines={num_lines} number of chunks={len_poss}"
        )
        pool = mp.Pool(num_workers, init_worker)
        pos_no = 0
        while pos_no < len_poss:
            jobs = []
            for i in range(num_workers):
                if pos_no == len_poss:
                    break
                (seekpos, num_lines) = poss[pos_no]
                if pos_no == len_poss - 1:
                    job = pool.apply_async(
                        mapper_runner,
                        (
                            self.crvinput,
                            seekpos,
                            max_num_lines - num_lines,
                            self.run_name,
                            self.output_dir,
                            self.status_writer,
                            self.mapper_name,
                            pos_no,
                            ";".join(self.args.primary_transcript),
                        ),
                    )
                else:
                    job = pool.apply_async(
                        mapper_runner,
                        (
                            self.crvinput,
                            seekpos,
                            chunksize,
                            self.run_name,
                            self.output_dir,
                            self.status_writer,
                            self.mapper_name,
                            pos_no,
                            ";".join(self.args.primary_transcript),
                        ),
                    )
                jobs.append(job)
                pos_no += 1
            for job in jobs:
                job.get()
        pool.close()
        # collects crx.
        crx_path = os.path.join(self.output_dir, f"{self.run_name}.crx")
        wf = open(crx_path, "w")
        fns = sorted(glob.glob(glob.escape(crx_path) + "[.]*"))
        fn = fns[0]
        f = open(fn)
        for line in f:
            wf.write(line)
        f.close()
        os.remove(fn)
        for fn in fns[1:]:
            f = open(fn)
            for line in f:
                if line[0] != "#":
                    wf.write(line)
            f.close()
            os.remove(fn)
        wf.close()
        # collects crg.
        crg_path = os.path.join(self.output_dir, f"{self.run_name}.crg")
        wf = open(crg_path, "w")
        unique_hugos = {}
        fns = sorted(glob.glob(glob.escape(crg_path) + "[.]*"))
        fn = fns[0]
        f = open(fn)
        for line in f:
            if line[0] != "#":
                hugo = line.split()[0]
                if hugo not in unique_hugos:
                    # wf.write(line)
                    unique_hugos[hugo] = line
            else:
                wf.write(line)
        f.close()
        os.remove(fn)
        for fn in fns[1:]:
            f = open(fn)
            for line in f:
                if line[0] != "#":
                    hugo = line.split()[0]
                    if hugo not in unique_hugos:
                        # wf.write(line)
                        unique_hugos[hugo] = line
            f.close()
            os.remove(fn)
        hugos = list(unique_hugos.keys())
        hugos.sort()
        for hugo in hugos:
            wf.write(unique_hugos[hugo])
        wf.close()
        del unique_hugos
        del hugos
        # collects crt.
        crt_path = os.path.join(self.output_dir, f"{self.run_name}.crt")
        """
        wf = open(crt_path, 'w')
        """
        unique_trs = {}
        fns = sorted(glob.glob(glob.escape(crt_path) + "[.]*"))
        fn = fns[0]
        """
        f = open(fn)
        for line in f:
            if line[0] != '#':
                [tr, alt] = line.split()[:1]
                if tr not in unique_trs:
                    unique_trs[tr] = {}
                if alt not in unique_trs[tr]:
                    unique_trs[tr][alt] = True
                    wf.write(line)
            else:
                wf.write(line)
        f.close()
        """
        os.remove(fn)
        for fn in fns[1:]:
            """
            f = open(fn)
            for line in f:
                if line[0] != '#':
                    [tr, alt] = line.split()[:1]
                    if tr not in unique_trs:
                        unique_trs[tr] = {}
                    if alt not in unique_trs[tr]:
                        unique_trs[tr][alt] = True
                        wf.write(line)
            f.close()
            """
            os.remove(fn)
        wf.close()
        del unique_trs

    def run_aggregator(self):
        # Variant level
        if not self.args.silent:
            print("\t{0:30s}\t".format("Variants"), end="", flush=True)
        stime = time.time()
        cmd = [
            "donotremove",
            "-i",
            self.output_dir,
            "-d",
            self.output_dir,
            "-l",
            "variant",
            "-n",
            self.run_name,
        ]
        if self.cleandb:
            cmd.append("-x")
        if self.append_mode:
            cmd.append("--append")
        if self.verbose:
            if not self.args.silent:
                print(" ".join(cmd))
        self.update_status(
            "Running {title} ({level})".format(title="Aggregator", level="variant"),
            force=True
        )
        v_aggregator = Aggregator(cmd, self.status_writer)
        v_aggregator.run()
        rtime = time.time() - stime
        if not self.args.silent:
            print("finished in {0:.3f}s".format(rtime))

        # Gene level
        if not self.args.silent:
            print("\t{0:30s}\t".format("Genes"), end="", flush=True)
        stime = time.time()
        cmd = [
            "donotremove",
            "-i",
            self.output_dir,
            "-d",
            self.output_dir,
            "-l",
            "gene",
            "-n",
            self.run_name,
        ]
        if self.append_mode:
            cmd.append("--append")
        if self.verbose:
            if not self.args.silent:
                print(" ".join(cmd))
        self.update_status(
            "Running {title} ({level})".format(title="Aggregator", level="gene"),
            force=True
        )
        g_aggregator = Aggregator(cmd, self.status_writer)
        g_aggregator.run()
        rtime = time.time() - stime
        if not self.args.silent:
            print("finished in {0:.3f}s".format(rtime))

        # Sample level
        if not self.append_mode:
            if not self.args.silent:
                print("\t{0:30s}\t".format("Samples"), end="", flush=True)
            stime = time.time()
            cmd = [
                "donotremove",
                "-i",
                self.output_dir,
                "-d",
                self.output_dir,
                "-l",
                "sample",
                "-n",
                self.run_name,
            ]
            if self.verbose:
                if not self.args.silent:
                    print(" ".join(cmd))
            self.update_status(
                "Running {title} ({level})".format(
                    title="Aggregator", level="sample"
                ), force=True
            )
            s_aggregator = Aggregator(cmd, self.status_writer)
            s_aggregator.run()
            rtime = time.time() - stime
            if not self.args.silent:
                print("finished in {0:.3f}s".format(rtime))

        # Mapping level
        if not self.append_mode:
            if not self.args.silent:
                print("\t{0:30s}\t".format("Tags"), end="", flush=True)
            cmd = [
                "donotremove",
                "-i",
                self.output_dir,
                "-d",
                self.output_dir,
                "-l",
                "mapping",
                "-n",
                self.run_name,
            ]
            if self.verbose:
                if not self.args.silent:
                    print(" ".join(cmd))
            self.update_status(
                "Running {title} ({level})".format(
                    title="Aggregator", level="mapping"
                ), force=True
            )
            m_aggregator = Aggregator(cmd, self.status_writer)
            m_aggregator.run()
            rtime = time.time() - stime
            if not self.args.silent:
                print("finished in {0:.3f}s".format(rtime))

        return v_aggregator.db_path

    def run_postaggregators(self):
        for module_name, module in self.postaggregators.items():
            cmd = [module.script_path, "-d", self.output_dir, "-n", self.run_name]
            postagg_conf = {}
            if module.name in self.cravat_conf:
                postagg_conf.update(self.cravat_conf[module_name])
            if module_name in self.conf._all:
                postagg_conf.update(self.conf._all[module_name])
            elif "run" in self.conf._all and module_name in self.conf._all["run"]:
                postagg_conf.update(self.conf._all["run"][module_name])
            if postagg_conf:
                confs = json.dumps(postagg_conf)
                confs = "'" + confs.replace("'", '"') + "'"
                cmd.extend(["--confs", confs])
            if self.verbose:
                if not self.args.silent:
                    print(" ".join(cmd))
            post_agg_cls = util.load_class(module.script_path, "CravatPostAggregator")
            post_agg = post_agg_cls(cmd, self.status_writer)
            if post_agg.should_run_annotate:
                self.announce_module(module)
            stime = time.time()
            post_agg.run()
            rtime = time.time() - stime
            if not self.args.silent and post_agg.should_run_annotate:
                print("finished in {0:.3f}s".format(rtime))

    async def run_reporter(self):
        if len(self.reports) > 0:
            module_names = [v for v in list(self.reports.keys())]
        else:
            if "reporter" in self.cravat_conf:
                module_names = [self.cravat_conf["reporter"]]
            else:
                module_names = []
        all_reporters_ran_well = True
        response = {}
        for module_name in module_names:
            try:
                module = au.get_local_module_info(module_name)
                self.announce_module(module)
                if module is None:
                    if not self.args.silent:
                        print("        {} does not exist.".format(module_name))
                    continue
                arg_dict = {
                    "script_path": module.script_path,
                    "dbpath": os.path.join(self.output_dir, self.run_name + ".sqlite"),
                    "savepath": os.path.join(self.output_dir, self.run_name),
                    "output_dir": self.output_dir,
                    "module_name": module_name,
                }
                if self.run_conf_path is not None:
                    arg_dict["confpath"] = self.run_conf_path
                if module_name in self.conf._all:
                    arg_dict["conf"] = self.conf._all[module_name]
                elif "run" in self.conf._all and module_name in self.conf._all["run"]:
                    arg_dict["conf"] = self.conf._all["run"][module_name]
                if self.pipeinput == False:
                    arg_dict["inputfiles"] = []
                    for input_file in self.inputs:
                        arg_dict["inputfiles"].append(f"{input_file}")
                if self.args.separatesample:
                    arg_dict["separatesample"] = True
                if self.verbose:
                    if not self.args.silent:
                        print(
                            " ".join(
                                [str(k) + "=" + str(v) for k, v in arg_dict.items()]
                            )
                        )
                arg_dict["status_writer"] = self.status_writer
                arg_dict["reporttypes"] = [module_name.replace("reporter", "")]
                arg_dict["concise_report"] = self.args.concise_report
                arg_dict["package"] = self.args.package
                arg_dict["filtersql"] = self.args.filtersql
                arg_dict['includesample'] = self.args.includesample
                arg_dict['excludesample'] = self.args.excludesample
                arg_dict["filter"] = self.args.filter
                arg_dict["filterpath"] = self.args.filterpath
                Reporter = util.load_class(module.script_path, "Reporter")
                reporter = Reporter(arg_dict)
                await reporter.prep()
                stime = time.time()
                response_t = await reporter.run()
                output_fns = None
                if self.args.silent == False:
                    response_type = type(response_t)
                    if response_type == list:
                        output_fns = " ".join(response_t)
                    elif response_type == str:
                        output_fns = response_t
                    if output_fns is not None:
                        print(f"report created: {output_fns} ", end="", flush=True)
                response[re.sub("reporter$", "", module_name)] = response_t
                rtime = time.time() - stime
                if not self.args.silent:
                    print("finished in {0:.3f}s".format(rtime))
            except Exception as e:
                if hasattr(e, "handled") and e.handled == True:
                    pass
                else:
                    if not hasattr(e, "notraceback") or e.notraceback != True:
                        import traceback
                        traceback.print_exc()
                        self.logger.exception(e)
                    else:
                        print(e)
                        if hasattr(self, "logger"):
                            write_log_msg(self.logger, e)
                    if "reporter" in locals() and hasattr(reporter, 'close_db'):
                        await reporter.close_db()
                all_reporters_ran_well = False
        return all_reporters_ran_well, response

    def run_annotators_mp(self):
        """
        Run annotators in multiple worker processes.
        """
        # Determine number of worker processes
        num_workers = au.get_max_num_concurrent_annotators_per_job()
        if self.args.mp is not None:
            try:
                self.args.mp = int(self.args.mp)
                if self.args.mp >= 1:
                    num_workers = self.args.mp
            except:
                self.logger.exception("error handling mp argument:")
        self.logger.info("num_workers: {}".format(num_workers))
        # Create arguments for each annotator
        run_args = {}
        for module in self.run_annotators.values():
            # Select correct input file for annotator
            if module.level == "variant":
                if "input_format" in module.conf:
                    input_format = module.conf["input_format"]
                    if input_format == "crv":
                        inputpath = self.crvinput
                    elif input_format == "crx":
                        inputpath = self.crxinput
                    else:
                        raise Exception("Incorrect input_format value")
                else:
                    inputpath = self.crvinput
            elif module.level == "gene":
                inputpath = self.crginput
            # Assign secondary inputs from sub-annotators
            secondary_inputs = []
            if "secondary_inputs" in module.conf:
                secondary_module_names = module.conf["secondary_inputs"]
                for secondary_module_name in secondary_module_names:
                    secondary_module = self.annotators[secondary_module_name]
                    secondary_output_path = self.get_module_output_path(
                        secondary_module
                    )
                    secondary_inputs.append(
                        secondary_module.name.replace("=", r"\=")
                        + "="
                        + os.path.join(self.output_dir, secondary_output_path).replace(
                            "=", r"\="
                        )
                    )
            # Assemble argument dictionary
            kwargs = {
                "script_path": module.script_path,
                "input_file": inputpath,
                "secondary_inputs": secondary_inputs,
                "silent": self.args.silent,
                "log_path": self.log_path,
            }
            if self.run_name != None:
                kwargs["run_name"] = self.run_name
            if self.output_dir != None:
                kwargs["output_dir"] = self.output_dir
            if module.name in self.cravat_conf:
                kwargs["conf"] = self.cravat_conf[module.name]
            run_args[module.name] = (module, kwargs)
        # Run annotator workers
        # Annotator workers receive annotators to run in start_queue. When an 
        # annotator is finished, it's name is placed in end_queue. This process
        # schedules annotators to run by placing them in start_queue. Annotators
        # that depend on other annotators results are not placed in start_queue 
        # until the dependent annotators are finished. When all annotators have 
        # been placed in start_queue, the queue_populated semaphore is set to 
        # True. Once queue_populated is True and start_queue is empty, the 
        # workers will exit. 
        self.logger.removeHandler(self.log_handler)
        start_queue = self.manager.Queue()
        end_queue = self.manager.Queue()
        all_mnames = set(self.run_annotators)
        queued_mnames = set()
        done_mnames = set(self.done_annotators)
        queue_populated = self.manager.Value("c_bool", False)
        pool_args = [
            [start_queue, end_queue, queue_populated, self.status_writer]
        ] * num_workers
        with mp.Pool(num_workers, init_worker) as pool:
            results = pool.starmap_async(
                annot_from_queue,
                pool_args,
                error_callback=lambda e, mp_pool=pool: mp_pool.terminate(),
            )
            pool.close()
            for mname, module in self.run_annotators.items():
                annotator_not_queue = mname not in queued_mnames
                secondaries_done = set(module.secondary_module_names) <= done_mnames
                if (annotator_not_queue and secondaries_done):
                    start_queue.put(run_args[mname])
                    queued_mnames.add(mname)
            # Loop until all annotators are put in start_queue
            # TODO not handling case where parent annotator errors out
            while (queued_mnames != all_mnames):  
                # Block until item availble in end_queue
                finished_module = end_queue.get()
                done_mnames.add(finished_module)
                # Queue any annotators that now have requirements complete
                for mname, module in self.run_annotators.items():
                    annotator_not_queue = mname not in queued_mnames
                    secondaries_done = set(module.secondary_module_names) <= done_mnames
                    if (annotator_not_queue and secondaries_done):
                        start_queue.put(run_args[mname])
                        queued_mnames.add(mname)
            queue_populated = True
            pool.join()
        self.log_path = os.path.join(self.output_dir, self.run_name + ".log")
        self.log_handler = logging.FileHandler(self.log_path, "a")
        formatter = logging.Formatter(
            "%(asctime)s %(name)-20s %(message)s", "%Y/%m/%d %H:%M:%S"
        )
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
        if len(self.run_annotators) > 0:
            self.annotator_ran = True

    def table_exists(self, cursor, table):
        sql = (
            'select name from sqlite_master where type="table" and '
            + 'name="'
            + table
            + '"'
        )
        cursor.execute(sql)
        if cursor.fetchone() == None:
            return False
        else:
            return True

    async def get_converter_format_from_crv(self):
        converter_format = None
        fn = os.path.join(self.output_dir, self.run_name + ".crv")
        if os.path.exists(fn):
            f = open(fn)
            for line in f:
                if line.startswith("#input_format="):
                    converter_format = line.strip().split("=")[1]
                    break
            f.close()
        return converter_format

    async def get_mapper_info_from_crx(self):
        title = None
        version = None
        modulename = None
        fn = os.path.join(self.output_dir, self.run_name + ".crx")
        if os.path.exists(fn):
            f = open(fn)
            for line in f:
                if line.startswith("#title="):
                    title = line.strip().split("=")[1]
                elif line.startswith("#version="):
                    version = line.strip().split("=")[1]
                elif line.startswith("#modulename="):
                    modulename = line.strip().split("=")[1]
                elif line.startswith("#") == False:
                    break
            f.close()
        return title, version, modulename

    async def write_job_info(self):
        dbpath = os.path.join(self.output_dir, self.run_name + ".sqlite")
        conn = await aiosqlite.connect(dbpath)
        cursor = await conn.cursor()
        if not self.append_mode:
            q = "drop table if exists info"
            await cursor.execute(q)
            q = "create table info (colkey text primary key, colval text)"
            await cursor.execute(q)
        modified = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        q = (
            'insert or replace into info values ("Result modified at", "'
            + modified
            + '")'
        )
        await cursor.execute(q)
        if not self.append_mode:
            created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            q = 'insert into info values ("Result created at", "' + created + '")'
            await cursor.execute(q)
            q = 'insert into info values ("Input file name", "{}")'.format(
                ";".join(self.inputs)
            )
            await cursor.execute(q)
            q = (
                'insert into info values ("Input genome", "'
                + self.input_assembly
                + '")'
            )
            await cursor.execute(q)
            q = "select count(*) from variant"
            await cursor.execute(q)
            r = await cursor.fetchone()
            no_input = str(r[0])
            q = (
                'insert into info values ("Number of unique input variants", "'
                + no_input
                + '")'
            )
            await cursor.execute(q)
            q = 'insert into info values ("open-cravat", "{}")'.format(self.pkg_ver)
            await cursor.execute(q)
            q = 'insert into info values ("_converter_format", "{}")'.format(
                await self.get_converter_format_from_crv()
            )
            await cursor.execute(q)
            (
                mapper_title,
                mapper_version,
                mapper_modulename,
            ) = await self.get_mapper_info_from_crx()
            genemapper_str = "{} ({})".format(mapper_title, mapper_version)
            q = 'insert into info values ("Gene mapper", "{}")'.format(genemapper_str)
            await cursor.execute(q)
            q = 'insert into info values ("_mapper", "{}:{}")'.format(
                mapper_modulename, mapper_version
            )
            await cursor.execute(q)
            f = open(os.path.join(self.output_dir, self.run_name + ".crm"))
            for line in f:
                if line.startswith("#input_paths="):
                    input_path_dict_str = "=".join(line.strip().split("=")[1:]).replace(
                        '"', "'"
                    )
                    q = 'insert into info values ("_input_paths", "{}")'.format(
                        input_path_dict_str
                    )
                    await cursor.execute(q)
            q = f'insert into info values ("primary_transcript", "{",".join(self.args.primary_transcript)}")'
            await cursor.execute(q)
        q = 'select colval from info where colkey="annotators_desc"'
        await cursor.execute(q)
        r = await cursor.fetchone()
        if r is None:
            annotator_desc_dict = {}
        else:
            annotator_desc_dict = json.loads(r[0])
        q = "select name, displayname, version from variant_annotator"
        await cursor.execute(q)
        rows = list(await cursor.fetchall())
        q = "select name, displayname, version from gene_annotator"
        await cursor.execute(q)
        tmp_rows = list(await cursor.fetchall())
        if tmp_rows is not None:
            rows.extend(tmp_rows)
        annotators_str = ""
        annotator_version = {}
        annotators = []
        for row in rows:
            (name, displayname, version) = row
            if name in ["base", "tagsampler", "hg19", "hg18"]:
                continue
            if version is not None and version != "":
                annotators_str += "{} ({}), ".format(displayname, version)
                annotators.append("{}:{}".format(name, version))
            else:
                annotators_str += "{}, ".format(displayname)
                annotators.append("{}:".format(name))
            annotator_version[name] = version
            module_info = au.get_local_module_info(name)
            if module_info is not None and module_info.conf is not None:
                annotator_desc_dict[name] = module_info.conf["description"]
        q = 'insert or replace into info values ("_annotator_desc", "{}")'.format(
            json.dumps(annotator_desc_dict).replace('"', "'")
        )
        await cursor.execute(q)
        if self.args.do_not_change_status != True:
            self.status_writer.queue_status_update(
                "annotator_version", annotator_version, force=True
            )
        q = (
            'insert or replace into info values ("Annotators", "'
            + annotators_str
            + '")'
        )
        await cursor.execute(q)
        q = 'insert or replace into info values ("_annotators", "{}")'.format(
            ",".join(annotators)
        )
        await cursor.execute(q)
        await conn.commit()
        await cursor.close()
        await conn.close()

    def run_summarizers(self):
        for module in self.ordered_summarizers:
            self.announce_module(module)
            self.run_summarizer(module)

    def run_summarizer(self, module):
        cmd = [module.script_path, "-l", "variant"]
        if self.run_name != None:
            cmd.extend(["-n", self.run_name])
        if self.output_dir != None:
            cmd.extend(["-d", self.output_dir])
        if self.verbose:
            if not self.args.silent:
                print(" ".join(cmd))
        summarizer_cls = util.load_class(module.script_path, "")
        summarizer = summarizer_cls(cmd)
        summarizer.run()

    def announce_module(self, module):
        if not self.args.silent:
            print(
                "\t{0:30s}\t".format(module.title + " (" + module.name + ")"),
                end="",
                flush=True,
            )
        self.update_status(
            "Running {title} ({name})".format(title=module.title, name=module.name),
            force=True
        )

    def clean_up_at_end(self):
        fns = os.listdir(self.output_dir)
        for fn in fns:
            fn_path = os.path.join(self.output_dir, fn)
            if os.path.isfile(fn_path) == False:
                continue
            if fn.startswith(self.run_name):
                fn_end = fn.split(".")[-1]
                if fn_end in ["var", "gen", "crv", "crx", "crg", "crs", "crm", "crt"]:
                    os.remove(os.path.join(self.output_dir, fn))
                if fn.split(".")[-2:] == ["status", "json"]:
                    os.remove(os.path.join(self.output_dir, fn))


class StatusWriter:
    def __init__(self, status_json_path):
        self.status_json_path = status_json_path
        self.status_queue = []
        self.load_status_json()
        self.t = time.time()
        self.lock = False

    def load_status_json(self):
        f = open(self.status_json_path)
        lines = "\n".join(f.readlines())
        self.status_json = json.loads(lines)
        f.close()

    def queue_status_update(self, k, v, force=False):
        self.status_json[k] = v
        tdif = time.time() - self.t
        if force == True or (tdif > 3 and self.lock == False):
            self.lock = True
            self.update_status_json()
            self.t = time.time()
            self.lock = False

    def update_status_json(self):
        with open(self.status_json_path, "w") as wf:
            json.dump(self.status_json, wf, indent=2, sort_keys=True)

    def get_status_json(self):
        return self.status_json

    def flush(self):
        self.lock = True
        self.update_status_json()
        self.t = time.time()
        self.lock = False
