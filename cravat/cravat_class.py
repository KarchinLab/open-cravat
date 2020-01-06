import time
import argparse
import os
import sys
from cravat import admin_util as au
from cravat import util
from cravat.config_loader import ConfigLoader
import aiosqlite3
import datetime
from types import SimpleNamespace
from cravat import constants
import json
import logging
import traceback
from cravat.mp_runners import annot_from_queue
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

cravat_cmd_parser = argparse.ArgumentParser(
    prog='cravat input_file_path_1 input_file_path_2 ...',
    description='Open-CRAVAT genomic variant interpreter. https://github.com/KarchinLab/open-cravat. Use input_file_path arguments before any option or define them in a conf file (option -c).',
    epilog='* input_file_path should precede any option.')
cravat_cmd_parser.add_argument('inputs',
    nargs='*',
    default=None,
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
cravat_cmd_parser.add_argument('--startat',
    dest='startat',
    choices=['converter', 'mapper', 'annotator', 'aggregator', 'postaggregator', 'reporter'],
    default=None,
    help='starts at given stage')
cravat_cmd_parser.add_argument('--repeat',
    dest='repeat',
    nargs='+',
    choices=['converter', 'mapper', 'annotator', 'aggregator', 'postaggregator', 'reporter'],
    default=None,
    help='forces re-running of given stage if it is in the run chain.')
cravat_cmd_parser.add_argument('--endat',
    dest='endat',
    choices=['converter', 'mapper', 'annotator', 'aggregator', 'postaggregator', 'reporter'],
    default=None,
    help='ends after given stage.')
cravat_cmd_parser.add_argument('--skip',
    dest='skip',
    nargs='+',
    choices=['converter', 'mapper', 'annotator', 'aggregator', 'postaggregator', 'reporter'],
    default=None,
    help='skips given stage(s).')
cravat_cmd_parser.add_argument('-c',
    dest='conf',
    default=None,
    help='path to a conf file')
cravat_cmd_parser.add_argument('--cs',
    dest='confs',
    default=None,
    help='configuration string')
cravat_cmd_parser.add_argument('-v', 
    dest='verbose',
    action='store_true',
    default=False,
    help='verbose')
cravat_cmd_parser.add_argument('-t',
    nargs='+',
    dest='reports',
    choices=au.report_formats(),
    help='report types. If omitted, default one in cravat.yml is used.')
cravat_cmd_parser.add_argument('-l',
    dest='liftover',
    choices=constants.assembly_choices,
    default=None,
    help='reference genome of input. CRAVAT will lift over to hg38 if needed.')
cravat_cmd_parser.add_argument('-x',
    dest='cleandb',
    action='store_true',
    help='deletes the existing result database and creates a new one.')
cravat_cmd_parser.add_argument('--newlog',
    dest='newlog',
    action='store_true',
    default=None,
    help='deletes the existing log file and creates a new one.')
cravat_cmd_parser.add_argument('--note',
    dest='note',
    default=None,
    help='note will be written to the run status file (.status.json)')
cravat_cmd_parser.add_argument('--mp',
    dest='mp',
    default=None,
    help='number of processes to use to run annotators')
cravat_cmd_parser.add_argument('-i','--input-format',
    dest='forcedinputformat',
    default=None,
    choices=au.input_formats(),
    help='Force input format')
cravat_cmd_parser.add_argument('--temp-files',
    dest='temp_files',
    action='store_true',
    default=False,
    help='Leave temporary files after run is complete.')
cravat_cmd_parser.add_argument('--writeadmindb',
    dest='writeadmindb',
    action='store_true',
    default=False,
    help='Write job information to admin db after job completion')
cravat_cmd_parser.add_argument('--jobid',
    dest='jobid',
    default=None,
    help='Job ID for server version')
cravat_cmd_parser.add_argument('--version',
    dest='show_version',
    action='store_true',
    default=False,
    help='Shows open-cravat version.')
cravat_cmd_parser.add_argument('--separatesample',
    dest='separatesample',
    action='store_true',
    default=False,
    help='Separate variant results by sample')
cravat_cmd_parser.add_argument('--unique-variants',
    dest='unique_variants',
    action='store_true',
    default=False,
    help=argparse.SUPPRESS
)

def run(cmd_args):
    au.ready_resolution_console()
    module = Cravat(**vars(cmd_args))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(module.main())

cravat_cmd_parser.set_defaults(func=run)

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
        self.pythonpath = sys.executable
        self.annotators = {}        
        self.append_mode = False
        self.make_args_namespace(kwargs)
        self.get_logger()
        self.start_time = time.time()
        self.logger.info('started: {0}'.format(time.asctime(time.localtime(self.start_time))))
        if self.run_conf_path != '':
            self.logger.info('conf file: {}'.format(self.run_conf_path))
        if self.args.confs != None:
            conf_bak = self.conf
            try:
                confs_conf = json.loads(self.args.confs.replace("'", '"'))
                self.conf.override_all_conf(confs_conf)
            except Exception as e:
                self.logger.exception(e)
                self.logger.info('Error in processing cs option. --cs option was not applied.')
                self.conf = conf_bak
        self.modules_conf = self.conf.get_modules_conf()
        self.write_initial_status_json()
        self.unique_logs = {}
        self.manager = MyManager()
        self.manager.register('StatusWriter', StatusWriter)
        self.manager.start()
        self.status_writer = self.manager.StatusWriter(self.status_json_path)

    def check_valid_modules (self):
        absent_modules = []
        module_names = self.args.annotators
        if module_names is None:
            module_names = []
        for report in self.reports:
            module_name = report + 'reporter'
            module_names.append(module_name)
        for module_name in module_names:
            if au.module_exists_local(module_name) == False:
                absent_modules.append(module_name)
        if len(absent_modules) > 0:
            msg = 'Invalid module(s): {}'.format(','.join(absent_modules))
            self.logger.info(msg)
            print(msg)
            raise InvalidReporter
        for mname, linfo in self.annotators.items():
            for sec_name in linfo.secondary_module_names:
                if not au.module_exists_local(sec_name):
                    msg = f'Invalid secondary annotator {sec_name} requested by {mname}'
                    self.logger.info(msg)
                    print(msg)
                    raise InvalidReporter
                

    def write_initial_status_json (self):
        status_fname = '{}.status.json'.format(self.run_name)
        self.status_json_path = os.path.join(self.output_dir, status_fname)
        if os.path.exists(self.status_json_path) == True:
            with open(self.status_json_path) as f:
                try:
                    self.status_json = json.load(f)
                    self.pkg_ver = self.status_json['open_cravat_version']
                except:
                    self.pkg_ver = au.get_current_package_version()
            if self.status_json['status'] == 'Submitted':
                self.status_json['job_dir'] = self.output_dir
                self.status_json['id'] = os.path.basename(os.path.normpath(self.output_dir))
                self.status_json['run_name'] = self.run_name
                self.status_json['assembly'] = self.input_assembly
                self.status_json['db_path'] = os.path.join(self.output_dir, self.run_name + '.sqlite')
                self.status_json['orig_input_fname'] = [os.path.basename(x) for x in self.inputs]
                self.status_json['orig_input_path'] = self.inputs
                self.status_json['submission_time'] = datetime.datetime.now().isoformat()
                self.status_json['viewable'] = False
                self.status_json['note'] = self.args.note
                self.status_json['status'] = 'Starting'
                self.status_json['reports'] = self.args.reports if self.args.reports != None else []
                self.pkg_ver = au.get_current_package_version()
                self.status_json['open_cravat_version'] = self.pkg_ver
                annot_names = list(self.annotators.keys())
                annot_names.sort()
                self.status_json['annotators'] = annot_names
                with open(self.status_json_path,'w') as wf:
                    wf.write(json.dumps(self.status_json, indent=2, sort_keys=True))
        else:
            self.status_json = {}
            self.status_json['job_dir'] = self.output_dir
            self.status_json['id'] = os.path.basename(os.path.normpath(self.output_dir))
            self.status_json['run_name'] = self.run_name
            self.status_json['assembly'] = self.input_assembly
            self.status_json['db_path'] = os.path.join(self.output_dir, self.run_name + '.sqlite')
            self.status_json['orig_input_fname'] = [os.path.basename(x) for x in self.inputs]
            self.status_json['orig_input_path'] = self.inputs
            self.status_json['submission_time'] = datetime.datetime.now().isoformat()
            self.status_json['viewable'] = False
            self.status_json['note'] = self.args.note
            self.status_json['status'] = 'Starting'
            self.status_json['reports'] = self.args.reports if self.args.reports != None else []
            self.pkg_ver = au.get_current_package_version()
            self.status_json['open_cravat_version'] = self.pkg_ver
            annot_names = list(self.annotators.keys())
            annot_names.sort()
            self.status_json['annotators'] = annot_names
            with open(self.status_json_path,'w') as wf:
                wf.write(json.dumps(self.status_json, indent=2, sort_keys=True))

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
            self.aggregator_ran = False
            self.check_valid_modules()
            self.update_status('Started cravat')
            input_files_str = ', '.join(self.inputs)
            print('Input file(s): {}'.format(input_files_str))
            print('Genome assembly: {}'.format(self.input_assembly))
            self.logger.info('input files: {}'.format(input_files_str))
            self.logger.info('input assembly: {}'.format(self.input_assembly))
            self.set_and_check_input_files()
            converter_ran = False
            if self.endlevel >= self.runlevels['converter'] and \
                    self.startlevel <= self.runlevels['converter'] and \
                    not 'converter' in self.args.skip and \
                    (
                        self.crv_present == False or
                        'converter' in self.args.repeat
                    ):
                print('Running converter...')
                stime = time.time()
                self.run_converter()
                rtime = time.time() - stime
                print('finished in {0:.3f}s'.format(rtime))
                converter_ran = True
            self.mapper_ran = False
            if self.endlevel >= self.runlevels['mapper'] and \
                    self.startlevel <= self.runlevels['mapper'] and \
                    not 'mapper' in self.args.skip and \
                    (
                        self.crx_present == False or
                        'mapper' in self.args.repeat or
                        converter_ran
                   ):
                print('Running gene mapper...')
                stime = time.time()
                self.run_genemapper()
                rtime = time.time() - stime
                print('finished in {0:.3f}s'.format(rtime))
                self.mapper_ran = True
            self.populate_secondary_annotators()
            self.done_annotators = {}
            for mname, module in self.annotators.items():
                if self.check_module_output(module) is not None:
                    self.done_annotators[mname] = module
            self.run_annotators = {aname: self.annotators[aname] for aname in set(self.annotators) - set(self.done_annotators)}
            self.annotator_ran = False
            if self.endlevel >= self.runlevels['annotator'] and \
                    self.startlevel <= self.runlevels['annotator'] and \
                    not 'annotator' in self.args.skip and \
                    (
                        self.mapper_ran or \
                        len(self.run_annotators) > 0
                    ):
                print('Running annotators...')
                stime = time.time()
                self.run_annotators_mp()
                rtime = time.time() - stime
                print('\tannotator(s) finished in {0:.3f}s'.format(rtime))
            if self.endlevel >= self.runlevels['aggregator'] and \
                    self.startlevel <= self.runlevels['aggregator'] and \
                    not 'aggregator' in self.args.skip and \
                    (
                        self.mapper_ran or \
                        self.annotator_ran or \
                        'aggregator' in self.args.repeat
                    ):
                print('Running aggregator...')
                self.result_path = self.run_aggregator()
                await self.write_job_info()
                self.write_smartfilters()
                self.aggregator_ran = True
            if self.endlevel >= self.runlevels['postaggregator'] and \
                    self.startlevel <= self.runlevels['postaggregator'] and \
                    not 'postaggregator' in self.args.skip and \
                    (
                        self.aggregator_ran or \
                        'postaggregator' in self.args.repeat
                    ):
                print('Running postaggregators...')
                self.run_postaggregators()
            if self.endlevel >= self.runlevels['reporter'] and \
                    self.startlevel <= self.runlevels['reporter'] and \
                    not 'reporter' in self.args.skip and \
                    (
                        self.aggregator_ran or \
                        len(self.reports) > 0
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
            if no_problem_in_run and not self.args.temp_files and self.aggregator_ran:
                self.clean_up_at_end()
            if self.args.writeadmindb:
                await self.write_admin_db(runtime, self.numinput)

    async def write_admin_db (self, runtime, numinput):
        if runtime is None or numinput is None:
            return
        if os.path.exists(constants.admindb_path) == False:
            s = '{} does not exist.'.format(constants.admindb_path)
            self.logger.info(s)
            print(s)
            return
        db = await aiosqlite3.connect(constants.admindb_path)
        cursor = await db.cursor()
        q = 'update jobs set runtime={}, numinput={} where jobid="{}"'.format(runtime, numinput, self.args.jobid)
        await cursor.execute(q)
        await db.commit()
        await cursor.close()
        await db.close()


    def write_smartfilters (self):
        dbpath = os.path.join(self.output_dir, self.run_name + '.sqlite')
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        q = 'create table if not exists smartfilters (name text primary key, definition text)'
        cursor.execute(q)
        ins_template = 'insert or replace into smartfilters (name, definition) values (?, ?);'
        for linfo in self.annotators.values():
            if linfo.smartfilters is not None:
                mname = linfo.name
                json_info = json.dumps(linfo.smartfilters)
                cursor.execute(ins_template, (mname, json_info))
        conn.commit()
        cursor.close()
        conn.close()
    
    def handle_exception (self, e):
        exc_str = traceback.format_exc()
        exc_class = e.__class__
        if exc_class in [InvalidData, InvalidReporter]:
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
        self.run_conf_path = ''
        if 'conf' in full_args: 
            self.run_conf_path = full_args['conf']
        self.conf = ConfigLoader(job_conf_path=self.run_conf_path)
        self.cravat_conf = self.conf.get_cravat_conf()
        self.run_conf = self.conf.get_run_conf()
        self.args = SimpleNamespace(**full_args)
        if self.args.show_version:
            au.show_cravat_version()
            exit()
        if len(self.args.inputs) == 0 and \
                'inputs' in self.run_conf:
            if type(self.run_conf['inputs']) == list:
                self.args.inputs = self.run_conf['inputs']
            else:
                print('inputs in conf file is invalid')
        if len(self.args.inputs) == 0:
            cravat_cmd_parser.print_help()
            print('\nNo input file was given.')
            exit()
        args_keys = self.args.__dict__.keys()
        for arg_key in args_keys:
            if self.args.__dict__[arg_key] is None and arg_key in self.run_conf:
                self.args.__dict__[arg_key] = self.run_conf[arg_key]
        self.annotator_names = self.args.annotators
        if self.annotator_names == None:
            self.annotators = au.get_local_module_infos_of_type('annotator')
        else:
            self.annotators = au.get_local_module_infos_by_names(self.annotator_names)
        self.excludes = self.args.excludes
        if self.excludes == ['*']:
            self.annotators = {}
        elif self.excludes != None:
            for m in self.excludes:
                if m in self.annotators:
                    del self.annotators[m]
        self.inputs = [os.path.abspath(x) for x in self.args.inputs]
        self.run_name = self.args.run_name
        if self.run_name == None:
            self.run_name = os.path.basename(self.inputs[0])
            if len(self.inputs) > 1:
                self.run_name += '_and_'+str(len(self.inputs)-1)+'_files'
        if self.inputs[0].endswith('.sqlite'):
            self.append_mode = True  
            if self.run_name.endswith('.sqlite'):
                self.run_name = self.run_name[:-7]
        self.output_dir = self.args.output_dir
        if self.output_dir == None:
            self.output_dir = os.path.dirname(os.path.abspath(self.inputs[0]))
        else:
            self.output_dir = os.path.abspath(self.output_dir)
        if os.path.exists(self.output_dir) == False:
            os.mkdir(self.output_dir)
        if self.args.verbose == True:
            self.verbose = True
        else:
            self.verbose = False
        self.reports = self.args.reports
        if self.reports is None:
            self.reports = ['excel']
        if self.args.liftover is None:
            if constants.default_assembly_key in self.cravat_conf:
                self.input_assembly = self.cravat_conf[constants.default_assembly_key]
            else:
                msg = 'Genome assembly should be given (as one of {}) with -l option or a default genome assembly should be defined in {} as default_assembly.'.format(
                    ', '.join(constants.assembly_choices), 
                    os.path.join(constants.conf['conf_dir'],'cravat.yml'),
                )
                print(msg)
                exit()
        else:
            self.input_assembly = self.args.liftover
        if self.args.repeat is None:
            self.args.repeat = []
        if self.args.skip is None:
            self.args.skip = []
        if self.args.startat == 'postaggregator':
            self.args.startat = 'aggregator'
        if 'postaggregator' in self.args.repeat and not 'aggregator' in self.args.repeat:
            self.args.repeat.append('aggregator')
        if self.append_mode:
            self.args.endat = 'aggregator'
        try:
            self.startlevel = self.runlevels[self.args.startat]
        except KeyError:
            self.startlevel = 0
        try:
            self.endlevel = self.runlevels[self.args.endat]
        except KeyError:
            self.endlevel = max(self.runlevels.values())
        self.cleandb = self.args.cleandb
        if self.args.newlog == True:
            self.logmode = 'w'
        else:
            self.logmode = 'a'
        if self.args.note == None:
            self.args.note = ''

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
        
        if self.append_mode:
            self.regenerate_from_db()
    
    def regenerate_from_db (self):
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
            colnames = [x['name'] for x in constants.crx_def]
            sel_cols = ', '.join(['base__'+x for x in colnames])
            q = f'select {sel_cols} from variant'
            c.execute(q)
            for r in c:
                rd = {x[0]:x[1] for x in zip(colnames,r)}
                if crv:
                    crv.write_data(rd)
                if crx:
                    crx.write_data(rd)
            crv.close()
            crx.close()
            self.crv_present = True
            self.crx_present = True
        # Gene
        if not self.crg_present:
            crg = CravatWriter(self.crginput, columns=constants.crg_def)
            crg.write_definition()
            colnames = [x['name'] for x in constants.crg_def]
            sel_cols = ', '.join(['base__'+x for x in colnames])
            q = f'select {sel_cols} from gene'
            c.execute(q)
            for r in c:
                rd = {x[0]:x[1] for x in zip(colnames,r)}
                crg.write_data(rd)
            crg.close()
            self.crg_present = True
        c.close()
        db.close()

    def populate_secondary_annotators (self):
        secondaries = {}
        for module in self.annotators.values():
            self._find_secondary_annotators(module, secondaries)
        self.annotators.update(secondaries)
        annot_names = [v.name for v in self.annotators.values()]
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
        if self.startlevel <= self.runlevels['annotator']:
            self.status_writer.queue_status_update('annotators', annot_names, force=True)
        self.annot_names = annot_names

    def _find_secondary_annotators (self, module, ret):
        sannots = self.get_secondary_modules(module)
        for sannot in sannots:
            ret[sannot.name] = sannot
            self._find_secondary_annotators(sannot, ret)

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
        if module.name in self.cravat_conf:
            if module.name in self.modules_conf:
                confs = json.dumps(self.modules_conf[module.name])
                confs = "'" + confs.replace("'", '"') + "'"
                cmd.extend(['--confs', confs])
        if self.args.forcedinputformat is not None:
            cmd.extend(['-f', self.args.forcedinputformat])
        if self.args.unique_variants:
            cmd.append('-u')
        self.announce_module(module)
        if self.verbose:
            print(' '.join(cmd))
        converter_class = util.load_class('MasterCravatConverter', module.script_path)
        converter = converter_class(cmd, self.status_writer)
        self.numinput, self.converter_format = converter.run()

    def run_genemapper (self):
        module = au.get_local_module_info(
            self.cravat_conf['genemapper'])
        self.genemapper = module
        cmd = [module.script_path, 
               self.crvinput,
               '-n', self.run_name,
               '-d', self.output_dir]
        if module.name in self.cravat_conf:
            confs = json.dumps(self.cravat_conf[module.name])
            confs = "'" + confs.replace("'", '"') + "'"
            cmd.extend(['--confs', confs])
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
        if self.append_mode:
            cmd.append('--append')
        if self.verbose:
            print(' '.join(cmd))
        self.update_status('Running {title} ({level})'.format(title='Aggregator', level='variant'))
        v_aggregator = Aggregator(cmd, self.status_writer)
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
        if self.append_mode:
            cmd.append('--append')
        if self.verbose:
            print(' '.join(cmd))
        self.update_status('Running {title} ({level})'.format(title='Aggregator', level='gene'))
        g_aggregator = Aggregator(cmd, self.status_writer)
        g_aggregator.run()
        rtime = time.time() - stime
        print('finished in {0:.3f}s'.format(rtime))

        # Sample level
        if not self.append_mode:
            print('\t{0:30s}\t'.format('Samples'), end='', flush=True)
            stime = time.time()
            cmd = ['donotremove', 
                '-i', self.output_dir,
                '-d', self.output_dir, 
                '-l', 'sample',
                '-n', self.run_name]
            if self.verbose:
                print(' '.join(cmd))
            self.update_status('Running {title} ({level})'.format(title='Aggregator', level='sample'))
            s_aggregator = Aggregator(cmd, self.status_writer)
            s_aggregator.run()
            rtime = time.time() - stime
            print('finished in {0:.3f}s'.format(rtime))

        # Mapping level
        if not self.append_mode:
            print('\t{0:30s}\t'.format('Tags'), end='', flush=True)
            cmd = ['donotremove', 
                '-i', self.output_dir,
                '-d', self.output_dir, 
                '-l', 'mapping',
                '-n', self.run_name]
            if self.verbose:
                print(' '.join(cmd))
            self.update_status('Running {title} ({level})'.format(title='Aggregator', level='mapping'))
            m_aggregator = Aggregator(cmd, self.status_writer)
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
            if module.name in self.cravat_conf:
                confs = json.dumps(self.cravat_conf[module.name])
                confs = "'" + confs.replace("'", '"') + "'"
                cmd.extend(['--confs', confs])
            if self.verbose:
                print(' '.join(cmd))
            post_agg_cls = util.load_class('CravatPostAggregator', module.script_path)
            post_agg = post_agg_cls(cmd, self.status_writer)
            stime = time.time()
            post_agg.run()
            rtime = time.time() - stime
            print('finished in {0:.3f}s'.format(rtime))

    async def run_reporter (self):
        if self.reports != None:
            module_names = [v + 'reporter' for v in self.reports]
        else:
            module_names = [self.cravat_conf['reporter']]
        all_reporters_ran_well = True
        for module_name in module_names:
            try:
                module = au.get_local_module_info(module_name)
                self.announce_module(module)
                if module is None:
                    print('        {} does not exist.'.format(module_name))
                    continue
                #print('')
                cmd = [module.script_path, 
                       '-s', os.path.join(self.output_dir, self.run_name),
                       os.path.join(self.output_dir, self.run_name + '.sqlite'),
                       '--module-name', module_name]
                if self.run_conf_path is not None:
                    cmd.extend(['-c', self.run_conf_path])
                if module_name in self.cravat_conf:
                    confs = json.dumps(self.cravat_conf[module_name])
                    confs = "'" + confs.replace("'", '"') + "'"
                    cmd.extend(['--confs', confs])
                cmd.append('--inputfiles')
                for input_file in self.inputs:
                    cmd.append(input_file)
                if self.args.separatesample:
                    cmd.append('--separatesample')
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
        num_workers = au.get_max_num_concurrent_annotators_per_job()
        if self.args.mp is not None:
            try:
                self.args.mp = int(self.args.mp)
                if self.args.mp >= 1:
                    num_workers = self.args.mp
            except:
                self.logger.exception('error handling mp argument:')
        self.logger.info('num_workers: {}'.format(num_workers))
        run_args = {}
        for module in self.run_annotators.values():
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
                    secondary_module = self.annotators[secondary_module_name]
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
            if module.name in self.cravat_conf:
                confs = json.dumps(self.cravat_conf[module.name])
                confs = "'" + confs.replace("'", '"') + "'"
                cmd.extend(['--confs', confs])
            run_args[module.name] = (module, cmd)
        self.logger.removeHandler(self.log_handler)
        start_queue = self.manager.Queue()
        end_queue = self.manager.Queue()
        all_mnames = set(self.run_annotators)
        assigned_mnames = set()
        done_mnames = set(self.done_annotators)
        queue_populated = self.manager.Value('c_bool',False)
        pool_args = [[start_queue, end_queue, queue_populated, self.status_writer]]*num_workers
        with mp.Pool(processes=num_workers) as pool:
            results = pool.starmap_async(annot_from_queue, pool_args, error_callback=lambda e, mp_pool=pool: mp_pool.terminate())
            pool.close()
            for mname, module in self.run_annotators.items():
                if mname not in assigned_mnames and set(module.secondary_module_names) <= done_mnames:
                    start_queue.put(run_args[mname])
                    assigned_mnames.add(mname)
            while assigned_mnames != all_mnames: #TODO not handling case where parent module errors out
                finished_module = end_queue.get()
                done_mnames.add(finished_module)
                for mname, module in self.annotators.items():
                    if mname not in assigned_mnames and set(module.secondary_module_names) <= done_mnames:
                        start_queue.put(run_args[mname])
                        assigned_mnames.add(mname)
            queue_populated = True
            pool.join()
        try:
            for _ in results.get():
                pass
        except Exception as e:
            self.handle_exception(e)
        self.log_path = os.path.join(self.output_dir, self.run_name + '.log')
        self.log_handler = logging.FileHandler(self.log_path, 'a')
        formatter = logging.Formatter('%(asctime)s %(name)-20s %(message)s', '%Y/%m/%d %H:%M:%S')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
        if len(self.run_annotators) > 0:
            self.annotator_ran = True

    def table_exists (self, cursor, table):
        sql = 'select name from sqlite_master where type="table" and ' +\
            'name="' + table + '"'
        cursor.execute(sql)
        if cursor.fetchone() == None:
            return False
        else:
            return True

    async def write_job_info (self):
        dbpath = os.path.join(self.output_dir, self.run_name + '.sqlite')
        conn = await aiosqlite3.connect(dbpath)
        cursor = await conn.cursor()
        if not self.append_mode:
            q = 'drop table if exists info'
            await cursor.execute(q)
            q = 'create table info (colkey text primary key, colval text)'
            await cursor.execute(q)
        modified = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        q = 'insert or replace into info values ("Result modified at", "' + modified + '")'
        await cursor.execute(q)
        if not self.append_mode:
            created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            q = 'insert into info values ("Result created at", "' + created + '")'
            await cursor.execute(q)
            q = 'insert into info values ("Input file name", "{}")'.format(';'.join(self.inputs)) #todo adapt to multiple inputs
            await cursor.execute(q)
            q = 'insert into info values ("Input genome", "' + self.input_assembly + '")'
            await cursor.execute(q)
            q = 'select count(*) from variant'
            await cursor.execute(q)
            r = await cursor.fetchone()
            no_input = str(r[0])
            q = 'insert into info values ("Number of unique input variants", "' + no_input + '")'
            await cursor.execute(q)
            q = 'insert into info values ("open-cravat", "{}")'.format(self.pkg_ver)
            await cursor.execute(q)
            if hasattr(self, 'converter_format'):
                q = 'insert into info values ("_converter_format", "{}")'.format(self.converter_format)
                await cursor.execute(q)
            if hasattr(self, 'genemapper'):
                version = self.genemapper.conf['version']
                title = self.genemapper.conf['title']
                modulename = self.genemapper.name
                genemapper_str = '{} ({})'.format(title, version)
                q = 'insert into info values ("Gene mapper", "{}")'.format(genemapper_str)
                await cursor.execute(q)
                q = 'insert into info values ("_mapper", "{}:{}")'.format(modulename, version)
                await cursor.execute(q)
            f = open(os.path.join(self.output_dir, self.run_name + '.crm'))
            for line in f:
                if line.startswith('#input_paths='):
                    input_path_dict_str = '='.join(line.strip().split('=')[1:]).replace('"', "'")
                    q = 'insert into info values ("_input_paths", "{}")'.format(input_path_dict_str)
                    await cursor.execute(q)
        q = 'select colval from info where colkey="annotators_desc"'
        await cursor.execute(q)
        r = await cursor.fetchone()
        if r is None:
            annotator_desc_dict = {}
        else:
            annotator_desc_dict = json.loads(r[0])
        q = 'select name, displayname, version from variant_annotator'
        await cursor.execute(q)
        rows = list(await cursor.fetchall())
        q = 'select name, displayname, version from gene_annotator'
        await cursor.execute(q)
        tmp_rows = list(await cursor.fetchall())
        if tmp_rows is not None:
            rows.extend(tmp_rows)
        annotators_str = ''
        annotator_version = {}
        annotators = []
        for row in rows:
            (name, displayname, version) = row
            if name in ['base', 'tagsampler', 'hg19', 'hg18']:
                continue
            if version is not None and version != '':
                annotators_str += '{} ({}), '.format(displayname, version)
                annotators.append('{}:{}'.format(name, version))
            else:
                annotators_str += '{}, '.format(displayname)
                annotators.append('{}:'.format(name))
            annotator_version[name] = version
            module_info = au.get_local_module_info(name)
            if module_info is not None and module_info.conf is not None:
                annotator_desc_dict[name] = module_info.conf['description']
        q = 'insert or replace into info values ("_annotator_desc", "{}")'.format(json.dumps(annotator_desc_dict).replace('"', "'"))
        await cursor.execute(q)
        self.status_writer.queue_status_update('annotator_version', annotator_version)
        q = 'insert or replace into info values ("Annotators", "' + annotators_str + '")'
        await cursor.execute(q)
        q = 'insert or replace into info values ("_annotators", "{}")'.format(','.join(annotators))
        await cursor.execute(q)
        await conn.commit()
        await cursor.close()
        await conn.close()

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

    def clean_up_at_end (self):
        fns = os.listdir(self.output_dir)
        for fn in fns:
            fn_path = os.path.join(self.output_dir, fn)
            if os.path.isfile(fn_path) == False:
                continue
            if fn.startswith(self.run_name):
                fn_end = fn.split('.')[-1]
                if fn_end in ['var', 'gen', 'crv', 'crx', 'crg', 'crs', 'crm', 'crt', 'json']:
                    os.remove(os.path.join(self.output_dir, fn))

def run_cravat_job(**kwargs):
    module = Cravat(**kwargs)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(module.main())

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

    '''
    def add_annotator_version_to_status_json (self, annotator_name, version):
        if 'annotator_version' not in self.status_json:
            self.status_json['annotator_version'] = {}
        self.status_json['annotator_version'][annotator_name] = version
        self.queue_status_update('annotator_version', self.status_json['annotator_version'])
    '''

    def queue_status_update (self, k, v, force=False):
        self.status_json[k] = v
        if force == True or\
                (time.time() - self.t > 3 and self.lock == False):
            self.lock = True
            self.update_status_json()
            self.t = time.time()
            self.lock = False

    def update_status_json (self):
        with open(self.status_json_path, 'w') as wf:
            json.dump(self.status_json, wf, indent=2, sort_keys=True)

    def get_status_json (self):
        return self.status_json

    def flush (self):
        self.lock = True
        self.update_status_json()
        self.t = time.time()
        self.lock = False
