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
from aiohttp import web, web_runner
import socket
import base64
#from cryptography import fernet
#from aiohttp_session import setup, get_session, new_session
#from aiohttp_session.cookie_storage import EncryptedCookieStorage
import hashlib
import platform
import asyncio
import datetime as dt
import requests
import traceback

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
        server = get_server()
        webbrowser.open('http://{host}:{port}/result/index.html?job_id='.format(host=server.get('host'), port=server.get('port')) + runid + '&dbpath=' + dbpath)
    main()

def store ():
    check_donotopenbrowser()
    ws.start_install_queue_manager()
    global donotopenbrowser
    if not donotopenbrowser:
        server = get_server()
        webbrowser.open('http://{host}:{port}/store/index.html'.format(host=server.get('host'), port=server.get('port')))

def submit ():
    check_donotopenbrowser()
    global donotopenbrowser
    if not donotopenbrowser:
        server = get_server()
        webbrowser.open('http://{host}:{port}/submit/index.html'.format(host=server.get('host'), port=server.get('port')))
    main()

def get_server():
    server = {}
    conf = ConfigLoader()
    pl = platform.platform()
    if pl.startswith('Windows'):
        def_host = 'localhost'
    elif pl.startswith('Linux'):
        def_host = 'localhost'
    elif pl.startswith('Darwin'):
        def_host = '0.0.0.0'
    else:
        def_host = 'localhost'
    host = conf.get_cravat_conf().get('gui_host', def_host)
    port = conf.get_cravat_conf().get('gui_port', 8060)
    server['host'] = host
    server['port'] = port
    return server

class TCPSitePatched (web_runner.BaseSite):
    __slots__ = ('loop', '_host', '_port', '_reuse_address', '_reuse_port')
    def __init__ (self, runner, host=None, port=None, *, shutdown_timeout=60.0, ssl_context=None, backlog=128, reuse_address=None, reuse_port=None, loop=None):
        super().__init__(runner, shutdown_timeout=shutdown_timeout, ssl_context=ssl_context, backlog=backlog)
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        if host is None:
            host = '0.0.0.0'
        self._host = host
        if port is None:
            port = 8443 if self._ssl_context else 8080
        self._port = port
        self._reuse_address = reuse_address
        self._reuse_port = reuse_port

    @property
    def name(self):
        scheme = 'https' if self._ssl_context else 'http'
        return str(URL.build(scheme=scheme, host=self._host, port=self._port))

    async def start(self):
        await super().start()
        self._server = await self.loop.create_server(self._runner.server, self._host, self._port, ssl=self._ssl_context, backlog=self._backlog, reuse_address=self._reuse_address, reuse_port=self._reuse_port)

class WebServer (object):
    def __init__ (self, host=None, port=None, loop=None):
        serv = get_server()
        if host is None:
            host = serv['host']
        if port is None:
            port = serv['port']
        self.host = host
        self.port = port
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        asyncio.ensure_future(self.start(), loop=self.loop)

    async def start (self):
        self.app = web.Application(loop=self.loop)
        self.setup_routes()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = TCPSitePatched(self.runner, self.host, self.port, loop=self.loop)
        await self.site.start()

    def setup_routes (self):
        routes = list()
        routes.extend(ws.routes)
        routes.extend(wr.routes)
        routes.extend(wu.routes)
        for route in routes:
            method, path, func_name = route
            self.app.router.add_route(method, path, func_name)
        self.app.router.add_static('/store', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webstore'))
        self.app.router.add_static('/result', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webresult'))
        self.app.router.add_static('/submit', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'websubmit'))
        self.app.router.add_get('/hello', hello)
        ws.start_worker()

async def hello(request):
    return web.Response(text='OpenCRAVAT server is running here. '+str(dt.datetime.now()))

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
    except BrokenPipeError:
    except:
        import traceback
        traceback.print_exc()
    '''
    def wakeup ():
        loop.call_later(0.1, wakeup)

    serv = get_server()
    hello_url = 'http://{host}:{port}/hello'.format(host=serv.get('host'),port=serv.get('port'))
    try:
        r = requests.get(hello_url, timeout=1)
        # print('{}:{} already in use'.format(serv['host'], serv['port']))
        print('OpenCRAVAT is already running.')
        return
    except requests.exceptions.ConnectionError:
        pass
    print('(******** Press Ctrl-C or Ctrl-Break to quit ********)')
    loop = asyncio.get_event_loop()
    loop.call_later(0.1, wakeup)
    server = WebServer(loop=loop)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
