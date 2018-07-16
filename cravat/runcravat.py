import argparse
import os
import sys
from cravat import admin_util as au
from cravat import util
from cravat import ConfigLoader
import sqlite3
import datetime
from types import SimpleNamespace
from cravat.constants import liftover_chain_paths

class Cravat (object):
    def __init__ (self, cmd_args):
        self.should_run_converter = False
        self.should_run_genemapper = False
        self.should_run_annotators = True
        self.should_run_aggregator = True
        self.should_run_reporter = True
        self.pythonpath = sys.executable
        self.annotators = {}
        parser = argparse.ArgumentParser()
        parser.add_argument('path',
                            help='Path to the Cravat python module, or cravat executable')
        parser.add_argument('input',
                            help='path to input file')
        parser.add_argument('-a',
                            nargs="+",
                            dest='annotators',
                            help='annotators to run')
        parser.add_argument('-e',
                            nargs='+',
                            dest='excludes',
                            help='annotators to exclude')
        parser.add_argument('-n',
                            dest='run_name',
                            help='name of cravat run')
        parser.add_argument('-d',
                            dest='output_dir',
                            default=None,
                            help='directory for output files')
        parser.add_argument('--rc',
                            dest='rc',
                            action='store_true',
                            default=False,
                            help='runs converter, gene mapper, annotators, aggregator, and reporter.')
        parser.add_argument('--rm',
                            dest='rm',
                            action='store_true',
                            default=False,
                            help='runs gene mapper, annotators, aggregator, and reporter.')
        parser.add_argument('--ra',
                            dest='ra',
                            action='store_true',
                            default=False,
                            help='runs annotators, aggregator, and reporter.')
        parser.add_argument('--ec',
                            dest='ec',
                            action='store_true',
                            default=False,
                            help='runs converter and ends.')
        parser.add_argument('--em',
                            dest='em',
                            action='store_true',
                            default=False,
                            help='runs converter and gene mapper and ends.')
        parser.add_argument('--ea',
                            dest='ea',
                            action='store_true',
                            default=False,
                            help='runs converter, gene mapper, and annotators and ends.')
        parser.add_argument('--sc',
                            dest='sc',
                            action='store_true',
                            default=False,
                            help='skips converter.')
        parser.add_argument('--sm',
                            dest='sm',
                            action='store_true',
                            default=False,
                            help='skips gene mapper.')
        parser.add_argument('--sa',
                            dest='sa',
                            action='store_true',
                            default=False,
                            help='skips annotators.')
        parser.add_argument('-c',
                            dest='conf',
                            help='path to a conf file')
        parser.add_argument('--cs',
                            dest='confs',
                            help='configuration string')
        parser.add_argument('-v', 
                            dest='verbose',
                            action='store_true',
                            default=False,
                            help='verbose')
        parser.add_argument('-t',
                            nargs='+',
                            dest='reports',
                            help='report types. If omitted, default one in cravat.yml is used.')
        parser.add_argument('-l',
                            dest='liftover',
                            choices=['hg38']+list(liftover_chain_paths.keys()),
                            default='hg38',
                            help='reference genome of input. CRAVAT will lift over to hg38 if needed.')
        parser.add_argument('-x',
                            dest='cleandb',
                            action='store_true',
                            help='deletes the existing result database and ' +
                                 'creates a new one.')
        '''
        parser.add_argument('-M',
                            dest='mapperonly',
                            action='store_true',
                            default=False,
                            help='Only convert and map.')
        parser.add_argument('-s',
                            nargs="+",
                            dest='summarizers',
                            help='summarizers to run')
        parser.add_argument('-F', 
                            dest='forceall',
                            action='store_true',
                            help='re-runs converter, mapper, and ' + 
                                'annotators.')
        parser.add_argument('-f', 
                            dest='forceannot',
                            action='store_true',
                            help='re-runs annotators.')
        parser.add_argument('-A',
                            dest='aggregateandreport',
                            action='store_true',
                            default=False,
                            help='only aggregate and report.')
        parser.add_argument('-N',
                            dest='noannot',
                            action='store_true',
                            default=False,
                            help='does not annotate.')
        '''
        self.cmd_arg_parser = parser
        self.parse_cmd_args(cmd_args)
        self.conf = ConfigLoader(job_conf_path=self.run_conf_path)
        if self.args.confs != None:
            self.conf.override_cravat_conf(
                self.args.confs.replace("'", '"'))
    
    def main (self):
        self.set_and_check_input_files()
        self.make_module_run_list()
        if self.crv_present == False:
            self.should_run_converter = True
        if self.crx_present == False and not self.ra:
            self.should_run_genemapper = True
        if self.should_run_converter and not self.sc:
            print('Running converter...')
            self.run_converter()
        if self.ec:
            exit()
        if self.should_run_genemapper and not self.sm:
            print('Running gene mapper...')
            self.run_genemapper()
        if self.em:
            exit()
        if self.should_run_annotators and not self.sa:
            print('Running annotators...')
            self.run_annotators()
        if self.ea:
            exit()
        if self.should_run_aggregator:
            print('Running aggregator...')
            self.run_aggregator()
            print('Writing job info...')
            self.write_job_info()
            print('Running post-aggregators...')
            self.run_postaggregators()
        if self.should_run_reporter:
            print('Running reporter...')
            self.run_reporter()
    def parse_cmd_args(self, cmd_args):
        self.args = self.cmd_arg_parser.parse_args(cmd_args)
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
        self.rc = self.args.rc
        self.rm = self.args.rm
        self.ra = self.args.ra
        self.ec = self.args.ec
        self.em = self.args.em
        self.ea = self.args.ea
        self.sc = self.args.sc
        self.sm = self.args.sm
        self.sa = self.args.sa
        if self.rc:
            self.should_run_converter = True
            self.should_run_genemapper = True
            self.should_run_annotator = True
            self.should_run_aggregator = True
            self.should_run_reporter = True
        if self.rm:
            self.should_run_converter = False
            self.should_run_genemapper = True
            self.should_run_annotators = True
            self.should_run_aggregator = True
            self.should_run_reporter = True
        if self.ra:
            self.should_run_converter = False
            self.should_run_genemapper = False
            self.should_run_annotators = True
            self.should_run_aggregator = True
            self.should_run_reporter = True
        self.cleandb = self.args.cleandb
    
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
            if self.ra == True or \
                    self.check_module_output(secondary_module) == None:
                self.add_annotator_to_queue(secondary_module)
        
        ordered_module_names = [m.name for m in self.ordered_annotators]
        if module.name not in ordered_module_names:
            if self.ra == True or \
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
            print('    '.join(cmd))
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
            print('    '.join(cmd))
        genemapper_class = util.load_class('Mapper', module.script_path)
        genemapper = genemapper_class(cmd)
        genemapper.run()
        
    def run_aggregator (self):
        module = au.get_local_module_info(
            self.conf.get_cravat_conf()['aggregator'])
        aggregator_cls = util.load_class('Aggregator', module.script_path)

        # Variant level
        print('    Variants')
        cmd = [module.script_path, 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'variant',
               '-n', self.run_name]
        if self.cleandb:
            cmd.append('-x')
        if self.verbose:
            print('    '.join(cmd))
        v_aggregator = aggregator_cls(cmd)
        v_aggregator.run() 
        
        # Gene level
        print('    Genes')
        cmd = [module.script_path, 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'gene',
               '-n', self.run_name]
        if self.verbose:
            print('    '.join(cmd))
        g_aggregator = aggregator_cls(cmd)
        g_aggregator.run()
        
        
        # Sample level
        print('    Samples')
        cmd = [module.script_path, 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'sample',
               '-n', self.run_name]
        if self.verbose:
            print('    '.join(cmd))
        s_aggregator = aggregator_cls(cmd)
        s_aggregator.run()
        
        # Mapping level
        print('    Tags')
        cmd = [module.script_path, 
               '-i', self.output_dir,
               '-d', self.output_dir, 
               '-l', 'mapping',
               '-n', self.run_name]
        if self.verbose:
            print('    '.join(cmd))
        m_aggregator = aggregator_cls(cmd)
        m_aggregator.run()
    
    def run_postaggregators (self):
        modules = au.get_local_module_infos_of_type('postaggregator')
        for module_name in modules:
            module = modules[module_name]
            self.announce_module(module)
            cmd = [module.script_path, 
                   '-d', self.output_dir, 
                   '-n', self.run_name]
            if self.verbose:
                print('    '.join(cmd))
            post_agg_cls = util.load_class('CravatPostAggregator', module.script_path)
            post_agg = post_agg_cls(cmd)
            post_agg.run()
    
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
                print('     '.join(cmd))
            reporter_cls = util.load_class('Reporter', module.script_path)
            reporter = reporter_cls(cmd)
            reporter.run()

    def run_annotators (self):
        for module in self.ordered_annotators:
            self.announce_module(module)
            self.run_annotator(module)
            
    def run_annotator (self, module, opts=[]):
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
        cmd.extend(opts)
        cmd.extend(secondary_opts)
        if self.run_name != None:
            cmd.extend(['-n', self.run_name])
        if self.output_dir != None:
            cmd.extend(['-d', self.output_dir])
        if self.verbose:
            print('    '.join(cmd))
        annotator_class = util.load_class("CravatAnnotator", module.script_path)
        annotator = annotator_class(cmd)
        annotator.run()
    
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
            print('    '.join(cmd))
        summarizer_cls = util.load_class('', module.script_path)
        summarizer = summarizer_cls(cmd)
        summarizer.run()
    
    def announce_module (self, module):
        print('    ' + module.title + ' (' + module.name + ')')

def main ():
    module = Cravat(sys.argv)
    module.main()

if __name__ ==  '__main__':
    main()
