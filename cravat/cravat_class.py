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
from logging.handlers import QueueListener

cravat_cmd_parser = argparse.ArgumentParser(
    prog='cravat input_file_path',
    description='Open-CRAVAT genomic variant interpreter. https://github.com/KarchinLab/open-cravat. Use input_file_path argument before any option.',
    epilog='* input_file_path should precede any option.')
cravat_cmd_parser.add_argument('input',
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
                    choices=['hg38', 'hg19'],
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
    
    def get_logger (self):
        self.logger = logging.getLogger('cravat')
        self.logger.setLevel('INFO')
        self.log_path = os.path.join(self.output_dir, self.run_name + '.log')
        self.log_handler = logging.FileHandler(self.log_path, mode=self.logmode)
        formatter = logging.Formatter('%(asctime)s %(name)-20s %(message)s', '%Y/%m/%d %H:%M:%S')
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)

    def close_logger (self):
        logging.shutdown()
    
    def update_status(self, status):
        status_fname = self.run_name+'.status.json'
        status_fpath = os.path.join(self.output_dir, status_fname)
        d = {
            'status': status
        }
        with open(status_fpath,'w') as wf:
            wf.write(json.dumps(d))

    def main (self):
        self.update_status('Started')
        self.set_and_check_input_files()
        self.make_module_run_list()
        try:
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
                self.run_reporter()
            self.update_status('Finished')
        except:
            self.logger.exception('<Exception>')
            self.update_status('Error')
            traceback.print_exc()
            end_time = time.time()
            self.logger.info('finished with an exception: {0}'.format(time.asctime(time.localtime(end_time))))
            runtime = end_time - self.start_time
            self.logger.info('runtime: {0:0.3f}s'.format(runtime))
            print('Finished with an exception. Runtime: {0:0.3f}s'.format(runtime))
            self.close_logger()
            return
        end_time = time.time()
        self.logger.info('finished: {0}'.format(time.asctime(time.localtime(end_time))))
        runtime = end_time - self.start_time
        self.logger.info('runtime: {0:0.3f}s'.format(runtime))
        print('Normally Finished. Runtime: {0:0.3f}s'.format(runtime))
        self.close_logger()

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
        if self.excludes == '*':
            self.annotators = {}
        elif self.excludes != None:
            for m in self.excludes:
                if m in self.annotators:
                    del self.annotators[m]
        self.input = os.path.abspath(self.args.input)
        self.run_name = self.args.run_name
        if self.run_name == None:
            self.run_name = os.path.basename(self.input)
        self.output_dir = self.args.output_dir
        if self.output_dir == None:
            self.output_dir = os.path.dirname(os.path.abspath(self.input))
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
        if self.input.split('.')[-1] == 'crv':
            self.crvinput = self.input
        else:
            self.crvinput = os.path.join(self.output_dir, self.run_name + '.crv')
        if self.input.split('.')[-1] == 'crx':
            self.crxinput = self.input
        else:
            self.crxinput = os.path.join(self.output_dir, self.run_name + '.crx')
        if self.input.split('.')[-1] == 'crg':
            self.crginput = self.input
        else:
            self.crginput = os.path.join(self.output_dir, self.run_name + '.crg')

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

    def add_annotator_to_queue (self, module):
        if module.directory == None:
            sys.exit('Module %s is not installed' % module)

        if module.name not in self.modules:
            self.modules[module.name] = module

        secondary_modules = self.get_secondary_modules(module)
        for secondary_module in secondary_modules:
            if self.args.ra == True or \
                    self.check_module_output(secondary_module) == None:
                self.add_annotator_to_queue(secondary_module)

        ordered_module_names = [m.name for m in self.ordered_annotators]
        if module.name not in ordered_module_names:
            if self.args.ra == True or \
                    self.check_module_output(module) == None:
                self.ordered_annotators.append(module)

    def check_module_output (self, module):
        paths = os.listdir(self.output_dir)
        output_path = None
        for path in paths:
            if path.startswith(self.run_name) and path.endswith(
                    module.output_suffix):
                output_path = path
                break
        return output_path

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
                self.input,
               '-n', self.run_name,
               '-d', self.output_dir,
               '-l', self.input_assembly]
        self.announce_module(module)
        if self.verbose:
            print(' '.join(cmd))
        converter_class = util.load_class('MasterCravatConverter', module.script_path)
        converter = converter_class(cmd)
        converter.run()

    def run_genemapper (self):
        module = au.get_local_module_info(
            self.conf.get_cravat_conf()['genemapper'])
        cmd = [module.script_path, 
               self.crvinput,
               '-n', self.run_name,
               '-d', self.output_dir]
        self.announce_module(module)
        if self.verbose:
            print(' '.join(cmd))
        genemapper_class = util.load_class('Mapper', module.script_path)
        genemapper = genemapper_class(cmd)
        genemapper.run()

    def run_aggregator (self):
        module = au.get_local_module_info(
            self.conf.get_cravat_conf()['aggregator'])
        aggregator_cls = util.load_class('Aggregator', module.script_path)

        # Variant level
        print('\t{0:30s}\t'.format('Variants'), end='', flush=True)
        stime = time.time()
        cmd = [module.script_path, 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'variant',
               '-n', self.run_name]
        if self.cleandb:
            cmd.append('-x')
        if self.verbose:
            print(' '.join(cmd))
        v_aggregator = aggregator_cls(cmd)
        v_aggregator.run()
        rtime = time.time() - stime
        print('finished in {0:.3f}s'.format(rtime)) 

        # Gene level
        print('\t{0:30s}\t'.format('Genes'), end='', flush=True)
        stime = time.time()
        cmd = [module.script_path, 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'gene',
               '-n', self.run_name]
        if self.verbose:
            print(' '.join(cmd))
        g_aggregator = aggregator_cls(cmd)
        g_aggregator.run()
        rtime = time.time() - stime
        print('finished in {0:.3f}s'.format(rtime))

        # Sample level
        print('\t{0:30s}\t'.format('Samples'), end='', flush=True)
        stime = time.time()
        cmd = [module.script_path, 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'sample',
               '-n', self.run_name]
        if self.verbose:
            print(' '.join(cmd))
        s_aggregator = aggregator_cls(cmd)
        s_aggregator.run()
        rtime = time.time() - stime
        print('finished in {0:.3f}s'.format(rtime))

        # Mapping level
        print('\t{0:30s}\t'.format('Tags'), end='', flush=True)
        cmd = [module.script_path, 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'mapping',
               '-n', self.run_name]
        if self.verbose:
            print(' '.join(cmd))
        m_aggregator = aggregator_cls(cmd)
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

    def run_reporter (self):
        if self.reports != None:
            module_names = [v + 'reporter' for v in self.reports]
        else:
            module_names = [self.conf.get_cravat_conf()['reporter']]
        for module_name in module_names:
            module = au.get_local_module_info(module_name)
            self.announce_module(module)
            cmd = [module.script_path, 
                   '-s', os.path.join(self.output_dir, self.run_name),
                   os.path.join(self.output_dir, self.run_name + '.sqlite'),
                   '-c', self.run_conf_path]
            if self.verbose:
                print(' '.join(cmd))
            reporter_cls = util.load_class('Reporter', module.script_path)
            reporter = reporter_cls(cmd)
            stime = time.time()
            reporter.run()
            rtime = time.time() - stime
            print('finished in {0:.3f}s'.format(rtime))

    def run_annotators (self):
        for module in self.ordered_annotators:
            stime = time.time()
            self.announce_module(module)
            self.run_annotator(module)
            rtime = time.time() - stime
            print('finished in {0:.3f}s'.format(rtime))

    def run_annotators_mp (self):
        default_workers = mp.cpu_count() - 1
        if default_workers < 1: 
            default_workers = 1
        num_workers = self.conf.get_cravat_conf().get('num_workers', default_workers)
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
                        inputpath = self.input
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
                        self.check_module_output(secondary_module)
                    if secondary_output_path == None:
                        print(secondary_module.name + ' output absent')
                        return 1
                    else:
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
        # Logging queue
        manager = mp.Manager()
        annot_log_queue = manager.Queue()
        pool_args = zip(
            self.ordered_annotators,
            all_cmds,
            len(self.ordered_annotators)*[annot_log_queue]
            )
        ql = QueueListener(annot_log_queue, *self.logger.handlers)
        with mp.Pool(processes=num_workers) as pool:
            ql.start()
            pool.starmap(run_annotator_mp, pool_args)
            ql.stop()

    def table_exists (self, cursor, table):
        sql = 'select name from sqlite_master where type="table" and ' +\
            'name="' + table + '"'
        cursor.execute(sql)
        if cursor.fetchone() == None:
            return False
        else:
            return True

    def add_annotator_displaynames (self, cursor, tab, annotators):
        if self.table_exists(cursor, tab):
            q = 'select displayname from ' + tab + '_annotator'
            cursor.execute(q)
            rs = cursor.fetchall()
            for r in rs:
                annotators[r[0]] = True

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
        q = 'insert into info values ("Input file name", "' + self.input + '")'
        cursor.execute(q)
        q = 'insert into info values ("Input genome", "' + self.input_assembly + '")'
        cursor.execute(q)
        q = 'select count(*) from variant'
        cursor.execute(q)
        no_input = str(cursor.fetchone()[0])
        q = 'insert into info values ("Number of unique input variants", "' + no_input + '")'
        cursor.execute(q)
        annotators = {}
        self.add_annotator_displaynames(cursor, 'variant', annotators)
        self.add_annotator_displaynames(cursor, 'gene', annotators)
        annotators = list(annotators.keys())
        annotators.sort(key=str.lower)
        annotators = ', '.join(annotators)
        q = 'insert into info values ("Annotators", "' + annotators + '")'
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
        self.update_status(
            'Running {title} ({name})'\
            .format(title=module.title, name=module.name)
            )
