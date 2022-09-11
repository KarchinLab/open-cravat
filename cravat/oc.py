import argparse
from cravat import cravat_admin, cravat_util
from cravat.cravat_class import cravat_cmd_parser
from cravat.cravat_test import parser as test_parser
from cravat.cravat_web import parser as gui_parser
from cravat.cravat_report import parser as report_parser
import sys

root_p = argparse.ArgumentParser(
    description="Open-CRAVAT genomic variant interpreter. https://github.com/KarchinLab/open-cravat"
)
root_sp = root_p.add_subparsers(title="Commands")

# run
run_p = root_sp.add_parser(
    "run",
    parents=[cravat_cmd_parser],
    add_help=False,
    description="Run a job",
    help="Run a job",
    epilog="inputs should be the first argument",
)

# report
report_p = root_sp.add_parser(
    "report",
    parents=[report_parser],
    add_help=False,
    help="Generate a report from a job",
    epilog="dbpath must be the first argument",
)

# gui
gui_p = root_sp.add_parser(
    "gui", parents=[gui_parser], add_help=False, help="Start the GUI"
)

# module
module_p = root_sp.add_parser(
    "module", description="Change installed modules", help="Change installed modules"
)
module_sp = module_p.add_subparsers(title="Commands")
module_ls_p = module_sp.add_parser(
    "ls", parents=[cravat_admin.parser_ls], add_help=False, help="List modules"
)
module_install_p = module_sp.add_parser(
    "install",
    parents=[cravat_admin.parser_install],
    add_help=False,
    help="Install modules",
)
module_uninstall_p = module_sp.add_parser(
    "uninstall",
    parents=[cravat_admin.parser_uninstall],
    add_help=False,
    help="Uninstall modules",
)
module_update_p = module_sp.add_parser(
    "update",
    parents=[cravat_admin.parser_update],
    add_help=False,
    help="Update modules",
)
module_info_p = module_sp.add_parser(
    "info", parents=[cravat_admin.parser_info], add_help=False, help="Module details"
)
module_install_base_base_p = module_sp.add_parser(
    "install-base",
    parents=[cravat_admin.parser_install_base],
    add_help=False,
    help="Install base modules",
)


# config
config_p = root_sp.add_parser(
    "config",
    description="View and change configuration settings",
    help="View and change configuration settings",
)
config_sp = config_p.add_subparsers(title="Commands")
config_md_p = config_sp.add_parser(
    "md",
    parents=[cravat_admin.parser_md],
    add_help=False,
    help="Change modules directory",
)
config_system_p = config_sp.add_parser(
    "system",
    parents=[cravat_admin.parser_show_system_conf],
    add_help=False,
    help="Show system config",
)
config_system_p = config_sp.add_parser(
    "cravat",
    parents=[cravat_admin.parser_show_cravat_conf],
    add_help=False,
    help="Show cravat config",
)

# new
new_p = root_sp.add_parser(
    "new", description="Create new modules", help="Create new modules"
)
new_sp = new_p.add_subparsers(title="Commands")
create_example_input_p = new_sp.add_parser(
    "example-input",
    parents=[cravat_admin.parser_make_example_input],
    add_help=False,
    help="Make example input file",
)
create_annotator_p = new_sp.add_parser(
    "annotator",
    parents=[cravat_admin.parser_new_annotator],
    add_help=False,
    help="Create new annotator",
)

# store
store_p = root_sp.add_parser(
    "store",
    description="Publish modules to the store",
    help="Publish modules to the store",
)
store_sp = store_p.add_subparsers(title="Commands")
store_publish_p = store_sp.add_parser(
    "publish",
    parents=[cravat_admin.parser_publish],
    add_help=False,
    help="Publish a module",
)
account_create_p = store_sp.add_parser(
    "new-account",
    parents=[cravat_admin.parser_create_account],
    add_help=False,
    help="Create an account",
)
account_change_pw_p = store_sp.add_parser(
    "change-pw",
    parents=[cravat_admin.parser_change_password],
    add_help=False,
    help="Change password",
)
account_reset_pw_p = store_sp.add_parser(
    "reset-pw",
    parents=[cravat_admin.parser_reset_pw],
    add_help=False,
    help="Request password reset",
)
account_verify_email_p = store_sp.add_parser(
    "verify-email",
    parents=[cravat_admin.parser_verify_email],
    add_help=False,
    help="Request email verification",
)
account_check_login_p = store_sp.add_parser(
    "check-login",
    parents=[cravat_admin.parser_check_login],
    add_help=False,
    help="Check login credentials",
)

# util
util_p = root_sp.add_parser("util", description="Utilities", help="Utilities")
util_sp = util_p.add_subparsers(title="Commands")
util_test_p = util_sp.add_parser(
    "test", parents=[test_parser], add_help=False, help="Test installed modules"
)
util_update_result_p = util_sp.add_parser(
    "update-result",
    parents=[cravat_util.parser_migrate_result],
    add_help=False,
    help="Update old result database to newer format",
)
util_send_gui_p = util_sp.add_parser(
    "send-gui",
    parents=[cravat_util.parser_result2gui],
    add_help=False,
    help="Copy a command line job into the GUI submission list",
)
util_mergesqlite_p = util_sp.add_parser(
    "mergesqlite",
    parents=[cravat_util.parser_mergesqlite],
    add_help=False,
    help="Merge SQLite result files",
)
util_filtersqlite_p = util_sp.add_parser(
    "filtersqlite",
    parents=[cravat_util.parser_filtersqlite],
    add_help=False,
    help="Filter SQLite result files",
)
util_showsqliteinfo_p = util_sp.add_parser(
    "showsqliteinfo",
    parents=[cravat_util.parser_showsqliteinfo],
    add_help=False,
    help="Show SQLite result file information",
)

# version
version_p = root_sp.add_parser(
    "version",
    parents=[cravat_admin.parser_show_version],
    add_help=False,
    help="Show version",
)

# feedback
feedback_p = root_sp.add_parser(
    "feedback",
    parents=[cravat_admin.parser_report_issue],
    add_help=False,
    help="Send feedback to the developers",
)


def main():
    try:
        # Global parser silently consumes the --debug option
        # --debug is used below in case of exceptions
        global_parser = argparse.ArgumentParser(add_help=False)
        global_parser.add_argument('--debug', action='store_true')
        global_args, cmd_toks = global_parser.parse_known_args()
        args = root_p.parse_args(cmd_toks)
        if hasattr(args, "func"):
            args.func(args)
        else:
            root_p.parse_args(sys.argv[1:] + ["--help"])
    except Exception as e:
        if '--debug' in sys.argv[1:]:
            import traceback
            traceback.print_exc()
        else:
            print('ERROR', file=sys.stderr)
            print(e, file=sys.stderr)
            print('Repeat command with --debug for more details', file=sys.stderr)


if __name__ == "__main__":
    main()
