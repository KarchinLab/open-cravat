#!/usr/bin/env python3
from cravat import Cravat, cravat_cmd_parser

def main ():
    cmd_args = cravat_cmd_parser.parse_args()
    module = Cravat(**vars(cmd_args))
    module.main()

if __name__ ==  '__main__':
    main()
    print('done')
