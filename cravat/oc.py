import argparse
from . import cravat_admin
from .cravat_class import cravat_cmd_parser

root_p = argparse.ArgumentParser()
root_sp = root_p.add_subparsers()

version_p = root_sp.add_parser('version', parents=[cravat_admin.parser_show_version], add_help=False)

run_p = root_sp.add_parser('run', parents=[cravat_cmd_parser], add_help=False)

module_p = root_sp.add_parser('module')
module_sp = module_p.add_subparsers()
module_ls_p = module_sp.add_parser('ls', parents=[cravat_admin.parser_ls], add_help=False)
module_install_p = module_sp.add_parser('install', parents=[cravat_admin.parser_install], add_help=False)
module_uninstall_p = module_sp.add_parser('uninstall', parents=[cravat_admin.parser_uninstall], add_help=False)
module_update_p = module_sp.add_parser('update', parents=[cravat_admin.parser_update], add_help=False)
module_info_base_p = module_sp.add_parser('info', parents=[cravat_admin.parser_info], add_help=False)

store_p = root_sp.add_parser('store')
store_sp = store_p.add_subparsers()
store_publish_p = store_sp.add_parser('publish', parents=[cravat_admin.parser_publish], add_help=False)

account_p = root_sp.add_parser('account')
account_sp = account_p.add_subparsers()
account_create_p = account_sp.add_parser('create', parents=[cravat_admin.parser_create_account], add_help=False)
account_change_pw_p = account_sp.add_parser('change-pw', parents=[cravat_admin.parser_change_password], add_help=False)
account_reset_pw_p = account_sp.add_parser('reset-pw', parents=[cravat_admin.parser_reset_pw], add_help=False)
account_verify_email_p = account_sp.add_parser('verify-email', parents=[cravat_admin.parser_verify_email], add_help=False)
account_check_login_p = account_sp.add_parser('check-login', parents=[cravat_admin.parser_check_login], add_help=False)


def main():
    args = root_p.parse_args()
    if hasattr(args, 'func'):
        args.func(args)

if __name__ == '__main__':
    main()