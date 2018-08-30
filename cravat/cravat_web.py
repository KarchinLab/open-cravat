from http.server import HTTPServer, CGIHTTPRequestHandler
from socketserver import TCPServer
import os
import webbrowser
import multiprocessing
import sqlite3
import urllib.parse
import json
import sys
import argparse
import imp
import yaml
import re
from cravat import ConfigLoader
from cravat import admin_util as au
from cravat import CravatFilter
from cravat.webresult import webresult as wr
from cravat.webstore import webstore as ws
import websockets
from aiohttp import web

def result ():
    server = Server()
    server.start()
    parser = argparse.ArgumentParser()
    parser.add_argument('dbpath',
                        help='path to a CRAVAT result SQLite file')
    parser.add_argument('-c',
                        dest='confpath',
                        default=None,
                        help='path to a CRAVAT configuration file')
    parsed_args = parser.parse_args(sys.argv[1:])
    dbpath = os.path.abspath(parsed_args.dbpath)
    if os.path.exists(dbpath) == False:
        sys.stderr.write(dbpath + ' does not exist.\n')
        exit(-1)
    confpath = parsed_args.confpath
    runid = os.path.basename(dbpath).replace('.sqlite', '')
    webbrowser.open('http://localhost:8060/result/index.html?job_id=' + runid + '&dbpath=' + dbpath)
    main()

def store ():
    webbrowser.open('http://localhost:8060/store/index.html')
    main()
    '''
    manager = Manager()
    install_state = manager.dict()
    sse_update_condition = manager.Condition()
    sse_update_event = manager.Event()
    install_state['stage'] = ''
    install_state['message'] = ''
    install_state['module_name'] = ''
    install_state['module_version'] = ''
    install_state['cur_chunk'] = 0
    install_state['total_chunks'] = 0
    install_state['cur_size'] = 0
    install_state['total_size'] = 0
    install_state['update_time'] = time.time()
    install_worker = Process(target=install_from_queue, args=(install_queue, install_state, sse_update_event))
    install_worker.start()
    app = web.Application()
    add_routes(app)
    conf_loader = ConfigLoader()
    conf = conf_loader.get_cravat_conf()
    port = conf['gui_port']
    web.run_app(app, host='localhost', port=port)
    '''

def main ():
    app = web.Application()
    routes = list()
    routes.extend(ws.routes)
    routes.extend(wr.routes)
    for route in routes:
        method, path, func_name = route
        app.router.add_route(method, path, func_name)
    app.router.add_static('/store', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webstore'))
    app.router.add_static('/result', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webresult'))
    web.run_app(app, port=8060)
