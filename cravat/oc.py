import argparse
from . import cravat_admin
from .cravat_class import cravat_cmd_parser
from .cravat_test import parser as test_parser
from . import cravat_web
from . import cravat_util

root_p = argparse.ArgumentParser()
root_sp = root_p.add_subparsers(title='Commands')

# run
run_p = root_sp.add_parser('run', parents=[cravat_cmd_parser], add_help=False, help='Run a job')

# gui
gui_p = root_sp.add_parser('gui', help='Use the GUI')
gui_sp = gui_p.add_subparsers(title='Commands')
gui_start_p = gui_sp.add_parser('start', parents=[cravat_web.base_parser], add_help=False, help='Start the gui')
gui_view_p = gui_sp.add_parser('result', parents=[cravat_web.view_parser], add_help=False, help='Open the result viewer')

# module
module_p = root_sp.add_parser('module', help='Change installed modules')
module_sp = module_p.add_subparsers(title='Commands')
module_ls_p = module_sp.add_parser('ls', parents=[cravat_admin.parser_ls], add_help=False, help='List modules')
module_install_p = module_sp.add_parser('install', parents=[cravat_admin.parser_install], add_help=False, help='Install modules')
module_uninstall_p = module_sp.add_parser('uninstall', parents=[cravat_admin.parser_uninstall], add_help=False, help='Uninstall modules')
module_update_p = module_sp.add_parser('update', parents=[cravat_admin.parser_update], add_help=False, help='Update modules')
module_info_base_p = module_sp.add_parser('info', parents=[cravat_admin.parser_info], add_help=False, help='Module details')

# config
config_p = root_sp.add_parser('config', help='View and change configuration settings')
config_sp = config_p.add_subparsers(title='Commands')
config_md_p = config_sp.add_parser('md', parents=[cravat_admin.parser_md], add_help=False, help='Change modules directory')
config_system_p = config_sp.add_parser('system', parents=[cravat_admin.parser_show_system_conf], add_help=False, help='Show system config')
config_system_p = config_sp.add_parser('cravat', parents=[cravat_admin.parser_show_cravat_conf], add_help=False, help='Show cravat config')

# create
create_p = root_sp.add_parser('create', help='Create new modules')
create_sp = create_p.add_subparsers(title='Commands')
create_example_input_p = create_sp.add_parser('example-input', parents=[cravat_admin.parser_make_example_input], add_help=False, help='Make example input file')
create_annotator_p = create_sp.add_parser('annotator', parents=[cravat_admin.parser_new_annotator], add_help=False, help='Create new annotator')

# store
store_p = root_sp.add_parser('store', help='Publish modules to the store')
store_sp = store_p.add_subparsers(title='Commands')
store_publish_p = store_sp.add_parser('publish', parents=[cravat_admin.parser_publish], add_help=False, help='Publish a module')
account_create_p = store_sp.add_parser('new-account', parents=[cravat_admin.parser_create_account], add_help=False, help='Create an account')
account_change_pw_p = store_sp.add_parser('change-pw', parents=[cravat_admin.parser_change_password], add_help=False, help='Change password')
account_reset_pw_p = store_sp.add_parser('reset-pw', parents=[cravat_admin.parser_reset_pw], add_help=False, help='Request password reset')
account_verify_email_p = store_sp.add_parser('verify-email', parents=[cravat_admin.parser_verify_email], add_help=False, help='Request email verification')
account_check_login_p = store_sp.add_parser('check-login', parents=[cravat_admin.parser_check_login], add_help=False, help='Check login credentials')

# util
util_p = root_sp.add_parser('util', help='Utilities')
util_sp = util_p.add_subparsers(title='Commands')
util_test_p = util_sp.add_parser('test', parents=[test_parser], add_help=False, help='Test installed modules')
util_update_result_p = util_sp.add_parser('update-result', parents=[cravat_util.parser_migrate_result], add_help=False, help='Update old result database to newer format')

# version
version_p = root_sp.add_parser('version', parents=[cravat_admin.parser_show_version], add_help=False, help='Show version')

# feedback
feedback_p = root_sp.add_parser('feedback', parents=[cravat_admin.parser_report_issue], add_help=False, help='Send feedback to the developers')

def main():
    args = root_p.parse_args()
    if hasattr(args, 'func'):
        args.func(args)

if __name__ == '__main__':
    main()