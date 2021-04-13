import os
import traceback
import argparse
import logging
import time
from .inout import CravatReader, CravatWriter, AllMappingsParser
from .constants import (
    crx_def,
    crx_idx,
    crg_def,
    crg_idx,
    crt_def,
    crt_idx,
    gene_level_so_exclude,
)
from .exceptions import InvalidData, NoVariantError
from cravat.config_loader import ConfigLoader
import sys
import pkg_resources
import json
import cravat.cravat_util as cu
from types import SimpleNamespace
import multiprocessing as mp
import cravat.admin_util as au
import time
import cravat.util


class BaseMapper(object):
    """
    BaseMapper is the parent class for Cravat Mapper objects.
    It receives a crv file and writes crx and crg files based on it's child
    mapper's map() function.
    It handles command line arguments, option parsing and file io for the
    mapping process.
    """

    def __init__(self, *inargs, **inkwargs):
        self.cmd_parser = None
        self.input_path = None
        self.input_dir = None
        self.reader = None
        self.output_dir = None
        self.output_base_fname = None
        self.crx_path = None
        self.crg_path = None
        self.crt_path = None
        self.crx_writer = None
        self.crg_writer = None
        self.crt_writer = None
        self._define_main_cmd_args()
        self._define_additional_cmd_args()
        self._parse_cmd_args(inargs, inkwargs)
        if hasattr(self.args, "status_writer") == False:
            status_writer = None
        else:
            status_writer = self.args.status_writer
        if hasattr(self.args, "live") == False:
            live = False
        else:
            live = self.args.live
        self.live = live
        self.t = time.time()
        self.status_writer = status_writer
        main_fpath = self.args.script_path
        main_basename = os.path.basename(main_fpath)
        if "." in main_basename:
            self.module_name = ".".join(main_basename.split(".")[:-1])
        else:
            self.module_name = main_basename
        self.module_dir = os.path.dirname(main_fpath)
        self.mapper_dir = os.path.dirname(main_fpath)
        self.gene_sources = []
        # self.primary_gene_source = None
        self.gene_info = {}
        # self.written_primary_transc = set([])
        self._setup_logger()
        config_loader = ConfigLoader()
        self.conf = config_loader.get_module_conf(self.module_name)
        self.cravat_version = pkg_resources.get_distribution("open-cravat").version

    def _define_main_cmd_args(self):
        self.cmd_parser = argparse.ArgumentParser()
        # self.cmd_parser.add_argument('path',
        #                            help='Path to this mapper\'s python module')
        self.cmd_parser.add_argument("input_file", help="Input crv file")
        self.cmd_parser.add_argument(
            "-n", dest="name", help="Name of job. " + "Default is input file name."
        )
        self.cmd_parser.add_argument(
            "-d",
            dest="output_dir",
            help="Output directory. " + "Default is input file directory.",
        )
        self.cmd_parser.add_argument(
            "--confs", dest="confs", default="{}", help="Configuration string"
        )
        self.cmd_parser.add_argument(
            "--seekpos", dest="seekpos", default=None, help=argparse.SUPPRESS
        )
        self.cmd_parser.add_argument(
            "--chunksize", dest="chunksize", default=None, help=argparse.SUPPRESS
        )
        self.cmd_parser.add_argument(
            "--slavemode",
            dest="slavemode",
            action="store_true",
            default=False,
            help=argparse.SUPPRESS,
        )
        self.cmd_parser.add_argument(
            "--postfix", dest="postfix", default="", help=argparse.SUPPRESS
        )
        self.cmd_parser.add_argument(
            "--primary-transcript",
            dest="primary_transcript",
            nargs="*",
            default=["mane"],
            help='"mane" for MANE transcripts as primary transcripts, or a path to a file of primary transcripts. MANE is default.',
        )

    def _define_additional_cmd_args(self):
        """This method allows sub-classes to override and provide addittional command line args"""
        pass

    def _parse_cmd_args(self, inargs, inkwargs):
        args = cravat.util.get_args(self.cmd_parser, inargs, inkwargs)
        self.input_path = os.path.abspath(args.input_file)
        self.input_dir, self.input_fname = os.path.split(self.input_path)
        if args.output_dir:
            self.output_dir = args.output_dir
        else:
            self.output_dir = self.input_dir
        if not (os.path.exists(self.output_dir)):
            os.makedirs(self.output_dir)
        if hasattr(args, "run_name"):
            self.output_base_fname = args.run_name
        else:
            self.output_base_fname = self.input_fname
        self.confs = None
        if args.confs is not None:
            confs = args.confs.lstrip("'").rstrip("'").replace("'", '"')
            self.confs = json.loads(confs)
        self.slavemode = args.slavemode
        self.postfix = args.postfix
        self.primary_transcript_paths = args.primary_transcript
        self.args = args

    def base_setup(self):
        self.setup()
        if self.live == False:
            self._setup_io()

    def setup(self):
        raise NotImplementedError("Mapper must have a setup() method.")

    def end(self):
        pass

    def _setup_logger(self):
        self.logger = logging.getLogger("cravat.mapper")
        self.logger.info("input file: %s" % self.input_path)
        self.error_logger = logging.getLogger("error.mapper")
        self.unique_excs = []

    def _setup_io(self):
        """
        Open input and output files
        Open CravatReader for crv input. Open  CravatWriters for crx, and crg
        output. Open plain file for err output.
        """
        # Reader
        if self.args.seekpos is not None and self.args.chunksize is not None:
            self.reader = CravatReader(
                self.input_path,
                seekpos=int(self.args.seekpos),
                chunksize=int(self.args.chunksize),
            )
        else:
            self.reader = CravatReader(self.input_path)
        # Various output files
        output_base_path = os.path.join(self.output_dir, self.output_base_fname)
        output_toks = self.output_base_fname.split(".")
        if output_toks[-1] == "crv":
            output_toks = output_toks[:-1]
        # .crx
        crx_fname = ".".join(output_toks) + ".crx"
        self.crx_path = os.path.join(self.output_dir, crx_fname)
        if self.slavemode:
            self.crx_path += self.postfix
        self.crx_writer = CravatWriter(self.crx_path)
        self.crx_writer.add_columns(crx_def)
        self.crx_writer.write_definition(self.conf)
        for index_columns in crx_idx:
            self.crx_writer.add_index(index_columns)
        self.crx_writer.write_meta_line("title", self.conf["title"])
        self.crx_writer.write_meta_line("version", self.conf["version"])
        self.crx_writer.write_meta_line("modulename", self.module_name)
        if self.primary_transcript_paths is None:
            self.crx_writer.write_meta_line("primary_transcript_paths", "")
        else:
            self.crx_writer.write_meta_line(
                "primary_transcript_paths", ",".join(self.primary_transcript_paths)
            )
        # .crg
        crg_fname = ".".join(output_toks) + ".crg"
        self.crg_path = os.path.join(self.output_dir, crg_fname)
        if self.slavemode:
            self.crg_path += self.postfix
        self.crg_writer = CravatWriter(self.crg_path)
        self.crg_writer.add_columns(crg_def)
        self.crg_writer.write_definition(self.conf)
        for index_columns in crg_idx:
            self.crg_writer.add_index(index_columns)
        # .crt
        crt_fname = ".".join(output_toks) + ".crt"
        self.crt_path = os.path.join(self.output_dir, crt_fname)
        if self.slavemode:
            self.crt_path += self.postfix
        self.crt_writer = CravatWriter(self.crt_path)
        self.crt_writer.add_columns(crt_def)
        self.crt_writer.write_definition()
        for index_columns in crt_idx:
            self.crt_writer.add_index(index_columns)

    def run(self):
        """
        Read crv file and use map() function to convert to crx dict. Write the
        crx dict to the crx file and add information in crx dict to gene_info
        """
        self.base_setup()
        start_time = time.time()
        self.logger.info("started: %s" % time.asctime(time.localtime(start_time)))
        if self.status_writer is not None:
            self.status_writer.queue_status_update(
                "status", "Started {} ({})".format(self.conf["title"], self.module_name)
            )
        count = 0
        last_status_update_time = time.time()
        crx_data = None
        output = {}
        for ln, line, crv_data in self.reader.loop_data():
            crx_data = None
            try:
                count += 1
                cur_time = time.time()
                if self.status_writer is not None:
                    if count % 10000 == 0 or cur_time - last_status_update_time > 3:
                        self.status_writer.queue_status_update(
                            "status", "Running gene mapper: line {}".format(count)
                        )
                        last_status_update_time = cur_time
                if crv_data["alt_base"] == "*":
                    crx_data = crv_data
                    crx_data["all_mappings"] = "{}"
                else:
                    crx_data = self.map(crv_data)
                # Skip cases where there was no change. Can result if ref_base not in original input
                if crx_data["ref_base"] == crx_data["alt_base"]:
                    continue
            except Exception as e:
                self._log_runtime_error(ln, line, e)
                continue
            if crx_data is not None:
                self.crx_writer.write_data(crx_data)
                self._add_crx_to_gene_info(crx_data)
        self._write_crg()
        stop_time = time.time()
        self.logger.info("finished: %s" % time.asctime(time.localtime(stop_time)))
        runtime = stop_time - start_time
        self.logger.info("runtime: %6.3f" % runtime)
        if self.status_writer is not None:
            self.status_writer.queue_status_update("status", "Finished gene mapper")
        self.end()
        return output

    def run_as_slave(self, pos_no):
        """
        Read crv file and use map() function to convert to crx dict. Write the
        crx dict to the crx file and add information in crx dict to gene_info
        """
        self.base_setup()
        start_time = time.time()
        tstamp = time.asctime(time.localtime(start_time))
        self.logger.info(f"started: {tstamp} | {self.args.seekpos}")
        if self.status_writer is not None:
            self.status_writer.queue_status_update(
                "status", "Started {} ({})".format(self.conf["title"], self.module_name)
            )
        count = 0
        last_status_update_time = time.time()
        crx_data = None
        for ln, line, crv_data in self.reader.loop_data():
            try:
                count += 1
                cur_time = time.time()
                if self.status_writer is not None:
                    if count % 10000 == 0 or cur_time - last_status_update_time > 3:
                        self.status_writer.queue_status_update(
                            "status", "Running gene mapper: line {}".format(count)
                        )
                        last_status_update_time = cur_time
                if crv_data["alt_base"] == "*":
                    crx_data = crv_data
                    crx_data["all_mappings"] = "{}"
                else:
                    crx_data = self.map(crv_data)
                if crx_data is None:
                    continue
            except Exception as e:
                self._log_runtime_error(ln, line, e)
            if crx_data is not None:
                self.crx_writer.write_data(crx_data)
                self._add_crx_to_gene_info(crx_data)
        self._write_crg()
        stop_time = time.time()
        tstamp = time.asctime(time.localtime(stop_time))
        self.logger.info(f"finished: {tstamp} | {self.args.seekpos}")
        runtime = stop_time - start_time
        self.logger.info("runtime: %6.3f" % runtime)
        self.end()

    def _write_to_crt(self, alt_transcripts):
        for primary, alts in alt_transcripts.items():
            if primary not in self.written_primary_transc:
                for alt in alts:
                    d = {"primary_transcript": primary, "alt_transcript": alt}
                    self.crt_writer.write_data(d)
                self.written_primary_transc.add(primary)

    def _add_crx_to_gene_info(self, crx_data):
        """
        Add information in a crx dict to persistent gene_info dict
        """
        tmap_json = crx_data["all_mappings"]
        # Return if no tmap
        if tmap_json == "":
            return
        tmap_parser = AllMappingsParser(tmap_json)
        for hugo in tmap_parser.get_genes():
            self.gene_info[hugo] = True

    def _write_crg(self):
        """
        Convert gene_info to crg dict and write to crg file
        """
        sorted_hugos = list(self.gene_info.keys())
        sorted_hugos.sort()
        for hugo in sorted_hugos:
            gene = self.gene_info[hugo]
            crg_data = {x["name"]: "" for x in crg_def}
            crg_data["hugo"] = hugo
            self.crg_writer.write_data(crg_data)

    def _log_runtime_error(self, ln, line, e):
        err_str = traceback.format_exc().rstrip()
        if err_str not in self.unique_excs:
            self.unique_excs.append(err_str)
            self.logger.error(err_str)
        self.error_logger.error(
            "\nLINE:{:d}\nINPUT:{}\nERROR:{}\n#".format(ln, line[:-1], str(e))
        )
        # if not(isinstance(e, InvalidData)):
        #     raise e

    async def get_gene_summary_data(self, cf):
        # print('            {}: started getting gene summary data'.format(self.module_name))
        t = time.time()
        hugos = await cf.exec_db(cf.get_filtered_hugo_list)
        # Below is to fix opening oc 1.8.0 jobs with oc 1.8.1.
        # TODO: Remove it after a while and add 1.8.0 to the db update chain in cravat_util.
        cols = [
            "base__" + coldef["name"]
            for coldef in crx_def
            if coldef["name"] != "cchange"
        ]
        cols.extend(["tagsampler__numsample"])
        data = {}
        t = time.time()
        rows = await cf.exec_db(cf.get_variant_data_for_cols, cols)
        rows_by_hugo = {}
        t = time.time()
        for row in rows:
            hugo = row[-1]
            if hugo not in rows_by_hugo:
                rows_by_hugo[hugo] = []
            rows_by_hugo[hugo].append(row)
        t = time.time()
        for hugo in hugos:
            rows = rows_by_hugo[hugo]
            input_data = {}
            for i in range(len(cols)):
                input_data[cols[i].split("__")[1]] = [row[i] for row in rows]
            out = self.summarize_by_gene(hugo, input_data)
            data[hugo] = out
        # print('            {}: finished getting gene summary data in {:0.3f}s'.format(self.module_name, time.time() - t))
        return data

    def live_report_substitute(self, d):
        import re

        if "report_substitution" not in self.conf:
            return
        rs_dic = self.conf["report_substitution"]
        rs_dic_keys = list(rs_dic.keys())
        for colname in d.keys():
            if colname in rs_dic_keys:
                value = d[colname]
                if colname in ["all_mappings", "all_so"]:
                    for target in list(rs_dic[colname].keys()):
                        value = re.sub(
                            "\\b" + target + "\\b", rs_dic[colname][target], value
                        )
                else:
                    if value in rs_dic[colname]:
                        value = rs_dic[colname][value]
                d[colname] = value
        return d
