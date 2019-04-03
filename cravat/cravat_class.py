import time
import argparse
import os
import sys
from . import admin_util as au
from . import util
from .config_loader import ConfigLoader
import sqlite3
import datetime
from types import SimpleNamespace
from .constants import liftover_chain_paths
import json
import logging
import traceback
from .mp_runners import run_annotator_mp
import multiprocessing as mp
import multiprocessing.managers
from logging.handlers import QueueListener
from .aggregator import Aggregator
from .exceptions import *
import yaml
import cravat.cravat_util as cu
import collections

cravat_cmd_parser = argparse.ArgumentParser(
    prog='cravat input_file_path',
    description='Open-CRAVAT genomic variant interpreter. https://github.com/KarchinLab/open-cravat. Use input_file_path argument before any option.',
    epilog='* input_file_path should precede any option.')
cravat_cmd_parser.add_argument('inputs',
                    nargs='+',
                    help=argparse.SUPPRESS)
cravat_cmd_parser.add_argument('-a',
                    nargs="+",
                    dest='annotators',
                    help='annotators to run')
cravat_cmd_parser.add_argument('-e',
                    nargs='+',
                    dest='excludes',
                    help='annotators to exclude')
cravat_cmd_parser.add_argument('-n',
                    dest='run_name',
                    help='name of cravat run')
cravat_cmd_parser.add_argument('-d',
                    dest='output_dir',
                    default=None,
                    help='directory for output files')
cravat_cmd_parser.add_argument('--stc',
                    dest='stc',
                    action='store_true',
                    default=False,
                    help='starts with converter')
cravat_cmd_parser.add_argument('--stm',
                    dest='stm',
                    action='store_true',
                    default=False,
                    help='starts with gene mapper')
cravat_cmd_parser.add_argument('--sta',
                    dest='sta',
                    action='store_true',
                    default=False,
                    help='starts with annotator(s)')
cravat_cmd_parser.add_argument('--stg',
                    dest='stg',
                    action='store_true',
                    default=False,
                    help='starts with aggregator')
cravat_cmd_parser.add_argument('--stp',
                    dest='stp',
                    action='store_true',
                    default=False,
                    help='starts with post-aggregator')
cravat_cmd_parser.add_argument('--str',
                    dest='str',
                    action='store_true',
                    default=False,
                    help='starts with reporter')
cravat_cmd_parser.add_argument('--rc',
                    dest='rc',
                    action='store_true',
                    default=False,
                    help='forces re-running of converter if it is in the run chain.')
cravat_cmd_parser.add_argument('--rm',
                    dest='rm',
                    action='store_true',
                    default=False,
                    help='forces re-running of gene mapper if it is in the run chain.')
cravat_cmd_parser.add_argument('--ra',
                    dest='ra',
                    action='store_true',
                    default=False,
                    help='forces re-running of annotator if it is in the run chain.')
cravat_cmd_parser.add_argument('--rg',
                    dest='rg',
                    action='store_true',
                    default=False,
                    help='forces re-running of aggregator if it is in the run chain.')
cravat_cmd_parser.add_argument('--rp',
                    dest='rp',
                    action='store_true',
                    default=False,
                    help='forces re-running of post-aggregator if it is in the run chain.')
cravat_cmd_parser.add_argument('--ec',
                    dest='ec',
                    action='store_true',
                    default=False,
                    help='ends after converter.')
cravat_cmd_parser.add_argument('--em',
                    dest='em',
                    action='store_true',
                    default=False,
                    help='ends after gene mapper.')
cravat_cmd_parser.add_argument('--ea',
                    dest='ea',
                    action='store_true',
                    default=False,
                    help='ends after annotator(s).')
cravat_cmd_parser.add_argument('--sc',
                    dest='sc',
                    action='store_true',
                    default=False,
                    help='skips converter.')
cravat_cmd_parser.add_argument('--sm',
                    dest='sm',
                    action='store_true',
                    default=False,
                    help='skips gene mapper.')
cravat_cmd_parser.add_argument('--sa',
                    dest='sa',
                    action='store_true',
                    default=False,
                    help='skips annotators.')
cravat_cmd_parser.add_argument('--sg',
                    dest='sg',
                    action='store_true',
                    default=False,
                    help='skips aggregator.')
cravat_cmd_parser.add_argument('--sp',
                    dest='sp',
                    action='store_true',
                    default=False,
                    help='skips post-aggregator.')
cravat_cmd_parser.add_argument('--sr',
                    dest='sr',
                    action='store_true',
                    default=False,
                    help='skips reporter.')
cravat_cmd_parser.add_argument('-c',
                    dest='conf',
                    help='path to a conf file')
cravat_cmd_parser.add_argument('--cs',
                    dest='confs',
                    help='configuration string')
cravat_cmd_parser.add_argument('-v', 
                    dest='verbose',
                    action='store_true',
                    default=False,
                    help='verbose')
cravat_cmd_parser.add_argument('-t',
                    nargs='+',
                    dest='reports',
                    help='report types. If omitted, default one in cravat.yml is used.')
cravat_cmd_parser.add_argument('-l',
                    dest='liftover',
                    choices=['hg38', 'hg19', 'hg18'],
                    default='hg38',
                    help='reference genome of input. CRAVAT will lift over to hg38 if needed.')
cravat_cmd_parser.add_argument('-x',
                    dest='cleandb',
                    action='store_true',
                    help='deletes the existing result database and ' +
                            'creates a new one.')
cravat_cmd_parser.add_argument('--newlog',
                    dest='newlog',
                    action='store_true',
                    default=False,
                    help='deletes the existing log file and ' +
                            'creates a new one.')
cravat_cmd_parser.add_argument('--note',
                    dest='note',
                    default='',
                    help='note will be written to the run status file (.status.json)')
cravat_cmd_parser.add_argument('--mp',
                    dest='mp',
                    default=None,
                    help='number of processes to use to run annotators')
cravat_cmd_parser.add_argument('--forcedinputformat',
                    dest='forcedinputformat',
                    default=None,
                    help='Force input format')

class MyManager (multiprocessing.managers.SyncManager):
    pass

class Cravat (object):

    def __init__ (self, **kwargs):
        self.runlevels = {
            'converter': 1, 
            'mapper': 2, 
            'annotator': 3, 
            'aggregator': 4, 
            'postaggregator': 5, 
            'reporter': 6}
        self.should_run_converter = False
        self.should_run_genemapper = False
        self.should_run_annotators = True
        self.should_run_aggregator = True
        self.should_run_reporter = True
        self.has_secondary_input = False
        self.pythonpath = sys.executable
        self.annotators = {}        
        self.make_args_namespace(kwargs)
        self.conf = ConfigLoader(job_conf_path=self.run_conf_path)
        if self.args.confs != None:
            self.conf.override_cravat_conf(
                self.args.confs.replace("'", '"'))
        self.get_logger()
        self.start_time = time.time()
        self.logger.info('started: {0}'.format(time.asctime(time.localtime(self.start_time))))
        self.logger.info('input assembly: {}'.format(self.input_assembly))
        if self.run_conf_path != '':
            self.logger.info('conf file: {}'.format(self.run_conf_path))
        self.write_initial_status_json()
        self.unique_logs = {}
        manager = MyManager()
        manager.register('StatusWriter', StatusWriter)
        manager.start()
        self.status_writer = manager.StatusWriter(self.status_json_path)

    def write_initial_status_json (self):
        status_fname = '{}.status.json'.format(self.run_name)
        self.status_json_path = os.path.join(self.output_dir, status_fname)
        if os.path.exists(self.status_json_path) == True:
            with open(self.status_json_path) as f:
                self.status_json = json.load(f)
                self.pkg_ver = self.status_json['open_cravat_version']
        else:
            self.status_json = {}
            self.status_json['job_dir'] = self.output_dir
            self.status_json['id'] = os.path.basename(os.path.normpath(self.output_dir))
            self.status_json['run_name'] = self.run_name
            self.status_json['assembly'] = self.input_assembly
            self.status_json['db_path'] = os.path.join(self.output_dir, self.run_name + '.sqlite')
            #todo adapt to multiple inputs
            self.status_json['orig_input_fname'] = ', '.join([os.path.basename(x) for x in self.inputs])
            self.status_json['orig_input_path'] = ', '.join(self.inputs)
            self.status_json['submission_time'] = datetime.datetime.now().isoformat()
            self.status_json['viewable'] = False
            self.status_json['note'] = self.args.note
            self.status_json['status'] = 'Starting'
            self.status_json['reports'] = self.args.reports if self.args.reports != None else []
            self.pkg_ver = au.get_current_package_version()
            self.status_json['open_cravat_version'] = self.pkg_ver
            with open(self.status_json_path,'w') as wf:
                wf.write(json.dumps(self.status_json))

    def get_logger (self):
        self.logger = logging.getLogger('cravat')
        self.logger.setLevel('INFO')
        self.log_path = os.path.join(self.output_dir, self.run_name + '.log')
        self.log_handler = logging.FileHandler(self.log_path, mode=self.logmode)
        formatter = logging.Formatter('%(asctime)s %(name)-20s %(message)s', '%Y/%m/%d %H:%M:%S')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
        # individual input line error log
        self.error_logger = logging.getLogger('error')
        self.error_logger.setLevel('INFO')
        error_log_path = os.path.join(self.output_dir, self.run_name + '.err')
        error_log_handler = logging.FileHandler(error_log_path, mode=self.logmode)
        formatter = logging.Formatter('SOURCE:%(name)-20s %(message)s')
        error_log_handler.setFormatter(formatter)
        self.error_logger.addHandler(error_log_handler)

    def close_logger (self):
        logging.shutdown()
    
    def update_status (self, status):
        self.status_writer.queue_status_update('status', status)

    async def main (self):
        no_problem_in_run = True
        try:
            self.update_status('Started cravat')
            self.set_and_check_input_files()
            self.make_module_run_list()
            if self.args.sc == False and \
                (
                    self.runlevel <= self.runlevels['converter'] or
                    self.crv_present == False or
                    self.args.rc
                ):
                print('Running converter...')
                stime = time.time()
                self.run_converter()
                rtime = time.time() - stime
                print('finished in {0:.3f}s'.format(rtime))
            if self.args.ec:
                return
            if self.args.sm == False and \
                (
                    self.runlevel <= self.runlevels['mapper'] or
                    self.crx_present == False or
                    self.args.rm
                ):
                print('Running gene mapper...')
                stime = time.time()
                self.run_genemapper()
                rtime = time.time() - stime
                print('finished in {0:.3f}s'.format(rtime))
            if self.args.em:
                return
            if self.args.sa == False and \
                (
                    self.runlevel <= self.runlevels['annotator'] or
                    self.args.ra
                ):
                print('Running annotators...')
                stime = time.time()
                self.run_annotators_mp()
                rtime = time.time() - stime
                print('\tannotator(s) finished in {0:.3f}s'.format(rtime))
            if self.args.ea:
                return
            if self.args.sg == False and \
                (
                    self.runlevel <= self.runlevels['aggregator'] or
                    self.args.rg
                ):
                print('Running aggregator...')
                self.result_path = self.run_aggregator()
                self.write_job_info()
            if self.args.sp == False and \
                (
                    self.runlevel <= self.runlevels['postaggregator'] or
                    self.args.rp
                ):
                print('Running post-aggregators...')
                self.run_postaggregators()
            if self.args.sr == False and \
                (
                    self.runlevel <= self.runlevels['reporter'] or
                    self.args.rr
                ):
                print('Running reporter...')
                no_problem_in_run = await self.run_reporter()
            self.update_status('Finished')
        except Exception as e:
            self.handle_exception(e)
            no_problem_in_run = False
        finally:
            end_time = time.time()
            display_time = time.asctime(time.localtime(end_time))
            runtime = end_time - self.start_time
            if no_problem_in_run:
                self.logger.info('finished: {0}'.format(display_time))
                self.logger.info('runtime: {0:0.3f}s'.format(runtime))
                print('Finished normally. Runtime: {0:0.3f}s'.format(runtime))
            else:
                self.logger.info('finished with an exception: {0}'.format(display_time))
                self.logger.info('runtime: {0:0.3f}s'.format(runtime))
                print('Finished with an exception. Runtime: {0:0.3f}s'.format(runtime))
                print('Check {}'.format(self.log_path))
                self.update_status('Error')
            self.close_logger()
            self.status_writer.flush()

    def handle_exception (self, e):
        exc_str = traceback.format_exc()
        exc_class = e.__class__
        if exc_class == LiftoverFailure or exc_class == InvalidData:
            pass
        elif exc_class == ExpectedException:
            self.logger.exception('An expected exception occurred.')
            self.logger.error(e)
        else:
            self.logger.exception('An unexpected exception occurred.')
            print(exc_str)

    def make_args_namespace(self, supplied_args):
        full_args = util.get_argument_parser_defaults(cravat_cmd_parser)
        full_args.update(supplied_args)
        self.args = SimpleNamespace(**full_args)
        self.annotator_names = self.args.annotators
        if self.annotator_names == None:
            self.annotators = au.get_local_module_infos_of_type('annotator')
        else:
            self.annotators = \
                au.get_local_module_infos_by_names(self.annotator_names)
        self.excludes = self.args.excludes
        if self.excludes == ['*']:
            self.annotators = {}
        elif self.excludes != None:
            for m in self.excludes:
                if m in self.annotators:
                    del self.annotators[m]
        self.inputs = [os.path.abspath(x) for x in self.args.inputs]
        self.run_name = self.args.run_name
        if self.run_name == None: #todo set run name different if multiple inputs
            self.run_name = os.path.basename(self.inputs[0])
        self.output_dir = self.args.output_dir
        if self.output_dir == None:
            self.output_dir = os.path.dirname(os.path.abspath(self.inputs[0]))
        else:
            self.output_dir = os.path.abspath(self.output_dir)
        if os.path.exists(self.output_dir) == False:
            os.mkdir(self.output_dir)
        self.run_conf_path = ''
        if self.args.conf: 
            self.run_conf_path = self.args.conf
        self.verbose = self.args.verbose
        self.reports = self.args.reports
        self.input_assembly = self.args.liftover
        self.runlevel = self.runlevels['annotator']
        if self.args.stc:
            self.runlevel = self.runlevels['converter']
        if self.args.stm:
            self.runlevel = self.runlevels['mapper']
        if self.args.sta:
            self.runlevel = self.runlevels['annotator']
        if self.args.stg:
            self.runlevel = self.runlevels['aggregator']
        if self.args.stp:
            self.runlevel = self.runlevels['postaggregator']
        if self.args.str:
            self.runlevel = self.runlevels['reporter']
        self.cleandb = self.args.cleandb
        if self.args.newlog == True:
            self.logmode = 'w'
        else:
            self.logmode = 'a'

    def set_and_check_input_files (self):
        self.crvinput = os.path.join(self.output_dir, self.run_name + '.crv')
        self.crxinput = os.path.join(self.output_dir, self.run_name + '.crx')
        self.crginput = os.path.join(self.output_dir, self.run_name + '.crg')
        # if self.input.split('.')[-1] == 'crv':
        #     self.crvinput = self.input
        # else:
        #     self.crvinput = os.path.join(self.output_dir, self.run_name + '.crv')
        # if self.input.split('.')[-1] == 'crx':
        #     self.crxinput = self.input
        # else:
        #     self.crxinput = os.path.join(self.output_dir, self.run_name + '.crx')
        # if self.input.split('.')[-1] == 'crg':
        #     self.crginput = self.input
        # else:
        #     self.crginput = os.path.join(self.output_dir, self.run_name + '.crg')

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

    def make_module_run_list (self):
        self.ordered_annotators = []
        self.modules = {}
        for module in self.annotators.values():
            self.add_annotator_to_queue(module)
        annot_names = [v.name for v in self.ordered_annotators]
        annot_names = list(set(annot_names))
        filenames = os.listdir(self.output_dir)
        for filename in filenames:
            toks = filename.split('.')
            if len(toks) == 3:
                extension = toks[2]
                if toks[0] == self.run_name and\
                    (extension == 'var' or extension == 'gen'):
                    annot_name = toks[1]
                    if annot_name not in annot_names:
                        annot_names.append(annot_name)
        annot_names.sort()
        if self.runlevel <= self.runlevels['annotator']:
            self.status_writer.queue_status_update('annotators', annot_names, force=True)

    def add_annotator_to_queue (self, module):
        if module.directory == None:
            sys.exit('Module %s is not installed' % module)
        if module.name not in self.modules:
            self.modules[module.name] = module
        secondary_modules = self.get_secondary_modules(module)
        if len(secondary_modules) > 0:
            self.has_secondary_input = True
        for secondary_module in secondary_modules:
            if self.args.ra == True or \
                    self.check_module_output(secondary_module) == None:
                self.add_annotator_to_queue(secondary_module)
        ordered_module_names = [m.name for m in self.ordered_annotators]
        if module.name not in ordered_module_names:
            if self.args.ra == True or \
                    self.check_module_output(module) == None:
                self.ordered_annotators.append(module)

    def get_module_output_path (self, module):
        if module.level == 'variant':
            postfix = '.var'
        elif module.level == 'gene':
            postfix = '.gen'
        else:
            return None
        path = os.path.join(
            self.output_dir, 
            self.run_name + '.' + module.name + postfix)
        return path

    def check_module_output (self, module):
        path = self.get_module_output_path(module)
        if os.path.exists(path):
            return path
        else:
            None

    def get_secondary_modules (self, primary_module):
        secondary_modules = \
            [au.get_local_module_info(module_name) for module_name in 
                primary_module.secondary_module_names]
        return secondary_modules

    def run_converter(self):
        converter_path = os.path.join(os.path.dirname(__file__),'cravat_convert.py')
        module = SimpleNamespace(title='Converter',
                                 name='converter',
                                 script_path=converter_path)
        cmd = [module.script_path,
                *self.inputs,
               '-n', self.run_name,
               '-d', self.output_dir,
               '-l', self.input_assembly]
        if self.args.forcedinputformat is not None:
            cmd.extend(['-f', self.args.forcedinputformat])
        self.announce_module(module)
        if self.verbose:
            print(' '.join(cmd))
        converter_class = util.load_class('MasterCravatConverter', module.script_path)
        converter = converter_class(cmd, self.status_writer)
        converter.run()

    def run_genemapper (self):
        module = au.get_local_module_info(
            self.conf.get_cravat_conf()['genemapper'])
        self.genemapper = module
        cmd = [module.script_path, 
               self.crvinput,
               '-n', self.run_name,
               '-d', self.output_dir]
        self.announce_module(module)
        if self.verbose:
            print(' '.join(cmd))
        genemapper_class = util.load_class('Mapper', module.script_path)
        genemapper = genemapper_class(cmd, self.status_writer)
        genemapper.run()

    def run_aggregator (self):
        # Variant level
        print('\t{0:30s}\t'.format('Variants'), end='', flush=True)
        stime = time.time()
        cmd = ['donotremove',
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'variant',
               '-n', self.run_name]
        if self.cleandb:
            cmd.append('-x')
        if self.verbose:
            print(' '.join(cmd))
        v_aggregator = Aggregator(cmd)
        v_aggregator.run()
        rtime = time.time() - stime
        print('finished in {0:.3f}s'.format(rtime)) 

        # Gene level
        print('\t{0:30s}\t'.format('Genes'), end='', flush=True)
        stime = time.time()
        cmd = ['donotremove', 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'gene',
               '-n', self.run_name]
        if self.verbose:
            print(' '.join(cmd))
        g_aggregator = Aggregator(cmd)
        g_aggregator.run()
        rtime = time.time() - stime
        print('finished in {0:.3f}s'.format(rtime))

        # Sample level
        print('\t{0:30s}\t'.format('Samples'), end='', flush=True)
        stime = time.time()
        cmd = ['donotremove', 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'sample',
               '-n', self.run_name]
        if self.verbose:
            print(' '.join(cmd))
        s_aggregator = Aggregator(cmd)
        s_aggregator.run()
        rtime = time.time() - stime
        print('finished in {0:.3f}s'.format(rtime))

        # Mapping level
        print('\t{0:30s}\t'.format('Tags'), end='', flush=True)
        cmd = ['donotremove', 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'mapping',
               '-n', self.run_name]
        if self.verbose:
            print(' '.join(cmd))
        m_aggregator = Aggregator(cmd)
        m_aggregator.run()
        rtime = time.time() - stime
        print('finished in {0:.3f}s'.format(rtime))

        return v_aggregator.db_path

    def run_postaggregators (self):
        modules = au.get_local_module_infos_of_type('postaggregator')
        for module_name in modules:
            module = modules[module_name]
            self.announce_module(module)
            cmd = [module.script_path, 
                   '-d', self.output_dir, 
                   '-n', self.run_name]
            if self.verbose:
                print(' '.join(cmd))
            post_agg_cls = util.load_class('CravatPostAggregator', module.script_path)
            post_agg = post_agg_cls(cmd)
            stime = time.time()
            post_agg.run()
            rtime = time.time() - stime
            print('finished in {0:.3f}s'.format(rtime))

    async def run_reporter (self):
        if self.reports != None:
            module_names = [v + 'reporter' for v in self.reports]
        else:
            module_names = [self.conf.get_cravat_conf()['reporter']]
        all_reporters_ran_well = True
        for module_name in module_names:
            try:
                module = au.get_local_module_info(module_name)
                self.announce_module(module)
                cmd = [module.script_path, 
                       '-s', os.path.join(self.output_dir, self.run_name),
                       os.path.join(self.output_dir, self.run_name + '.sqlite'),
                       '-c', self.run_conf_path,
                       '--module-name', module_name]
                if self.verbose:
                    print(' '.join(cmd))
                Reporter = util.load_class('Reporter', module.script_path)
                reporter = Reporter(cmd, self.status_writer)
                await reporter.prep()
                stime = time.time()
                await reporter.run()
                rtime = time.time() - stime
                print('finished in {0:.3f}s'.format(rtime))
            except Exception as e:
                traceback.print_exc()
                self.logger.exception(e)
                all_reporters_ran_well = False
        return all_reporters_ran_well

    def run_annotators_mp (self):
        default_workers = mp.cpu_count() - 1
        if default_workers < 1: 
            default_workers = 1
        num_workers = self.conf.get_cravat_conf().get('num_workers', default_workers)
        if self.args.mp is not None:
            try:
                self.args.mp = int(self.args.mp)
                if self.args.mp >= 1 and self.args.mp <= default_workers:
                    num_workers = self.args.mp
            except:
                self.logger.exception('error handling mp argument:')
        if self.has_secondary_input:
            num_workers = 1
        self.logger.info('num_workers: {}'.format(num_workers))
        all_cmds = []
        for module in self.ordered_annotators:
            # Make command
            if module.level == 'variant':
                if 'input_format' in module.conf:
                    input_format = module.conf['input_format']
                    if input_format == 'crv':
                        inputpath = self.crvinput
                    elif input_format == 'crx':
                        inputpath = self.crxinput
                    else:
                        raise Exception('Incorrect input_format value')
                        # inputpath = self.input
                else:
                    inputpath = self.crvinput
            elif module.level == 'gene':
                inputpath = self.crginput
            secondary_opts = []
            if 'secondary_inputs' in module.conf:
                secondary_module_names = module.conf['secondary_inputs']
                for secondary_module_name in secondary_module_names:
                    secondary_module = self.modules[secondary_module_name]
                    secondary_output_path =\
                        self.get_module_output_path(secondary_module)
                    secondary_opts.extend([
                        '-s', 
                        secondary_module.name + '@' +\
                            os.path.join(self.output_dir, secondary_output_path)])
            cmd = [module.script_path, inputpath]
            cmd.extend(secondary_opts)
            if self.run_name != None:
                cmd.extend(['-n', self.run_name])
            if self.output_dir != None:
                cmd.extend(['-d', self.output_dir])
            all_cmds.append(cmd)
        ds = [self.status_writer for i in range(len(self.ordered_annotators))]
        pool_args = zip(
            self.ordered_annotators,
            all_cmds,
            ds,
        )
        self.logger.removeHandler(self.log_handler)
        with mp.Pool(processes=num_workers) as pool:
            results = pool.starmap_async(run_annotator_mp, pool_args, error_callback=lambda e, mp_pool=pool: mp_pool.terminate())
            pool.close()
            pool.join()
        try:
            for result in results.get():
                pass
        except Exception as e:
            self.handle_exception(e)
        self.log_path = os.path.join(self.output_dir, self.run_name + '.log')
        self.log_handler = logging.FileHandler(self.log_path, 'a')
        formatter = logging.Formatter('%(asctime)s %(name)-20s %(message)s', '%Y/%m/%d %H:%M:%S')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)

    def table_exists (self, cursor, table):
        sql = 'select name from sqlite_master where type="table" and ' +\
            'name="' + table + '"'
        cursor.execute(sql)
        if cursor.fetchone() == None:
            return False
        else:
            return True

    def write_job_info (self):
        dbpath = os.path.join(self.output_dir, self.run_name + '.sqlite')
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        q = 'drop table if exists info'
        cursor.execute(q)
        q = 'create table info (colkey text, colval text)'
        cursor.execute(q)
        created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        q = 'insert into info values ("Result created at", "' + created + '")'
        cursor.execute(q)
        q = 'insert into info values ("Input file name", "{}")'.format(';'.join(self.inputs)) #todo adapt to multiple inputs
        cursor.execute(q)
        q = 'insert into info values ("Input genome", "' + self.input_assembly + '")'
        cursor.execute(q)
        q = 'select count(*) from variant'
        cursor.execute(q)
        no_input = str(cursor.fetchone()[0])
        q = 'insert into info values ("Number of unique input variants", "' + no_input + '")'
        cursor.execute(q)
        q = 'insert into info values ("open-cravat", "{}")'.format(self.pkg_ver)
        cursor.execute(q)
        if hasattr(self, 'genemapper'):
            version = self.genemapper.conf['version']
            title = self.genemapper.conf['title']
            modulename = self.genemapper.name
            genemapper_str = '{} ({})'.format(title, version)
            q = 'insert into info values ("Gene mapper", "{}")'.format(genemapper_str)
            cursor.execute(q)
        '''
        q = 'update variant_annotator set version="{}" where name="{}"'.format(version, modulename)
        cursor.execute(q)
        q = 'update gene_annotator set version="{}" where name="{}"'.format(version, modulename)
        cursor.execute(q)
        '''
        annotators_str = ''
        for modulename in self.annotators.keys():
            annot = self.annotators[modulename]
            version = annot.conf['version']
            title = annot.conf['title']
            level = annot.conf['level']
            q = 'update {}_annotator set version="{}" where name="{}"'.format(level, version, modulename)
            cursor.execute(q)
            annotators_str += '{} ({}), '.format(title, version)
        annotators = annotators_str.rstrip(', ')
        q = 'insert into info values ("Annotators", "' + annotators_str + '")'
        cursor.execute(q)
        conn.commit()
        cursor.close()
        conn.close()

    def run_summarizers (self):
        for module in self.ordered_summarizers:
            self.announce_module(module)
            self.run_summarizer(module)

    def run_summarizer (self, module):
        cmd = [module.script_path, '-l', 'variant']
        if self.run_name != None:
            cmd.extend(['-n', self.run_name])
        if self.output_dir != None:
            cmd.extend(['-d', self.output_dir])
        if self.verbose:
            print(' '.join(cmd))
        summarizer_cls = util.load_class('', module.script_path)
        summarizer = summarizer_cls(cmd)
        summarizer.run()

    def announce_module (self, module):
        print('\t{0:30s}\t'.format(module.title + ' (' + module.name + ')'), end='', flush=True)
        self.update_status('Running {title} ({name})'.format(title=module.title, name=module.name))

class StatusWriter:
    def __init__ (self, status_json_path):
        self.status_json_path = status_json_path
        self.status_queue = []
        self.load_status_json() 
        self.t = time.time()
        self.lock = False

    def load_status_json (self):
        f = open(self.status_json_path)
        lines = '\n'.join(f.readlines())
        self.status_json = json.loads(lines)
        f.close()

    def add_annotator_version_to_status_json (self, annotator_name, version):
        if 'annotator_version' not in self.status_json:
            self.status_json['annotator_version'] = {}
        self.status_json['annotator_version'][annotator_name] = version
        self.queue_status_update('annotator_version', self.status_json['annotator_version'])

    def queue_status_update (self, k, v, force=False):
        self.status_json[k] = v
        if force == True or\
                (time.time() - self.t > 3 and self.lock == False):
            self.lock = True
            self.update_status_json()
            self.t = time.time()
            self.lock = False

    def update_status_json (self):
        wf = open(self.status_json_path, 'w')
        json.dump(self.status_json, wf)
        wf.close()

    def get_status_json (self):
        return self.status_json

    def flush (self):
        self.lock = True
        self.update_status_json()
        self.t = time.time()
        self.lock = False
