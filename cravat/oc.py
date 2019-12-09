import argparse
from . import cravat_admin

root_p = argparse.ArgumentParser()
root_sp = root_p.add_subparsers()
module_p = root_sp.parser('module')
module_sp = module_p.add_subparsers()
module_install_p = module_sp.add_parser('install', parents=[cravat_admin.parser_install])

def main():
    args = root_p.parse_args()
    if hasattr(args, 'func'):
        args.func(args)

if __name__ == '__main__':
    main()