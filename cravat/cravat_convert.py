import os
import importlib
import sys
import logging
import argparse
import time
import traceback
import cravat.constants as constants
from cravat import CravatWriter
from cravat.exceptions import LiftoverFailure, InvalidData, BadFormatError
import cravat.admin_util as au
from pyliftover import LiftOver
import copy

class VTracker:
    """ This helper class is used to identify the unique variants from the input 
        so the crv file will not contain multiple copies of the same variant.
    """
    var_by_chrom = {}
    current_UID = 1;
    
    #Add a variant - Returns true if the variant is a new unique variant, false
    #if it is a duplicate.  Also returns the UID.
    def addVar(self, chrom, pos, ref, alt):
        change = ref+":"+alt; 
        if chrom not in self.var_by_chrom:
            self.var_by_chrom[chrom] = {};
        
        chr_dict = self.var_by_chrom[chrom];
        if pos not in chr_dict:
            #we have not seen this position before, add the position and change
            chr_dict[pos] = {};
            chr_dict[pos][change] = self.current_UID;
            self.current_UID += 1;
            return True, chr_dict[pos][change];
        else:
            variants = chr_dict[pos];
            if change not in variants:
                #we have the position but not this base change, add it.
                chr_dict[pos][change] = self.current_UID;
                self.current_UID = self.current_UID + 1;
                return True, chr_dict[pos][change];
            else:
                #this variant has been seen before.
                return False, chr_dict[pos][change];      

class MasterCravatConverter(object):
    """ Convert a file of ambiguous format to .crv format.
        
        Reads in CravatConverter classes in the same directory, selects the
        correct converter, and writes a crv file.
    """
    ALREADYCRV = 2
    def __init__(self, args=None):
        try:
            args = args if args else sys.argv
            self.input_path = None
            self.f = None
            self.input_format = None
            self.logger = None
            self.crv_writer = None
            self.crs_writer = None
            self.crm_writer = None
            self.crl_writer = None
            self.err_file = None
            self.primary_converter = None
            self.converters = {}
            self.possible_formats = []
            self.ready_to_convert = False
            self.cmd_args = None
            self.output_dir = None
            self.output_base_fname = None
            self.chromdict = {'chrx': 'chrX', 'chry': 'chrY', 'chrMT': 'chrM', 'chrMt': 'chrM'}
            self.vtracker = VTracker();
            self._parse_cmd_args(args)
            self._setup_logger()
        except Exception as e:
            self.__handle_exception(e)

    def _parse_cmd_args(self, args):
        """ Parse the arguments in sys.argv """
        parser = argparse.ArgumentParser()
        parser.add_argument('path',
                            help='Path to this converter\'s python module')
        parser.add_argument('input',
                            help='File to be converted to .crv')
        parser.add_argument('-f',
                            dest='format',
                            help='Specify an input format')
        parser.add_argument('-n', '--name',
                            dest='name',
                            help='Name of job. Default is input file name.')
        parser.add_argument('-d', '--output-dir',
                            dest='output_dir',
                            help='Output directory. '\
                                 +'Default is input file directory.')
        parser.add_argument('-l','--liftover',
                            dest='liftover',
                            choices=['hg38']+list(constants.liftover_chain_paths.keys()),
                            default='hg38',
                            help='Input gene assembly. Will be lifted over to hg38')
        parsed_args = parser.parse_args(args)
        self.input_path = os.path.abspath(parsed_args.input)
        if parsed_args.format:
            self.input_format = parsed_args.format
        input_dir, input_fname = os.path.split(self.input_path)
        if parsed_args.output_dir:
            self.output_dir = parsed_args.output_dir
        else:
            self.output_dir = input_dir
        if not(os.path.exists(self.output_dir)):
            os.makedirs(self.output_dir)
        if parsed_args.name:
            self.output_base_fname = parsed_args.name
        else:
            self.output_base_fname = input_fname
        self.input_assembly = parsed_args.liftover
        self.do_liftover = self.input_assembly != 'hg38'
        if self.do_liftover:
            self.lifter = LiftOver(constants.liftover_chain_paths[self.input_assembly])
        else:
            self.lifter = None

    def setup (self):
        """ Do necesarry pre-run tasks """
        if self.ready_to_convert: return
        # Open file handle to input path
        self.f = open(self.input_path)
        # Read in the available converters
        self._initialize_converters()
        # Select the converter that matches the input format
        self._select_primary_converter()
        
        # A correct .crv file is not processed. 
        if self.input_format == 'crv' and \
            self.input_path.split('.')[-1] == 'crv':
            #exit(cravat.util.exit_codes['alreadycrv'])
            exit(1)
        
        # Open the output files
        self._open_output_files()
        self.ready_to_convert = True

    def _setup_logger(self):
        """ Open a log file and set up log handler """
        self.logger = logging.getLogger('cravat.converter')
        self.logger.info('started: %s' %time.asctime())
        self.logger.info('input file: %s' %self.input_path)
        if self.do_liftover:
            self.logger.info('liftover from %s' %self.input_assembly)

    def _initialize_converters(self):
        """ Reads in available converters.
            
            Loads any python files in same directory that start with _ as
            python modules. Initializes the CravatConverter class from that
            module and places them in a dict keyed by their input format
        """
        for module_info in au.get_local_module_infos_of_type('converter').values():
            # path based import from https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
            spec = importlib.util.spec_from_file_location(module_info.name,
                                                          module_info.script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            converter = module.CravatConverter()
            if converter.format_name not in self.converters:
                self.converters[converter.format_name] = converter
            else:
                err_msg = 'Cannot load two converters for format %s' \
                    %converter.format_name
                raise Exception(err_msg)
        self.possible_formats = list(self.converters.keys())

    def _select_primary_converter(self):
        """ Choose the converter which matches the input format.
            
            If a input format was not specified in the cmd args, uses the 
            check_format() method of the CravatConverters to identify a
            converter which can parse the input file.
        """
        if self.input_format is not None:
            if self.input_format not in self.possible_formats:
                sys.exit('Invalid input format. Please select from [%s]' \
                         %', '.join(self.possible_formats))
        else:
            valid_formats = []
            self.f.seek(0)
            for converter_name, converter in self.converters.items():
                check_success = converter.check_format(self.f)
                self.f.seek(0)
                if check_success: valid_formats.append(converter_name)
            if len(valid_formats) == 0:
                sys.exit('Input format could not be determined. ' +\
                    'Exiting without conversion.')
            elif len(valid_formats) > 1:
                sys.exit('Input format ambiguous in [%s]. '\
                            %', '.join(valid_formats)\
                         +'Please specify an input format.')
            else:
                self.input_format = valid_formats[0]
        self.primary_converter = self.converters[self.input_format]
        self.logger.info('input format: %s' %self.input_format)

    def _open_output_files (self):
        """ Open .crv .crs and .crm output files, plus .err file.
            
            .crv .crs and .crm files are opened using a CravatWriter. 
            .err file will contain all errors which occur during conversion.
            .map file contains two columns showing which lines in input
            correspond to which lines in output.
        """
        # Setup CravatWriter
        self.wpath = os.path.join(self.output_dir,
                                  self.output_base_fname + '.crv')
        self.crv_writer = CravatWriter(self.wpath)
        self.crv_writer.add_columns(constants.crv_def)
        self.crv_writer.write_definition()
        for index_columns in constants.crv_idx:
            self.crv_writer.add_index(index_columns)
        # Setup err file
        self.err_path = os.path.join(self.output_dir,
                                     self.output_base_fname + '.converter.err')
        # Setup crm line mappings file
        self.crm_path = os.path.join(self.output_dir, self.output_base_fname +'.crm')
        self.crm_writer = CravatWriter(self.crm_path)
        self.crm_writer.add_columns(constants.crm_def)
        self.crm_writer.write_definition()
        for index_columns in constants.crm_idx:
            self.crm_writer.add_index(index_columns)
        # Setup crs sample file
        self.crs_path = os.path.join(self.output_dir, self.output_base_fname +'.crs')
        self.crs_writer = CravatWriter(self.crs_path)
        self.crs_writer.add_columns(constants.crs_def)
        if hasattr(self.primary_converter, 'addl_cols'):
            self.crs_writer.add_columns(self.primary_converter.addl_cols, append=True)
            constants.crs_def.extend(self.primary_converter.addl_cols)
        self.crs_writer.write_definition()
        for index_columns in constants.crs_idx:
            self.crs_writer.add_index(index_columns)
        # Setup liftover var file
        if self.do_liftover:
            self.crl_path = '.'.join([self.wpath,self.input_assembly,'var'])
            self.crl_writer = CravatWriter(self.crl_path)
            assm_crl_def = copy.deepcopy(constants.crl_def)
            assm_crl_def[1]['title'] = '{0} Chrom'.format(self.input_assembly.title())
            assm_crl_def[2]['title'] = '{0} Position'.format(self.input_assembly.title())
            self.crl_writer.add_columns(assm_crl_def)
            self.crl_writer.write_definition()
            self.crl_writer.write_names(self.input_assembly,
                                        self.input_assembly.title())

    def run(self):
        """ Convert input file to a .crv file using the primary converter."""
        try:
            self.setup()
            start_time = time.time()
            self.primary_converter.setup(self.f)
            self.f.seek(0)
            read_lnum = 0
            write_lnum = 0
            num_errors = 0
            for l in self.f:
                read_lnum += 1
                try:
                    # all_wdicts is a list, since one input line can become
                    # multiple output lines
                    all_wdicts = self.primary_converter.convert_line(l)
                    if all_wdicts is None:
                        continue
                except Exception as e:
                    num_errors += 1
                    self._log_conversion_error(read_lnum, e)
                    continue
                if all_wdicts:
                    UIDMap = [] 
                    for wdict in all_wdicts:
                        chrom = wdict['chrom']
                        if chrom.startswith('chr') == False:
                            wdict['chrom'] = 'chr' + chrom
                        if chrom in self.chromdict:
                            wdict['chrom'] = self.chromdict[chrom]
                        if wdict['ref_base'] == '' and wdict['alt_base'] not in ['A','T','C','G']:
                            num_errors += 1
                            e = BadFormatError('Reference base required for non SNV')
                            self._log_conversion_error(read_lnum, e)
                            continue
                        if self.do_liftover:
                            prelift_wdict = copy.copy(wdict)
                            try:
                                wdict['chrom'], wdict['pos'] = self.liftover(wdict['chrom'],
                                                                             wdict['pos'])
                            except LiftoverFailure as e:
                                num_errors += 1
                                self._log_conversion_error(read_lnum, e)
                                continue
                        unique, UID = self.vtracker.addVar(wdict['chrom'], int(wdict['pos']), wdict['ref_base'], wdict['alt_base'])                       
                        wdict['uid'] = UID
                        if unique:
                            write_lnum += 1
                            self.crv_writer.write_data(wdict)
                            if self.do_liftover:
                                prelift_wdict['uid'] = UID
                                self.crl_writer.write_data(prelift_wdict)
                        if UID not in UIDMap: 
                            #For this input line, only write to the .crm if the UID has not yet been written to the map file.   
                            self.crm_writer.write_data({'original_line': read_lnum, 'tags': wdict['tags'], 'uid': UID})
                            UIDMap.append(UID)
                        self.crs_writer.write_data(wdict)
            self.logger.info('error lines: %d' %num_errors)
            self._close_files()
            end_time = time.time()
            self.logger.info('finished: %s' %\
                time.asctime(time.localtime(end_time)))
            runtime = round(end_time - start_time, 3)
            self.logger.info('num input lines: {}'.format(read_lnum))
            self.logger.info('runtime: %s'%runtime)
        except Exception as e:
            self.__handle_exception(e)
    
    def liftover(self, old_chrom, old_pos):
        new_coords = self.lifter.convert_coordinate(old_chrom, int(old_pos))
        if len(new_coords) > 0:
            new_chrom = new_coords[0][0]
            new_pos = new_coords[0][1]
            return new_chrom, new_pos
        else:
            raise LiftoverFailure(old_chrom, old_pos)
    
    def __handle_exception(self, e):
        sys.stderr.write(traceback.format_exc())
        if hasattr(self, 'logger'):
            if self.logger is not None:
                self.logger.exception(e)
                sys.exit(2)
        sys.exit(1)
                
    def _log_conversion_error(self, ln, e):
        """ Log exceptions thrown by primary converter.
            All exceptions are written to the .err file with the exception type
            and message. Exceptions are also written to the log file, with the 
            traceback. Exceptions of type InvalidData do not have their
            traceback logged.
        """
        err_toks = [str(x) for x in [ln, e.__class__.__name__, e]]
        #self.err_file.write('\t'.join(err_toks)+'\n')
        self.logger.exception(e)
        '''
        if not(isinstance(e,InvalidData)):
            self.logger.exception(e)
        '''

    def _close_files(self):
        """ Close the input and output files. """
        self.f.close()
        self.crv_writer.close()
        self.crm_writer.close()
        self.crs_writer.close()
        #self.err_file.close()

def main ():
    master_cravat_converter = MasterCravatConverter()
    master_cravat_converter.run()
    
if __name__ ==  '__main__':
    master_cravat_converter = MasterCravatConverter()
    master_cravat_converter.run()
