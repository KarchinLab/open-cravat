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
import socket
import concurrent
import logging
from cravat import constants

conf = ConfigLoader()
sysconf = au.get_system_conf()
log_dir = sysconf[constants.log_dir_key]
log_path = os.path.join(log_dir, 'wcravat.log')
logger = logging.getLogger()
logger.setLevel(logging.INFO)
log_handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=1024*1024*10, backupCount=5)
log_formatter = logging.Formatter('%(asctime)s: %(message)s', '%Y/%m/%d %H:%M:%S')
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)
logger.info('Starting wcravat...')

try:
    donotopenbrowser = None
    servermode = None

    parser = argparse.ArgumentParser()
    if os.path.basename(sys.argv[0]) == 'cravat-view':
        parser.add_argument('dbpath',
            nargs='?',
            default=None,
            help='path to a CRAVAT result SQLite file')
        parser.add_argument('-c',
                            dest='confpath',
                            default=None,
                            help='path to a CRAVAT configuration file')
        parser.add_argument('--username',
            dest='username',
            default=None,
            help='username of the job')
        parser.add_argument('--jobid',
            dest='job_id',
            default=None,
            help='ID of the job')
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
    parser.add_argument('--nossl',
        dest='nossl',
        action='store_true',
        default=False,
        help='Force not to accept https connection')
    parser.add_argument('--nostdoutexception',
        dest='nostdoutexception',
        action='store_true',
        default=False,
        help='Console echoes exceptions written to log file.')
    args = parser.parse_args(sys.argv[1:])
    donotopenbrowser = args.donotopenbrowser
    servermode = args.servermode
    if servermode and importlib.util.find_spec('cravatserver') is not None:
        try:
            import cravatserver
            server_ready = True
        except Exception as e:
            logger.exception(e)
            logger.info('Exiting...')
            print('Error occurred while loading open-cravat-server.\nCheck {} for details.'.format(log_path))
            exit()
    else:
        servermode = False
        server_ready = False
    wu.servermode = args.servermode
    ws.servermode = args.servermode
    wr.servermode = args.servermode
    wu.filerouter.servermode = args.servermode
    wu.server_ready = server_ready
    ws.server_ready = server_ready
    wr.server_ready = server_ready
    wu.filerouter.server_ready = server_ready
    wr.wu = wu
    if server_ready:
        cravatserver.servermode = servermode
        cravatserver.server_ready = server_ready
        cravatserver.logger = logger
        wu.cravatserver = cravatserver
        ws.cravatserver = cravatserver
    if servermode and server_ready == False:
        msg = 'open-cravat-server package is required to run OpenCRAVAT Server.\nRun "pip install open-cravat-server" to get the package.'
        logger.info(msg)
        logger.info('Exiting...')
        print(msg)
        exit()

    ssl_enabled = False
    protocol = None
    nossl = args.nossl
    if 'conf_dir' in sysconf:
        pem_path = os.path.join(sysconf['conf_dir'], 'cert.pem')
        if os.path.exists(pem_path) and nossl == False:
            ssl_enabled = True
            sc = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            sc.load_cert_chain(pem_path)
    if ssl_enabled:
        protocol = 'https://'
    else:
        protocol = 'http://'
except Exception as e:
    logger.exception(e)
    if args.nostdoutexception == False:
        traceback.print_exc()
    logger.info('Exiting...')
    print('Error occurred while loading open-cravat-server.\nCheck {} for details.'.format(log_path))
    exit()

def result ():
    global args
    try:
        dbpath = args.dbpath
        if dbpath is not None:
            dbpath = os.path.abspath(dbpath)
            if dbpath is not None and os.path.exists(dbpath) == False:
                sys.stderr.write(dbpath + ' does not exist.\n')
                exit(-1)
        username = args.username
        job_id = args.job_id
        confpath = args.confpath
        sys.argv = sys.argv[1:]
        global donotopenbrowser
        if not donotopenbrowser:
            server = get_server()
            global protocol
            url = '{host}:{port}/result/index.html'.format(host=server.get('host'), port=server.get('port'))
            if dbpath is not None:
                url = url + '?dbpath={}'.format(dbpath)
            elif username is not None and job_id is not None:
                url = url + '?username={}&job_id={}'.format(username, job_id)
            else:
                print('Provide the path to a OpenCRAVAT result sqlite file or both username and job ID')
                exit()
            webbrowser.open(protocol + url)
        main()
    except Exception as e:
        logger.exception(e)
        if args.nostdoutexception == False:
            traceback.print_exc()
        logger.info('Exiting...')
        print('Error occurred while loading open-cravat-server.\nCheck {} for details.'.format(log_path))
        exit()

def store ():
    global args
    try:
        ws.start_install_queue_manager()
        global donotopenbrowser
        if not donotopenbrowser:
            server = get_server()
            global protocol
            webbrowser.open(protocol + '{host}:{port}/store/index.html'.format(host=server.get('host'), port=server.get('port')))
    except Exception as e:
        logger.exception(e)
        if args.nostdoutexception == False:
            traceback.print_exc()
        logger.info('Exiting...')
        print('Error occurred while loading open-cravat-server.\nCheck {} for details.'.format(log_path))
        exit()

def submit ():
    global args
    try:
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
    except Exception as e:
        logger.exception(e)
        if args.nostdoutexception == False:
            traceback.print_exc()
        logger.info('Exiting...')
        print('Error occurred while loading open-cravat-server.\nCheck {} for details.'.format(log_path))
        exit()

def get_server():
    global args
    try:
        server = {}
        conf = ConfigLoader()
        pl = platform.platform()
        if pl.startswith('Windows'):
            def_host = 'localhost'
        elif pl.startswith('Linux'):
            if 'Microsoft' in pl:
                def_host = 'localhost'
            else:
                def_host = '0.0.0.0'
        elif pl.startswith('Darwin'):
            def_host = '0.0.0.0'
        else:
            def_host = 'localhost'
        host = conf.get_cravat_conf().get('gui_host', def_host)
        port = conf.get_cravat_conf().get('gui_port', 8060)
        server['host'] = host
        server['port'] = port
        return server
    except Exception as e:
        logger.exception(e)
        if args.nostdoutexception == False:
            traceback.print_exc()
        logger.info('Exiting...')
        print('Error occurred while loading open-cravat-server.\nCheck {} for details.'.format(log_path))
        exit()

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
        global ssl_enabled
        scheme = 'https' if ssl_enabled else 'http'
        return str(URL.build(scheme=scheme, host=self._host, port=self._port))

    async def start(self):
        await super().start()
        self._server = await self.loop.create_server(self._runner.server, self._host, self._port, ssl=self._ssl_context, backlog=self._backlog, reuse_address=self._reuse_address, reuse_port=self._reuse_port)

@web.middleware
async def middleware (request, handler):
    global loop
    global args
    try:
        url_parts = request.url.parts
        response = await handler(request)
        nocache = False
        if url_parts[0] == '/':
            if len(url_parts) >= 3 and url_parts[2] == 'nocache':
                nocache = True
        elif url_parts[0] == 'nocache':
            nocache = True
        if nocache:
            response.headers['Cache-Control'] = 'no-cache'
        return response
    except Exception as e:
        logger.info('Exception occurred at request={}'.format(request))
        logger.exception(e)
        if args.nostdoutexception == False:
            traceback.print_exc()

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
        global server_ready
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
        self.app.router.add_get('/heartbeat', heartbeat)
        self.app.router.add_get('/issystemready', is_system_ready)
        ws.start_worker()
        wu.start_worker()

async def heartbeat(request):
    ws = web.WebSocketResponse(timeout=60*60*24*365)
    if servermode and server_ready:
        asyncio.get_running_loop().create_task(cravatserver.update_last_active(request))
    await ws.prepare(request)
    async for msg in ws:
        pass
    return ws

async def is_system_ready (request):
    return web.json_response(dict(au.system_ready()))

loop = None
def main ():
    global args
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        def wakeup ():
            global loop
            loop.call_later(0.1, wakeup)
        serv = get_server()
        global protocol
        host = serv.get('host')
        port = serv.get('port')
        try:
            sr = s.connect_ex((host, port))
            s.close()
            if sr == 0:
                logger.info('wcravat already running. Exiting from this instance of wcravat...') 
                print('OpenCRAVAT is already running at {}{}:{}.'.format(protocol, serv.get('host'), serv.get('port')))
                return
        except requests.exceptions.ConnectionError:
            pass
        print('OpenCRAVAT is served at {}:{}'.format(serv.get('host'), serv.get('port')))
        logger.info('Serving OpenCRAVAT server at {}:{}'.format(serv.get('host'), serv.get('port')))
        print('(To quit: Press Ctrl-C or Ctrl-Break if run on a Terminal or Windows, or click "Cancel" and then "Quit" if run through OpenCRAVAT app on Mac OS)')
        global loop
        loop = asyncio.get_event_loop()
        loop.call_later(0.1, wakeup)
        async def clean_sessions():
            """
            Clean sessions every hour.
            """
            try:
                while True:
                    await cravatserver.admindb.clean_sessions()
                    await asyncio.sleep(3600)
            except Exception as e:
                logger.exception(e)
                if args.nostdoutexception == False:
                    traceback.print_exc()
        if servermode and server_ready:
            loop.create_task(clean_sessions())
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
    except Exception as e:
        logger.exception(e)
        if args.nostdoutexception == False:
            traceback.print_exc()
        logger.info('Exiting...')
        print('Error occurred while loading open-cravat-server.\nCheck {} for details.'.format(log_path))
        exit()

if __name__ == '__main__':
    main()
