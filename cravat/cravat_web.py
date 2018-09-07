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
# from cravat.websubmit import websubmit
import websockets
from aiohttp import web

def result ():
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

def main ():
    app = web.Application()
    routes = list()
    routes.extend(ws.routes)
    routes.extend(wr.routes)
    # routes.extend(websubmit.routes)
    for route in routes:
        method, path, func_name = route
        app.router.add_route(method, path, func_name)
    app.router.add_static('/store', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webstore'))
    app.router.add_static('/result', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webresult'))
    app.router.add_static('/submit',os.path.join(os.path.dirname(os.path.realpath(__file__)), 'websubmit'))
    ws.start_worker()
    web.run_app(app, port=8060)

if __name__ == '__main__':
    main()
