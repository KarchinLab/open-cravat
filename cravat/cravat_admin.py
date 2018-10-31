#!/usr/bin/env python3
import argparse
import os
import yaml
import sys
import traceback
from cravat import admin_util as au
from cravat import util
from cravat import constants
from types import SimpleNamespace
import re
import textwrap
import math
import copy

class ExampleCommandsFormatter(object,):
    def __init__(self, prefix='',  cmd_indent=' '*2, desc_indent=' '*8, width=70):
        self._prefix = prefix
        self._examples = []
        self._s = 'Examples:'
        self._cmd_indent = cmd_indent
        self._desc_indent = desc_indent
        self._width = width
        
    def add_example(self, cmd, desc):
        self._s += '\n\n'
        self._s += self._cmd_indent
        if self._prefix:
            self._s += self._prefix+' '
        self._s += cmd
        # Eliminate newlines in desc
        desc = re.sub(r'\s*\n\s*',' ',desc)
        # Wrap the description
        desc = textwrap.fill(desc,self._width-len(self._desc_indent))
        desc = textwrap.indent(desc,self._desc_indent)
        self._s += '\n'+desc
       
    def __str__(self):
        return self._s
    
class InstallProgressStdout(au.InstallProgressHandler):
    def __init__ (self, module_name, module_version):
        super().__init__(module_name, module_version)
    
    def stage_start(self, stage):
        self.cur_stage = stage
        sys.stdout.write(self._stage_msg(stage)+'\n')
        
    def stage_progress(self, cur_chunk, total_chunks, cur_size, total_size):
        rem_chunks = total_chunks - cur_chunk
        perc = cur_size/total_size*100
        # trailing spaces needed to avoid leftover characters on resize
        out = '\r[{cur_prog}{rem_prog}] {cur_size} / {total_size} ({perc:.0f}%)  '\
            .format(cur_prog='*'*cur_chunk,
                    rem_prog=' '*rem_chunks,
                    cur_size = humanize_bytes(cur_size),
                    total_size = humanize_bytes(total_size),
                    perc = perc)
        sys.stdout.write(out)
        if cur_chunk == total_chunks:
            sys.stdout.write('\n')
            
def humanize_bytes(num, binary=False):
    """Human friendly file size"""
    exp2unit_dec = {0:'B',1:'kB',2:'MB',3:'GB'}
    exp2unit_bin = {0:'B',1:'KiB',2:'MiB',3:'GiB'}
    max_exponent = 3
    if binary:
        base = 1024
    else:
        base = 1000
    if num > 0:
        exponent = math.floor(math.log(num, base))
        if exponent > max_exponent:
            exponent = max_exponent
    else:
        exponent = 0
    quotient = float(num) / base**exponent
    if binary:
        unit = exp2unit_bin[exponent]
    else:
        unit = exp2unit_dec[exponent]
    quot_str = '{:.1f}'.format(quotient)
    # No decimal for byte level sizes
    if exponent == 0:
        quot_str = quot_str.rstrip('0').rstrip('.')
    return '{quotient} {unit}'.format(quotient=quot_str, unit=unit)
    
def main ():
    # Print usage if no args
    if len(sys.argv) == 1: sys.argv.append('-h')

    def yield_tabular_lines(l, col_spacing=4, indent=0):
        sl = []
        n_toks = len(l[0])
        max_lens = [0] * n_toks
        for toks in l:
            if len(toks) != n_toks:
                raise RuntimeError('Inconsistent sub-list length')
            stoks = [str(x) for x in toks]
            sl.append(stoks)
            stoks_len = [len(x) for x in stoks]
            max_lens = [max(x) for x in zip(stoks_len, max_lens)]
        for stoks in sl:
            jline = ' '*indent
            for i, stok in enumerate(stoks):
                jline += stok + ' ' * (max_lens[i] + col_spacing - len(stok))
            yield jline
    
    def print_tabular_lines(l, *kwargs):
        for line in yield_tabular_lines(l, *kwargs):
            print(line)
        
    def list_local_modules(pattern=r'.*', types=[]):
        header = ['Name','Type','Version','Size']
        all_toks = [header]
        for module_name in au.search_local(pattern):
            module_info = au.get_local_module_info(module_name)
            if len(types) > 0 and module_info.type not in types:
                continue
            size = module_info.get_size()
            toks = [module_name, module_info.type, module_info.version, humanize_bytes(size)]
            all_toks.append(toks)
        print_tabular_lines(all_toks)
                
    def list_available_modules(pattern=r'.*', types=[]):
        header = ['Name','Type','Latest version','Installed','Installed version','Up-to-date','Size']
        all_toks = [header]
        for module_name in au.search_remote(pattern):
            remote_info = au.get_remote_module_info(module_name)
            if len(types) > 0 and remote_info.type not in types:
                continue
            local_info = au.get_local_module_info(module_name)
            if local_info is not None:
                installed = True
                local_version = local_info.version
                up_to_date = local_version == remote_info.latest_version
            else:
                installed = False
                local_version = ''
                up_to_date = ''
            toks = [module_name,
                    remote_info.type,
                    remote_info.latest_version,
                    installed,
                    local_version,
                    up_to_date,
                    humanize_bytes(remote_info.size)]
            all_toks.append(toks)
        print_tabular_lines(all_toks)
    
    def list_modules(args):
        if args.available:
            list_available_modules(pattern=args.pattern, types=args.types)
        else:
            list_local_modules(pattern=args.pattern, types=args.types)
    
    def yaml_string(x):
        s = yaml.dump(x, default_flow_style = False)
        s = re.sub('!!.*', '', s)
        s = s.strip('\r\n')
        return s

    def print_info(args):
        module_name = args.module
        installed = False
        available = False
        up_to_date = False
        local_info = None
        remote_info = None
        # Remote
        try:
            remote_info = au.get_remote_module_info(module_name)
            if remote_info != None:
                available = True
        except LookupError:
            available = False
        if available:
            dump = yaml_string(remote_info)
            print(dump)
        # Local
        try:
            local_info = au.get_local_module_info(module_name)
            if local_info != None:
                installed = True
                del local_info.readme
            else:
                installed = False
        except LookupError:
            installed = False
        if installed:
            print('INSTALLED')
            if args.include_local:
                li_out = copy.deepcopy(local_info)
                del li_out.conf
                li_out.get_size()
                dump = yaml_string(li_out)
                print(dump)
        else:
            print('NOT INSTALLED')
        if installed and available:
            if installed and local_info.version == remote_info.latest_version:
                up_to_date = True
            else:
                up_to_date = False
            if up_to_date:
                print('UP TO DATE')
            else:
                print('NEWER VERSION EXISTS')
    
    def set_modules_dir(args):
        if args.directory:
            au.set_modules_dir(args.directory)
        print(au.get_modules_dir())

    def install_modules(args):
        matching_names = au.search_remote(*args.modules)
        if len(matching_names) > 1 and args.version is not None:
            print('WARNING: Version filter applied to all matching modules')
        to_install = {}
        for module_name in matching_names:
            remote_info = au.get_remote_module_info(module_name)
            if args.version is None:
                    to_install[module_name] = remote_info.latest_version
            elif remote_info.has_version(args.version):
                    to_install[module_name] = args.version
            else:
                continue
        if len(to_install) > 0:
            print('Installing: {:}'\
                  .format(', '.join([name+':'+version for name, version in sorted(to_install.items())]))
                  )
            if not(args.yes):
                while True:
                    resp = input('Proceed? (y/n) > ')
                    if resp == 'y':
                        break
                    if resp == 'n':
                        exit()
                    else:
                        print('Your response (\'{:}\') was not one of the expected responses: y, n'.format(resp))
                        continue
            for module_name, module_version in sorted(to_install.items()):
                stage_handler = InstallProgressStdout(module_name, module_version)
                au.install_module(module_name,
                                  version=module_version,
                                  force_data=args.force_data,
                                  stage_handler=stage_handler
                                  )
        else:
            print('No modules found')
                    
    def update_modules(args):
        if len(args.modules) == 0:
            requested_modules = au.list_local()
        else:
            requested_modules = au.search_local(*args.modules)
        print('Checking status')
        needs_update = []
        status_table = [['Name','Status']]
        for module_name in requested_modules:
            local_info = au.get_local_module_info(module_name)
            version = local_info.conf['version']
            if au.module_exists_remote(module_name):
                latest_version = au.get_remote_latest_version(module_name)
                if version == latest_version:
                    status = 'Up to date'
                else:
                    status = 'Requires update'
                    needs_update.append(module_name)
            else:
                status = 'No remote version'
            status_table.append([module_name, status])
        print_tabular_lines(status_table)
        if len(needs_update) == 0:
            print('All modules are up to date')
            exit()
        else:
            user_cont = input('Continue to update the following modules:\n%s\n<y/n>: '\
                              %','.join(needs_update))
            if user_cont.lower() not in ['y','yes']:
                print('Cancelling update')
                exit()
        args.modules = needs_update
        args.force_data = False
        args.version = None
        args.yes = True
        install_modules(args)
        
    def uninstall_modules (args):
        matching_names = au.search_local(*args.modules)
        if len(matching_names) > 0:
            print('Uninstalling: {:}'.format(', '.join(matching_names)))
            if not(args.yes):
                while True:
                    resp = input('Proceed? (y/n) > ')
                    if resp == 'y':
                        break
                    elif resp == 'n':
                        exit()
                    else:
                        print('Response \'{:}\' not one of (y/n).'.format(resp))
            for module_name in matching_names:
                au.uninstall_module(module_name)
                print('Uninstalled %s' %module_name)
        else:
            print('No modules found')
            
    def publish_module (args):
        print('args force yes in publish', args.force_yes)
        au.publish_module(args.module, args.user, args.password, args.overwrite_same_version, include_data=args.data)
        
    def install_base (args):
        sys_conf = au.get_system_conf()
        base_modules = sys_conf.get(constants.base_modules_key,[])
        args = SimpleNamespace(modules=base_modules,force_data=False,skip_installed=True,version=None,yes=True)
        install_modules(args)
            
    def create_account (args):
        au.create_account(args.username, args.password)
        
    def change_password (args):
        au.change_password(args.username, args.cur_pw, args.new_pw)
        
    def send_reset_email (args):
        au.send_reset_email(args.username)
        
    def send_verify_email (args):
        au.send_verify_email(args.username)
        
    def check_login (args):
        au.check_login(args.username, args.password)
    
    def make_example_input (arg):
        au.make_example_input(arg.directory)
    
    def new_annotator (args):
        au.new_annotator(args.annotator_name)
        module_info = au.get_local_module_info(args.annotator_name)
        print('Annotator {0} created at {1}'.format(args.annotator_name,
                                                    module_info.directory))
    
    def report_issue (args):
        au.report_issue()
    
    def show_system_conf (args):
        au.show_system_conf()
    
    ###########################################################################
    # PARSERS START HERE
    ###########################################################################
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(title='Commands')
    
    # md
    md_examples = ExampleCommandsFormatter(prefix='cravat-admin md')
    md_examples.add_example('','Print the current CRAVAT modules directory')
    md_examples.add_example('~/cravat-modules',
                            '''Set the cravat modules directory to ~/cravat-modules. 
                            ~/cravat-modules will be created if it does not already exist. 
                            The cravat config file cravat.yml will be copied from your current 
                            modules directory to the new one if there is not already a file 
                            named cravat.yml in the new modules directory.''')
    parser_md = subparsers.add_parser('md',
                                      help='displays or changes CRAVAT modules directory.',
                                      description='displays or changes CRAVAT modules directory.',
                                      epilog=str(md_examples),
                                      formatter_class=argparse.RawDescriptionHelpFormatter
                                      )
    parser_md.add_argument('directory',
                            nargs='?',
                            help='sets modules directory.')
    parser_md.set_defaults(func=set_modules_dir)
    
    # install-base
    parser_install_base = subparsers.add_parser('install-base',
                                                help='installs base modules.',
                                                description='installs base modules.')
    parser_install_base.set_defaults(func=install_base)
    
    # # install
    # parser_install = subparsers.add_parser('install',
    #                                        help='installs modules.',
    #                                        description='installs modules.')
    # parser_install.add_argument('modules',
    #                             nargs='+',
    #                             help='Modules to install. Format as module_name:version. Leaving version blank installs the latest version.')
    # parser_install.add_argument('-d',
    #                             '--force-data',
    #                             action='store_true',
    #                             help='Force download new data even if not needed.')
    # parser_install.add_argument('--skip-installed',
    #                             action='store_true',
    #                             help='skips already installed modules.')
    # parser_install.set_defaults(func=install_modules)

    # install
    parser_install = subparsers.add_parser('install',
                                           help='installs modules.',
                                           description='installs modules.')
    parser_install.add_argument('modules',
                                nargs='+',
                                help='Modules to install. May be regular expressions.')
    parser_install.add_argument('-v','--version',
                                help='Version to install. Will apply to all modules. Default is latest version for each module')
    parser_install.add_argument('-d',
                                '--force-data',
                                action='store_true',
                                help='Force download new data even if not needed.')
    parser_install.add_argument('--skip-installed',
                                action='store_true',
                                help='skips already installed modules.')
    parser_install.add_argument('-y','--yes',
                                action='store_true',
                                help='Proceed without prompt')
    parser_install.set_defaults(func=install_modules)
    
    # update
    update_examples = ExampleCommandsFormatter(prefix='cravat-admin update')
    update_examples.add_example('', 
                                '''Enter an interactive update process. Cravat 
                                   will check to see which modules need to
                                   be updated, and will ask you if you wish to update them.''')
    update_examples.add_example('hg38 aggregator vcf-converter',
                                '''Only attempt update on the hg38, aggregator,
                                   and vcf-converter modules.''')
    parser_update = subparsers.add_parser('update',
                                           help='updates modules.',
                                           description='updates modules.',
                                           epilog=str(update_examples),
                                           formatter_class=argparse.RawDescriptionHelpFormatter)
    parser_update.add_argument('modules',
                                nargs='*',
                                help='Modules to update.')
    parser_update.set_defaults(func=update_modules)
    
    # uninstall
    parser_uninstall = subparsers.add_parser('uninstall',
                                          help='uninstalls modules.')
    parser_uninstall.add_argument('modules',
                               nargs='+',
                               help='Modules to uninstall')
    parser_uninstall.add_argument('-y','--yes',
                                  action='store_true',
                                  help='Proceed without prompt')
    parser_uninstall.set_defaults(func=uninstall_modules)
    
    # info
    parser_info = subparsers.add_parser('info',
                                        help='shows module information.')
    parser_info.add_argument('module',
                             help='Module to get info about')
    parser_info.add_argument('-l','--include-local',
                             dest='include_local',
                             help='Include local info',
                             action='store_true')
    parser_info.set_defaults(func=print_info)
    
    # ls
    ls_examples = ExampleCommandsFormatter(prefix='cravat-admin ls')
    ls_examples.add_example('', 'List installed modules')
    ls_examples.add_example('-t annotator', 'List installed annotators')
    ls_examples.add_example('-a', 'List all modules available on the store')
    ls_examples.add_example('-a -t mapper', 'List all mappers available on the store')
    parser_ls = subparsers.add_parser('ls',
                                       help='lists modules.',
                                       description='lists modules.',
                                       epilog=str(ls_examples),
                                       formatter_class=argparse.RawDescriptionHelpFormatter)
    parser_ls.add_argument('pattern',
                            nargs='?',
                            default=r'.*',
                            help='Regular expression for module names')
    parser_ls.add_argument('-a','--available',
                           action='store_true',
                           help='Include available modules')
    parser_ls.add_argument('-t','--types',
                           nargs='+',
                           default=[],
                           help='Only list modules of certain types')
    parser_ls.set_defaults(func=list_modules)
    
    # publish
    parser_publish = subparsers.add_parser('publish',
                                           help='publishes a module.')
    parser_publish.add_argument('module',
                                help='module to publish')
    data_group = parser_publish.add_mutually_exclusive_group(required=True)
    data_group.add_argument('-d',
                            '--data',
                            action='store_true',
                            default=False,
                            help='publishes module with data.')
    data_group.add_argument('-c',
                            '--code',
                            action='store_true',
                            help='publishes module without data.')
    parser_publish.add_argument('-u',
                                '--user',
                                required=True,
                                help='user to publish as. Typically your email.'
                                )
    parser_publish.add_argument('-p',
                                '--password',
                                required=True,
                                help='password for the user.')
    parser_publish.add_argument('--force-yes',
                                default=False,
                                action='store_true',
                                help='overrides yes to overwrite question')
    parser_publish.add_argument('--overwrite-same-version',
                                default=False,
                                action='store_true',
                                help='overwrites the same version already published.')
    parser_publish.set_defaults(func=publish_module)
    
    # create-account
    parser_create_account = subparsers.add_parser('create-account',
                                                  help='creates a CRAVAT store developer account.')
    parser_create_account.add_argument('username',
                                       help='use your email as your username.')
    parser_create_account.add_argument('password',
                                       help='this is your password.')
    parser_create_account.set_defaults(func=create_account)
    
    # change-password
    parser_change_password = subparsers.add_parser('change-password',
                                                   help='changes CRAVAT store account password.')
    parser_change_password.add_argument('username',
                                        help='username')
    parser_change_password.add_argument('cur_pw',
                                        help='current password')
    parser_change_password.add_argument('new_pw',
                                        help='new password')
    parser_change_password.set_defaults(func=change_password)
    
    # reset-password
    parser_reset_pw = subparsers.add_parser('reset-password',
                                            help='resets CRAVAT store account password.')
    parser_reset_pw.add_argument('username',
                                 help='username')
    parser_reset_pw.set_defaults(func=send_reset_email)
    
    # verify-email
    parser_verify_email = subparsers.add_parser('verify-email',
                                              help='sends a verification email.')
    parser_verify_email.add_argument('username',
                                     help='username')
    parser_verify_email.set_defaults(func=send_verify_email)
    
    # check-login
    parser_check_login = subparsers.add_parser('check-login',
                                               help='checks username and password.')
    parser_check_login.add_argument('username',
                                   help='username')
    parser_check_login.add_argument('password',
                                   help='password')
    parser_check_login.set_defaults(func=check_login)
    
    # test input file
    parser_make_example_input = subparsers.add_parser('make-example-input',
                                                      help='makes a file with example input variants.')
    parser_make_example_input.add_argument('directory', default='',
                                           help='Directory to make the example input file in')
    parser_make_example_input.set_defaults(func=make_example_input)

    # new-annotator
    parser_new_annotator = subparsers.add_parser('new-annotator',
                                               help='creates a new annotator')
    parser_new_annotator.add_argument('annotator_name',
                                   help='Annotator name')
    parser_new_annotator.set_defaults(func=new_annotator)
    
    # opens issue report
    parser_new_annotator = subparsers.add_parser('report-issue',
                                               help='opens a browser window to report issues')
    parser_new_annotator.set_defaults(func=report_issue)
    
    # shows system conf content.
    parser_new_annotator = subparsers.add_parser('show-system-conf',
                                               help='shows system configuration.')
    parser_new_annotator.set_defaults(func=show_system_conf)
    
    ###########################################################################
    
    args = parser.parse_args()
    args.func(args) 
    
if __name__ == '__main__':
    main()
