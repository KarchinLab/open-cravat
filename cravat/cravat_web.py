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
import oyaml as yaml
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
import hashlib
import platform
import asyncio
import datetime as dt
import requests
import traceback
import ssl
import importlib
if importlib.util.find_spec('cravatserver') is not None:
    import cravatserver
    server_ready = True
else:
    server_ready = False

donotopenbrowser = False
ssl_enabled = False
protocol = None
conf = ConfigLoader()
sysconf = au.get_system_conf()
if 'conf_dir' in sysconf:
    pem_path = os.path.join(sysconf['conf_dir'], 'cert.pem')
    if os.path.exists(pem_path):
        ssl_enabled = True
        sc = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        sc.load_cert_chain(pem_path)
if ssl_enabled:
    protocol = 'https://'
else:
    protocol = 'http://'

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
    ws.servermode = args.servermode
    global server_ready
    if server_ready:
        cravatserver.servermode = servermode
    if servermode and server_ready == False:
        print('open-cravat-server package is required to run OpenCRAVAT Server.\nRun "pip install open-cravat-server" to get the package.')
        exit()

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
        global protocol
        webbrowser.open(protocol + '{host}:{port}/result/index.html?job_id='.format(host=server.get('host'), port=server.get('port')) + runid + '&dbpath=' + dbpath)
    main()

def store ():
    check_donotopenbrowser()
    ws.start_install_queue_manager()
    global donotopenbrowser
    if not donotopenbrowser:
        server = get_server()
        global protocol
        webbrowser.open(protocol + '{host}:{port}/store/index.html'.format(host=server.get('host'), port=server.get('port')))

def submit ():
    check_donotopenbrowser()
    global donotopenbrowser
    if not donotopenbrowser:
        server = get_server()
        global protocol
        global server_ready
        global servermode
        if server_ready and servermode:
            webbrowser.open(protocol + '{host}:{port}/server/nocache/login.html'.format(host=server.get('host'), port=server.get('port')))
        else:
            webbrowser.open(protocol + '{host}:{port}/submit/index.html'.format(host=server.get('host'), port=server.get('port')))
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

@web.middleware
async def middleware (request, handler):
    response = await handler(request)
    url_parts = request.url.parts
    nocache = False
    if url_parts[0] == '/':
        if len(url_parts) >= 3 and url_parts[2] == 'nocache':
            nocache = True
    elif url_parts[0] == 'nocache':
        nocache = True
    if nocache:
        response.headers['Cache-Control'] = 'no-cache'
    return response

class WebServer (object):
    def __init__ (self, host=None, port=None, loop=None, ssl_context=None):
        serv = get_server()
        if host is None:
            host = serv['host']
        if port is None:
            port = serv['port']
        self.host = host
        self.port = port
        if loop is None:
            loop = asyncio.get_event_loop()
        self.ssl_context = ssl_context
        self.loop = loop
        asyncio.ensure_future(self.start(), loop=self.loop)

    async def start (self):
        global middleware
        self.app = web.Application(loop=self.loop, middlewares=[middleware])
        if server_ready:
            cravatserver.setup(self.app)
        self.setup_routes()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = TCPSitePatched(self.runner, self.host, self.port, loop=self.loop, ssl_context=self.ssl_context)
        await self.site.start()

    def setup_routes (self):
        routes = list()
        routes.extend(ws.routes)
        routes.extend(wr.routes)
        routes.extend(wu.routes)
        global server_ready
        if server_ready:
            cravatserver.add_routes(self.app.router)
        for route in routes:
            method, path, func_name = route
            self.app.router.add_route(method, path, func_name)
        self.app.router.add_static('/store', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webstore'))
        self.app.router.add_static('/result', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'webresult'))
        self.app.router.add_static('/submit', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'websubmit'))
        self.app.router.add_get('/hello', hello)
        self.app.router.add_get('/heartbeat', heartbeat)
        self.app.router.add_get('/issystemready', is_system_ready)
        ws.start_worker()

async def hello(request):
    return web.Response(text='OpenCRAVAT server is running here. '+str(dt.datetime.now()))

async def heartbeat(request):
    ws = web.WebSocketResponse(timeout=60*60*24*365)
    await ws.prepare(request)
    async for msg in ws:
        pass
    return ws

async def is_system_ready (request):
    return web.json_response(dict(au.system_ready()))

def main ():

    def wakeup ():
        loop.call_later(0.1, wakeup)

    serv = get_server()
    global protocol
    hello_url = protocol + '{host}:{port}/hello'.format(host=serv.get('host'),port=serv.get('port'))
    try:
        r = requests.get(hello_url, timeout=0.01)
        print('OpenCRAVAT is already running at port {}:{}.'.format(serv.get('host'), serv.get('port')))
        return
    except requests.exceptions.ConnectionError:
        pass
    print('OpenCRAVAT is served at {}:{}'.format(serv.get('host'), serv.get('port')))
    print('(To quit: Press Ctrl-C or Ctrl-Break if run on a Terminal or Windows, or click "Cancel" and then "Quit" if run through OpenCRAVAT app on Mac OS)')
    loop = asyncio.get_event_loop()
    loop.call_later(0.1, wakeup)
    global ssl_enabled
    if ssl_enabled:
        global sc
        server = WebServer(loop=loop, ssl_context=sc)
    else:
        server = WebServer(loop=loop)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
