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
from cravat.websubmit import websubmit as wu
import websockets
from aiohttp import web
import socket
import base64
#from cryptography import fernet
#from aiohttp_session import setup, get_session, new_session
#from aiohttp_session.cookie_storage import EncryptedCookieStorage
import hashlib
import platform

donotopenbrowser = False

def check_donotopenbrowser ():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server',
                        dest='servermode',
                        action='store_true',
                        default=False,
                        help='run in server mode')
    parser.add_argument('--donotopenbrowser',
                        dest='donotopenbrowser',
                        action='store_true',
                        default=False,
                        help='do not open the cravat web page')
    args = parser.parse_args(sys.argv[1:])
    global donotopenbrowser
    donotopenbrowser = args.donotopenbrowser
    global servermode
    servermode = args.servermode
    wu.servermode = args.servermode

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
    sys.argv = sys.argv[1:]
    check_donotopenbrowser()
    global donotopenbrowser
    if not donotopenbrowser:
        webbrowser.open('http://localhost:8060/result/index.html?job_id=' + runid + '&dbpath=' + dbpath)
    main()

def store ():
    check_donotopenbrowser()
    ws.start_install_queue_manager()
    global donotopenbrowser
    if not donotopenbrowser:
        webbrowser.open('http://localhost:8060/store/index.html')

def submit ():
    check_donotopenbrowser()
    global donotopenbrowser
    if not donotopenbrowser:
        webbrowser.open('http://localhost:8060/submit/index.html')
    main()

def main ():
    '''
    if servermode:
        jobs_dir = au.get_jobs_dir()
        admin_sqlite_path = os.path.join(jobs_dir, 'admin.sqlite')
        if os.path.exists(admin_sqlite_path) == False:
            db = sqlite3.connect(admin_sqlite_path)
            cursor = db.cursor()
            cursor.execute('create table users (email text, passwordhash text, question text, answerhash text)')
            cursor.execute('create table jobs (jobname text, username text, submit date, runtime integer, numinput integer, annotators text, genome text)')
            m = hashlib.sha256()
            adminpassword = 'admin'
            m.update(adminpassword.encode('utf-16be'))
            adminpasswordhash = m.hexdigest()
            cursor.execute('insert into users values ("admin", "{}", "", "")'.format(adminpasswordhash))
            cursor.close()
            db.commit()
            db.close()
    s = socket.socket()
    try:
        s.bind(('localhost', 8060))
        app = web.Application()
        fernet_key = fernet.Fernet.generate_key()
        secret_key = base64.urlsafe_b64decode(fernet_key)
        setup(app, EncryptedCookieStorage(secret_key))
        routes = list()
        routes.extend(ws.routes)
        routes.extend(wr.routes)
        routes.extend(wu.routes)
        for route in routes:
            method, path, func_name = route
            app.router.add_route(method, path, func_name)
        app.router.add_static('/store', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webstore'))
        app.router.add_static('/result', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webresult'))
        app.router.add_static('/submit',os.path.join(os.path.dirname(os.path.realpath(__file__)), 'websubmit'))
        ws.start_worker()
        print('(******** Press Ctrl-C or Ctrl-Break to quit ********)')
        web.run_app(app, port=8060)
    except KeyboardInterrupt:
        print('@@@@@@@ keyboard interrupt')
    except BrokenPipeError:
        print('@@@@@@@ broken pipe')
    except:
        import traceback
        traceback.print_exc()
    '''
    try:
        s = socket.socket()
        pl = platform.platform()
        if pl == 'Windows':
            s.bind(('0.0.0.0', 8060))
        else:
            s.bind(('localhost', 8060))
    except:
        return
    app = web.Application()
    routes = list()
    routes.extend(ws.routes)
    routes.extend(wr.routes)
    routes.extend(wu.routes)
    for route in routes:
        method, path, func_name = route
        app.router.add_route(method, path, func_name)
    app.router.add_static('/store', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webstore'))
    app.router.add_static('/result', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webresult'))
    app.router.add_static('/submit',os.path.join(os.path.dirname(os.path.realpath(__file__)), 'websubmit'))
    ws.start_worker()
    print('(******** Press Ctrl-C or Ctrl-Break to quit ********)')
    web.run_app(app, port=8060)

if __name__ == '__main__':
    main()
