import argparse
from . import cravat_admin
from .cravat_class import cravat_cmd_parser

root_p = argparse.ArgumentParser()
root_sp = root_p.add_subparsers()

version_p = root_sp.add_parser('version', parents=[cravat_admin.parser_show_version], add_help=False)

run_p = root_sp.add_parser('run', parents=[cravat_cmd_parser], add_help=False)

# module
module_p = root_sp.add_parser('module')
module_sp = module_p.add_subparsers()
module_ls_p = module_sp.add_parser('ls', parents=[cravat_admin.parser_ls], add_help=False)
module_install_p = module_sp.add_parser('install', parents=[cravat_admin.parser_install], add_help=False)
module_uninstall_p = module_sp.add_parser('uninstall', parents=[cravat_admin.parser_uninstall], add_help=False)
module_update_p = module_sp.add_parser('update', parents=[cravat_admin.parser_update], add_help=False)
module_info_base_p = module_sp.add_parser('info', parents=[cravat_admin.parser_info], add_help=False)

# store
store_p = root_sp.add_parser('store')
store_sp = store_p.add_subparsers()
store_publish_p = store_sp.add_parser('publish', parents=[cravat_admin.parser_publish], add_help=False)
account_create_p = store_sp.add_parser('new-account', parents=[cravat_admin.parser_create_account], add_help=False)
account_change_pw_p = store_sp.add_parser('change-pw', parents=[cravat_admin.parser_change_password], add_help=False)
account_reset_pw_p = store_sp.add_parser('reset-pw', parents=[cravat_admin.parser_reset_pw], add_help=False)
account_verify_email_p = store_sp.add_parser('verify-email', parents=[cravat_admin.parser_verify_email], add_help=False)
account_check_login_p = store_sp.add_parser('check-login', parents=[cravat_admin.parser_check_login], add_help=False)

#new
new_p = root_sp.add_parser('new')
new_sp = new_p.add_subparsers()
new_annotator_p = new_sp.add_parser('annotator', parents=[cravat_admin.parser_new_annotator], add_help=False)

# util
util_p = root_sp.add_parser('util')
util_sp = util_p.add_subparsers()
util_example_input_p = util_sp.add_parser('example-input', parents=[cravat_admin.parser_make_example_input], add_help=False)


def main():
    args = root_p.parse_args()
    if hasattr(args, 'func'):
        args.func(args)

if __name__ == '__main__':
    main()