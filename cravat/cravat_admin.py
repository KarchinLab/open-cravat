#!/usr/bin/env python3
import argparse
import os
import oyaml as yaml
import sys
import traceback
from cravat import admin_util as au
from cravat import util
from cravat import constants
from types import SimpleNamespace
import re
import textwrap
import copy
from getpass import getpass
from distutils.version import LooseVersion
from cravat import util


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
                    cur_size = util.humanize_bytes(cur_size),
                    total_size = util.humanize_bytes(total_size),
                    perc = perc)
        sys.stdout.write(out)
        if cur_chunk == total_chunks:
            sys.stdout.write('\n')

def yield_tabular_lines(l, col_spacing=2, indent=0):
    if not l:
        return
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

def list_local_modules(pattern=r'.*', types=[], include_hidden=False, tags=[], quiet=False, raw_bytes=False):
    if quiet:
        all_toks = []
    else:
        header = ['Name', 'Title', 'Type','Version','Data source ver','Size']
        all_toks = [header]
    for module_name in au.search_local(pattern):
        module_info = au.get_local_module_info(module_name)
        if len(types) > 0 and module_info.type not in types:
            continue
        if len(tags) > 0:
            if module_info.tags is None:
                continue
            if len(set(tags).intersection(module_info.tags)) == 0:
                continue
        if module_info.hidden and not include_hidden:
            continue
        if quiet:
            toks = [module_name]
        else:
            size = module_info.get_size()
            toks = [module_name, module_info.title, module_info.type, module_info.version, module_info.datasource]
            if raw_bytes:
                toks.append(size)
            else:
                toks.append(util.humanize_bytes(size))
        all_toks.append(toks)
    print_tabular_lines(all_toks)

def list_available_modules(pattern=r'.*', types=[], include_hidden=False, tags=[], quiet=False, raw_bytes=False):
    if quiet:
        all_toks = []
    else:
        header = ['Name', 'Title', 'Type','Installed', 'Store ver','Store data ver', 'Local ver', 'Local data ver', 'Size']
        all_toks = [header]
    for module_name in au.search_remote(pattern):
        remote_info = au.get_remote_module_info(module_name)
        if len(types) > 0 and remote_info.type not in types:
            continue
        if len(tags) > 0:
            if remote_info.tags is None:
                continue
            if len(set(tags).intersection(remote_info.tags)) == 0:
                continue
        if remote_info.hidden and not include_hidden:
            continue
        local_info = au.get_local_module_info(module_name)
        if local_info is not None:
            installed = 'yes'
            local_version = local_info.version
            local_datasource = local_info.datasource
        else:
            installed = ''
            local_version = ''
            local_datasource = ''
        if quiet:
            toks = [module_name]
        else:
            toks = [
                module_name,
                remote_info.title,
                remote_info.type,
                installed,
                remote_info.latest_version,
                remote_info.datasource,
                local_version,
                local_datasource,
            ]
            if raw_bytes:
                toks.append(remote_info.size)
            else:
                toks.append(util.humanize_bytes(remote_info.size))
        all_toks.append(toks)
    print_tabular_lines(all_toks)

def list_modules(args):
    if args.available:
        list_available_modules(pattern=args.pattern, types=args.types, include_hidden=args.include_hidden, tags=args.tags, quiet=args.quiet, raw_bytes=args.raw_bytes)
    else:
        list_local_modules(pattern=args.pattern, types=args.types, include_hidden=args.include_hidden, tags=args.tags, quiet=args.quiet, raw_bytes=args.raw_bytes)

def yaml_string(x):
    s = yaml.dump(x, default_flow_style = False)
    s = re.sub('!!.*', '', s)
    s = s.strip('\r\n')
    return s

def print_info(args):
    if args.md is not None:
        constants.custom_modules_dir = args.md
    module_name = args.module
    installed = False
    remote_available = False
    up_to_date = False
    local_info = None
    remote_info = None
    # Remote
    try:
        remote_info = au.get_remote_module_info(module_name)
        if remote_info != None:
            remote_available = True
    except LookupError:
        remote_available = False
    # Local
    release_note = {}
    try:
        local_info = au.get_local_module_info(module_name)
        if local_info != None:
            installed = True
            del local_info.readme
            release_note = local_info.conf.get('release_note', {})
        else:
            installed = False
    except LookupError:
        installed = False
    if remote_available:
        versions = remote_info.versions
        data_sources = remote_info.data_sources
        new_versions = []
        for version in versions:
            data_source = data_sources.get(version, None)
            note = release_note.get(version, None)
            if data_source:
                version = version + ' (data source ' + data_source + ')'
            if note:
                version = version + ' ' + note
            new_versions.append(version)
        remote_info.versions = new_versions
        del remote_info.data_sources
        dump = yaml_string(remote_info)
        print(dump)
        # output columns
        print('output columns:')
        conf = au.get_remote_module_config(module_name)
        if 'output_columns' in conf:
            output_columns = conf['output_columns']
            for col in output_columns:
                desc = ''
                if 'desc' in col:
                    desc = col['desc']
                print('  {}: {}'.format(col['title'], desc))
    else:
        print('NOT IN STORE')
    if installed:
        print('INSTALLED')
        if args.local:
            li_out = copy.deepcopy(local_info)
            del li_out.conf
            li_out.get_size()
            dump = yaml_string(li_out)
            print(dump)
    else:
        print('NOT INSTALLED')
    if installed and remote_available:
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
    if args.md is not None:
        constants.custom_modules_dir = args.md
    matching_names = au.search_remote(*args.modules)
    if len(matching_names) > 1 and args.version is not None:
        sys.exit('Version filter cannot be applied to multiple modules')
    selected_install = {}
    for module_name in matching_names:
        remote_info = au.get_remote_module_info(module_name)
        local_info = au.get_local_module_info(module_name)
        if args.version is None:
            if local_info is not None:
                local_ver = local_info.version
                remote_ver = remote_info.latest_version
                if not args.force and LooseVersion(local_ver) >= LooseVersion(remote_ver):
                    print(f'{module_name}: latest ({local_ver}) is already installed. Use -f/--force to overwrite')
                    continue
            selected_install[module_name] = remote_info.latest_version
        elif remote_info.has_version(args.version):
            if not args.force and local_info is not None and LooseVersion(local_info.version) == LooseVersion(args.version):
                print(f'{module_name}:{args.version} is already installed. Use -f/--force to overwrite')
                continue
            selected_install[module_name] = args.version
        else:
            continue
    if args.private:
        if args.version is None:
            sys.exit('--include-private cannot be used without specifying a version using -v/--version')
        for module_name in args.modules:
            if au.module_exists_remote(module_name, version=args.version, private=True):
                selected_install[module_name] = args.version
    # Add dependencies of selected modules
    dep_install = {}
    pypi_deps_install = {}
    if not args.skip_dependencies:
        for module_name, version in selected_install.items():
            deps = au.get_install_deps(module_name, version=version)
            dep_install.update(deps)
    # If overlap between selected modules and dependency modules, use the dependency version
    to_install = selected_install
    to_install.update(dep_install)
    if len(to_install) == 0:
        print('No modules to install found')
    else:
        print('Installing: {:}'\
                .format(', '.join([name+':'+version for name, version in sorted(to_install.items())]))
                )
        if not(args.yes):
            while True:
                resp = input('Proceed? ([y]/n) > ')
                if resp == 'y' or resp=='':
                    break
                if resp == 'n':
                    exit()
                else:
                    print('Your response (\'{:}\') was not one of the expected responses: y, n'.format(resp))
                    continue
        for module_name, module_version in sorted(to_install.items()):
            stage_handler = InstallProgressStdout(module_name, module_version)
            au.install_module(
                module_name,
                version=module_version,
                force_data=args.force_data,
                stage_handler=stage_handler,
                force=args.force,
                skip_data=args.skip_data,
                install_pypi_dependency=args.install_pypi_dependency
            )

def update_modules(args):
    if args.md is not None:
        constants.custom_modules_dir = args.md
    if len(args.modules) > 0:
        requested_modules = au.search_local(*args.modules)
    else:
        requested_modules = []
    update_strategy = args.strategy
    status_table = [['Name','New Version','Size']]
    updates, _, reqs_failed = au.get_updatable(requested_modules, strategy=update_strategy)
    if reqs_failed:
        print('Newer versions of ({}) are available, but would break dependencies. You may use --strategy=force to force installation.'\
            .format(', '.join(reqs_failed.keys())))
    if not updates:
        print('No module updates are needed')
        exit()
    for mname, update_info in updates.items():
        version = update_info.version
        size = update_info.size
        status_table.append([mname, version, util.humanize_bytes(size)])
    print_tabular_lines(status_table)
    if not args.y:
        user_cont = input('Update the above modules? (y/n) > ')
        if user_cont.lower() not in ['y','yes']:
            exit()
    for mname, update_info in updates.items():
        args.modules = [mname]
        args.force_data = False
        args.version = update_info.version
        args.yes = True
        args.private = False
        args.skip_dependencies = False
        args.force = False
        args.skip_data = False
        install_modules(args)

def uninstall_modules (args):
    if args.md is not None:
        constants.custom_modules_dir = args.md
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
        print('No modules to uninstall found')

def publish_module (args):
    if args.md is not None:
        constants.custom_modules_dir = args.md
    sys_conf = au.get_system_conf()
    if args.user is None:
        if 'publish_username' in sys_conf:
            args.user = sys_conf['publish_username']
        else:
            args.user = input("Username: ")
    if args.password is None:
        if 'publish_password' in sys_conf:
            args.password = sys_conf['publish_password']
        else:
            args.password = getpass()
    au.publish_module(args.module, args.user, args.password, overwrite=args.overwrite, include_data=args.data)

def install_base (args):
    sys_conf = au.get_system_conf()
    base_modules = sys_conf.get(constants.base_modules_key,[])
    args = SimpleNamespace(modules=base_modules,
        force_data=args.force_data,
        version=None,
        yes=True,
        private=False,
        skip_dependencies=False,
        force=args.force,
        skip_data=False,
        install_pypi_dependency=args.install_pypi_dependency,
        md=args.md
    )
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
    if args.md is not None:
        constants.custom_modules_dir = args.md
    au.new_annotator(args.annotator_name)
    module_info = au.get_local_module_info(args.annotator_name)
    print('Annotator {0} created at {1}'.format(args.annotator_name,
                                                module_info.directory))

def report_issue (args):
    au.report_issue()

def show_system_conf (args):
    au.show_system_conf()

def show_cravat_conf (args):
    au.show_cravat_conf()

def show_version (args):
    au.show_cravat_version()

# Check that the system is ready
au.ready_resolution_console()

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
    description='installs base modules.'
)
parser_install_base.add_argument('-f','--force',
    action='store_true',
    help='Overwrite existing modules',
)
parser_install_base.add_argument('-d', '--force-data',
    action='store_true',
    help='Download data even if latest data is already installed'
)
parser_install_base.add_argument('--install-pypi-dependency',
    action='store_true',
    default=True,
    help='Try to install non-OpenCRAVAT package dependency with pip'
)
parser_install_base.add_argument('--md',
    default=None,
    help='Specify the root directory of OpenCRAVAT modules'
)
parser_install_base.set_defaults(func=install_base)

# install
parser_install = subparsers.add_parser('install',
                                        help='installs modules.',
                                        description='installs modules.')
parser_install.add_argument('modules',
    nargs='+',
    help='Modules to install. May be regular expressions.'
)
parser_install.add_argument('-v','--version',
    help='Install a specific version'
)
parser_install.add_argument('-f','--force',
    action='store_true',
    help='Install module even if latest version is already installed',
)
parser_install.add_argument('-d', '--force-data',
    action='store_true',
    help='Download data even if latest data is already installed'
)
parser_install.add_argument('-y','--yes',
    action='store_true',
    help='Proceed without prompt'
)
parser_install.add_argument('--skip-dependencies',
    action='store_true',
    help='Skip installing dependencies'
)
parser_install.add_argument('-p','--private',
    action='store_true',
    help='Install a private module'
)
parser_install.add_argument('--skip-data',
    action='store_true',
    help='Skip installing data'
)
parser_install.add_argument('--install-pypi-dependency',
    action='store_true',
    default=True,
    help='Try to install non-OpenCRAVAT package dependency with pip'
)
parser_install.add_argument('--md',
    default=None,
    help='Specify the root directory of OpenCRAVAT modules'
)
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
parser_update.add_argument('-y',
                            action='store_true',
                            help='Proceed without prompt'
                            )
parser_update.add_argument('--strategy',
                            help='Dependency resolution strategy. "consensus" will attemp to resolve dependencies. "force" will install the highest available version. "skip" will skip modules with constraints.',
                            default='consensus',
                            type=str,
                            choices=('consensus','force','skip')
                            )
parser_update.add_argument('--install-pypi-dependency',
    action='store_true',
    default=True,
    help='Try to install non-OpenCRAVAT package dependency with pip'
)
parser_update.add_argument('--md',
    default=None,
    help='Specify the root directory of OpenCRAVAT modules'
)
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
parser_uninstall.add_argument('--md',
    default=None,
    help='Specify the root directory of OpenCRAVAT modules'
)
parser_uninstall.set_defaults(func=uninstall_modules)

# info
parser_info = subparsers.add_parser('info',
                                    help='shows module information.')
parser_info.add_argument('module',
                            help='Module to get info about')
parser_info.add_argument('-l','--local',
                            dest='local',
                            help='Include local info',
                            action='store_true')
parser_info.add_argument('--md',
    default=None,
    help='Specify the root directory of OpenCRAVAT modules'
)
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
parser_ls.add_argument('-i','--include-hidden',
                        action='store_true',
                        help='Include hidden modules')
parser_ls.add_argument('--tags',
    nargs='+',
    default=[],
    help='Only list modules of given tag(s)'
)
parser_ls.add_argument('-q','--quiet',
                        action='store_true',
                        help='Only list module names')
parser_ls.add_argument('--bytes',
    action='store_true',
    dest='raw_bytes',
    help='Machine readable data sizes'
    )
parser_ls.add_argument('--md',
    default=None,
    help='Specify the root directory of OpenCRAVAT modules'
)
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
                            default=None,
                            help='user to publish as. Typically your email.'
                            )
parser_publish.add_argument('-p',
                            '--password',
                            default=None,
                            help='password for the user. Enter at prompt if missing.')
parser_publish.add_argument('--force-yes',
                            default=False,
                            action='store_true',
                            help='overrides yes to overwrite question')
parser_publish.add_argument('--overwrite',
                            default=False,
                            action='store_true',
                            help='overwrites a published module/version')
parser_publish.add_argument('--md',
    default=None,
    help='Specify the root directory of OpenCRAVAT modules'
)
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
parser_new_annotator.add_argument('--md',
    default=None,
    help='Specify the root directory of OpenCRAVAT modules'
)
parser_new_annotator.set_defaults(func=new_annotator)

# opens issue report
parser_report_issue = subparsers.add_parser('report-issue',
                                            help='opens a browser window to report issues')
parser_report_issue.set_defaults(func=report_issue)

# shows system conf content.
parser_show_system_conf = subparsers.add_parser('show-system-conf',
                                            help='shows system configuration.')
parser_show_system_conf.set_defaults(func=show_system_conf)

# shows cravat conf content.
parser_show_cravat_conf = subparsers.add_parser('show-cravat-conf',
                                            help='shows cravat configuration.')
parser_show_cravat_conf.set_defaults(func=show_cravat_conf)

# shows version
parser_show_version = subparsers.add_parser('version',
                                            help='shows open-cravat version')
parser_show_version.set_defaults(func=show_version)

def main ():
    # Print usage if no args
    if len(sys.argv) == 1:
        sys.argv.append('-h')
    args = parser.parse_args()
    args.func(args) 

if __name__ == '__main__':
    main()
