try:
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
    import time

    SERVER_ALREADY_RUNNING = -1

    conf = ConfigLoader()
    sysconf = au.get_system_conf()
    log_dir = sysconf[constants.log_dir_key]
    log_path = os.path.join(log_dir, 'wcravat.log')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    log_handler = logging.handlers.TimedRotatingFileHandler(log_path, when='d', backupCount=30)
    log_formatter = logging.Formatter('%(asctime)s: %(message)s', '%Y/%m/%d %H:%M:%S')
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)

    headless = None
    servermode = None
    server_ready = None
    ssl_enabled = None
    protocol = None
    http_only = None
    sc = None
    loop = None
    debug = False

    parser = argparse.ArgumentParser()
    parser.add_argument('--multiuser',
        dest='servermode',
        action='store_true',
        default=False,
        help='Runs in multiuser mode')
    parser.add_argument('--headless',
        action='store_true',
        default=False,
        help='do not open the cravat web page')
    parser.add_argument('--http-only',
        action='store_true',
        default=False,
        help='Force not to accept https connection')
    parser.add_argument('--debug',
        dest='debug',
        action='store_true',
        default=False,
        help='Console echoes exceptions written to log file.')
    parser.add_argument('result',
        nargs='?',
        help='Path to a CRAVAT result SQLite file')
except KeyboardInterrupt:
    import sys
    sys.exit(1)

def setup(args):
    try:
        global loop
        if sys.platform == 'win32': # Required to use asyncio subprocesses
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
        else:
            loop = asyncio.get_event_loop()
        global headless
        headless = args.headless
        global servermode
        servermode = args.servermode
        global debug
        debug = args.debug
        if servermode and importlib.util.find_spec('cravat_multiuser') is not None:
            try:
                global cravat_multiuser
                import cravat_multiuser
                loop.create_task(cravat_multiuser.setup_module())
                global server_ready
                server_ready = True
            except Exception as e:
                logger.exception(e)
                logger.info('Exiting...')
                print('Error occurred while loading open-cravat-multiuser.\nCheck {} for details.'.format(log_path))
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
            cravat_multiuser.servermode = servermode
            cravat_multiuser.server_ready = server_ready
            cravat_multiuser.logger = logger
            wu.cravat_multiuser = cravat_multiuser
            ws.cravat_multiuser = cravat_multiuser
        if servermode and server_ready == False:
            msg = 'open-cravat-server package is required to run OpenCRAVAT Server.\nRun "pip install open-cravat-server" to get the package.'
            logger.info(msg)
            logger.info('Exiting...')
            print(msg)
            exit()
        global ssl_enabled
        ssl_enabled = False
        global protocol
        protocol = None
        global http_only
        http_only = args.http_only
        if 'conf_dir' in sysconf:
            pem_path = os.path.join(sysconf['conf_dir'], 'cert.pem')
            if os.path.exists(pem_path) and http_only == False:
                ssl_enabled = True
                global sc
                sc = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                sc.load_cert_chain(pem_path)
        if ssl_enabled:
            protocol = 'https://'
        else:
            protocol = 'http://'
    except Exception as e:
        logger.exception(e)
        if debug:
            traceback.print_exc()
        logger.info('Exiting...')
        print('Error occurred while starting OpenCRAVAT server.\nCheck {} for details.'.format(log_path))
        exit()

def wcravat_entrypoint ():
    args = parser.parse_args()
    run(args)

def run(args):
    if args.servermode:
        args.headless = True
    if args.result:
        args.headless = False
        args.result = os.path.abspath(args.result)
    setup(args)
    try:
        global headless
        url = None
        if not headless:
            server = get_server()
            global server_ready
            global servermode
            host = server.get('host')
            port = server.get('port')
            if args.result:
                url = f'{host}:{port}/result/index.html?dbpath={args.result}'
            else:
                if server_ready and servermode:
                    url = f'{host}:{port}/server/nocache/login.html'
                else:
                    url = f'{host}:{port}/submit/nocache/index.html'
            global protocol
            url = protocol + url
        main(url=url)
    except Exception as e:
        logger.exception(e)
        if debug:
            traceback.print_exc()
        logger.info('Exiting...')
        print('Error occurred while starting OpenCRAVAT server.\nCheck {} for details.'.format(log_path))
        exit()
parser.set_defaults(func=run)

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
        host = au.get_system_conf().get('gui_host', def_host)
        port = au.get_system_conf().get('gui_port', 8060)
        server['host'] = host
        server['port'] = port
        return server
    except Exception as e:
        logger.exception(e)
        if debug:
            traceback.print_exc()
        logger.info('Exiting...')
        print('Error occurred while OpenCRAVAT server.\nCheck {} for details.'.format(log_path))
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
        if debug:
            traceback.print_exc()

class WebServer (object):
    def __init__ (self, host=None, port=None, loop=None, ssl_context=None, url=None):
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
        self.server_started = False
        loop.create_task(self.start())
        global headless
        if headless == False and url is not None:
            self.loop.create_task(self.open_url(url))

    async def open_url (self, url):
        while not self.server_started:
            await asyncio.sleep(0.2)
        webbrowser.open(url)

    async def start (self):
        global middleware
        global server_ready
        self.app = web.Application(loop=self.loop, middlewares=[middleware])
        if server_ready:
            cravat_multiuser.setup(self.app)
        self.setup_routes()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = TCPSitePatched(self.runner, self.host, self.port, loop=self.loop, ssl_context=self.ssl_context)
        await self.site.start()
        self.server_started = True

    def setup_routes (self):
        routes = list()
        routes.extend(ws.routes)
        routes.extend(wr.routes)
        routes.extend(wu.routes)
        global server_ready
        if server_ready:
            cravat_multiuser.add_routes(self.app.router)
        for route in routes:
            method, path, func_name = route
            self.app.router.add_route(method, path, func_name)
        source_dir = os.path.dirname(os.path.realpath(__file__))
        self.app.router.add_static('/store', os.path.join(source_dir, 'webstore'))
        self.app.router.add_static('/result', os.path.join(source_dir, 'webresult'))
        self.app.router.add_static('/submit', os.path.join(source_dir, 'websubmit'))
        self.app.router.add_get('/heartbeat', heartbeat)
        self.app.router.add_get('/issystemready', is_system_ready)
        self.app.router.add_get('/favicon.ico', serve_favicon)
        ws.start_worker()
        wu.start_worker()

async def serve_favicon (request):
    source_dir = os.path.dirname(os.path.realpath(__file__))
    return web.FileResponse(os.path.join(source_dir, 'favicon.ico'))

async def heartbeat(request):
    ws = web.WebSocketResponse(timeout=60*60*24*365)
    if servermode and server_ready:
        asyncio.get_event_loop().create_task(cravat_multiuser.update_last_active(request))
    await ws.prepare(request)
    try:
        async for msg in ws:
            pass
    except concurrent.futures._base.CancelledError:
        pass
    return ws

async def is_system_ready (request):
    return web.json_response(dict(au.system_ready()))

loop = None
def main (url=None):
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
                global SERVER_ALREADY_RUNNING
                if url and not headless:
                    webbrowser.open(url)
                return SERVER_ALREADY_RUNNING
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
            Clean sessions periodically.
            """
            try:
                max_age = au.get_system_conf().get('max_session_age',604800) # default 1 week
                interval = au.get_system_conf().get('session_clean_interval',3600) # default 1 hr
                while True:
                    await cravat_multiuser.admindb.clean_sessions(max_age)
                    await asyncio.sleep(interval)
            except Exception as e:
                logger.exception(e)
                if debug:
                    traceback.print_exc()
        if servermode and server_ready:
            if 'max_session_age' in au.get_system_conf():
                loop.create_task(clean_sessions())
        global ssl_enabled
        if ssl_enabled:
            global sc
            server = WebServer(loop=loop, ssl_context=sc, url=url)
        else:
            server = WebServer(loop=loop, url=url)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
    except Exception as e:
        logger.exception(e)
        if debug:
            traceback.print_exc()
        logger.info('Exiting...')
        print('Error occurred while starting OpenCRAVAT server.\nCheck {} for details.'.format(log_path))
        exit()

if __name__ == '__main__':
    main()
