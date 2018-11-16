import os
import traceback
import argparse
import logging
import time
from .inout import CravatReader, CravatWriter, AllMappingsParser
from .constants import crx_def, crx_idx, crg_def, crg_idx, crt_def, crt_idx
from .util import most_severe_so, so_severity
from .exceptions import InvalidData
from cravat.config_loader import ConfigLoader
import sys

class BaseMapper(object):
    """
    BaseMapper is the parent class for Cravat Mapper objects.
    
    It recieves a crv file and writes crx and crg files based on it's child
    mapper's map() function.
    
    It handles command line arguments, option parsing and file io for the
    mapping process.
    """
    def __init__(self, cmd_args):
        try:
            main_fpath = cmd_args[0]
            main_basename = os.path.basename(main_fpath)
            if '.' in main_basename:
                self.module_name = '.'.join(main_basename.split('.')[:-1])
            else:
                self.module_name = main_basename
            self.mapper_dir = os.path.dirname(main_fpath)
            self.cmd_parser = None
            self.cmd_args = None
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
            self.gene_sources = []
            self.primary_gene_source = None
            self.gene_info = {}
            self.written_primary_transc = set([])
            self._define_main_cmd_args()
            self._define_additional_cmd_args()
            self._parse_cmd_args(cmd_args)
            self._setup_logger()
            config_loader = ConfigLoader()
            self.conf = config_loader.get_module_conf(self.module_name)
        except Exception as e:
            self.__handle_exception(e)
            
    def _define_main_cmd_args(self):
        self.cmd_parser = argparse.ArgumentParser()
        self.cmd_parser.add_argument('path',
                                    help='Path to this mapper\'s python module')
        self.cmd_parser.add_argument('input',
                                     help='Input crv file')
        self.cmd_parser.add_argument('-n',
                                     dest='name',
                                     help='Name of job. '\
                                          +'Default is input file name.')
        self.cmd_parser.add_argument('-d',
                                     dest='output_dir',
                                     help='Output directory. '\
                                          +'Default is input file directory.')
    
    def _define_additional_cmd_args(self):
        """This method allows sub-classes to override and provide addittional command line args"""
        pass
    
    def _parse_cmd_args(self, args):
        self.cmd_args = self.cmd_parser.parse_args(args)
        self.input_path = os.path.abspath(self.cmd_args.input)
        self.input_dir, self.input_fname = os.path.split(self.input_path)
        if self.cmd_args.output_dir:
            self.output_dir = self.cmd_args.output_dir
        else:
            self.output_dir = self.input_dir
        if not(os.path.exists(self.output_dir)):
            os.makedirs(self.output_dir)
        if self.cmd_args.name:
            self.output_base_fname = self.cmd_args.name
        else:
            self.output_base_fname = self.input_fname

    def base_setup(self):
        self._setup_io()
        self.setup()
        
    def setup(self):
        raise NotImplementedError('Mapper must have a setup() method.')
    
    def __handle_exception(self, e, should_exit=True):
        """
        Handles exceptions in standard cravat method
        """
        sys.stderr.write(traceback.format_exc())
        if hasattr(self, 'logger') and self.logger is not None:
                self.logger.exception(e)
                if should_exit: sys.exit(2)
        else:
            if should_exit: sys.exit(1)
    
    def _setup_logger(self):
        self.logger = logging.getLogger('cravat.mapper')
        self.logger.info('input file: %s' %self.input_path)
        
    def _setup_io(self):
        """
        Open input and output files
        
        Open CravatReader for crv input. Open  CravatWriters for crx, and crg
        output. Open plain file for err output.
        """
        # Reader
        self.reader = CravatReader(self.input_path)
        # Various output files
        output_base_path = os.path.join(self.output_dir,
                                        self.output_base_fname)
        output_toks = self.output_base_fname.split('.')
        if output_toks[-1] == 'crv':
            output_toks = output_toks[:-1]
        # .crx
        crx_fname = '.'.join(output_toks) + '.crx'
        self.crx_path = os.path.join(self.output_dir, crx_fname)
        self.crx_writer = CravatWriter(self.crx_path)
        self.crx_writer.add_columns(crx_def)
        self.crx_writer.write_definition(self.conf)
        for index_columns in crx_idx:
            self.crx_writer.add_index(index_columns)
        # .crg
        crg_fname = '.'.join(output_toks) + '.crg'
        self.crg_path = os.path.join(self.output_dir, crg_fname)
        self.crg_writer = CravatWriter(self.crg_path)
        self.crg_writer.add_columns(crg_def)
        self.crg_writer.write_definition()
        for index_columns in crg_idx:
            self.crg_writer.add_index(index_columns)
        #.crt
        crt_fname = '.'.join(output_toks) + '.crt'
        self.crt_path = os.path.join(self.output_dir, crt_fname)
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
        try:
            self.base_setup()
            start_time = time.time()
            self.logger.info('started: %s' \
                             %time.asctime(time.localtime(start_time)))
            count = 0
            for ln, crv_data in self.reader.loop_data('dict'):
                count += 1
                try:
                    crx_data, alt_transcripts = self.map(crv_data)
                except Exception as e:
                    self._log_runtime_error(ln, e)
                    continue
                self.crx_writer.write_data(crx_data)
                self._add_crx_to_gene_info(crx_data)
                self._write_to_crt(alt_transcripts)
            self._write_crg()
            stop_time = time.time()
            self.logger.info('finished: %s' \
                             %time.asctime(time.localtime(stop_time)))
            runtime = stop_time - start_time
            self.logger.info('runtime: %6.3f' %runtime)
        except Exception as e:
            self.__handle_exception(e)
        
    def _write_to_crt(self, alt_transcripts):
        for primary, alts in alt_transcripts.items():
            if primary not in self.written_primary_transc:
                for alt in alts:
                    d = {'primary_transcript': primary,
                         'alt_transcript': alt}
                    self.crt_writer.write_data(d)
                self.written_primary_transc.add(primary)
    
    def _add_crx_to_gene_info(self, crx_data):
        """
        Add information in a crx dict to persistent gene_info dict
        """
        tmap_json = crx_data['all_mappings']
        # Return if no tmap
        if tmap_json == '':
            return
        tmap_parser = AllMappingsParser(tmap_json)
        for hugo in tmap_parser.get_genes():
            so = most_severe_so(tmap_parser.get_uniq_sos_for_gene(genes=[hugo]))
            try:
                self.gene_info[hugo]['variant_count'] += 1
            except KeyError:
                self.gene_info[hugo] = {'hugo': hugo,
                                        'variant_count': 1,
                                        'so_counts': {}}
            try:
                self.gene_info[hugo]['so_counts'][so] += 1
            except KeyError:
                self.gene_info[hugo]['so_counts'][so] = 1
    
    def _write_crg(self):
        """
        Convert gene_info to crg dict and write to crg file
        """
        sorted_hugos = list(self.gene_info.keys())
        sorted_hugos.sort()
        for hugo in sorted_hugos:
            gene = self.gene_info[hugo]
            crg_data = {x['name']:'' for x in crg_def}
            crg_data['hugo'] = hugo
            crg_data['num_variants'] = gene['variant_count']
            so_count_toks = []
            worst_so = ''
            try:
                worst_so = most_severe_so((gene['so_counts'].keys()))
            except:
                pass
            sorted_counts = list(gene['so_counts'].items())
            # Sort by SO occurence, descending
            sorted_counts.sort(key=lambda l: so_severity.index(l[0]), reverse=True)
            for so, so_count in sorted_counts:
                so_count_toks.append('%s(%d)' %(so, so_count))
            crg_data['so'] = worst_so
            crg_data['all_so'] = ','.join(so_count_toks)
            self.crg_writer.write_data(crg_data)
    
    def _log_runtime_error(self, ln, e):
        err_toks = [str(x) for x in [ln, e]]
        #self.ef.write('\t'.join(err_toks)+'\n')
        self.logger.exception(e)
        if not(isinstance(e,InvalidData)):
            self.__handle_exception(e, should_exit=False)
    
