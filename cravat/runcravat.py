#!/usr/bin/env python3
from cravat import Cravat, cravat_cmd_parser, system_ready
import asyncio

def main ():
    is_ready, msg = system_ready()
    if not is_ready:
        exit(msg)
    cmd_args = cravat_cmd_parser.parse_args()
    module = Cravat(**vars(cmd_args))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(module.main())

if __name__ ==  '__main__':
    main()
    print('done')
