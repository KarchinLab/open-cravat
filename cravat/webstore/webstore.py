from cravat import admin_util as au
from cravat import ConfigLoader
import os
import yaml
import json
from multiprocessing import Process, Pipe, Value, Manager, Queue
import time
import traceback
import sys
import urllib
import asyncio
from aiohttp import web
from html.parser import HTMLParser
from cravat import store_utils as su
from cravat import constants
#from aiohttp_session import get_session, new_session

system_conf = au.get_system_conf()
pathbuilder = su.PathBuilder(system_conf['store_url'],'url')
install_queue = None
install_state = None
install_worker = None
install_ws = None
last_update_time = 0

def get_filepath (path):
    filepath = os.sep.join(path.split('/'))
    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        filepath
        )
    return filepath

class InstallProgressMpDict(au.InstallProgressHandler):

    def __init__(self, module_name, module_version, install_state):
        super().__init__(module_name, module_version)
        self._module_name = module_name
        self._module_version = module_version
        self.install_state = install_state

    def _reset_progress(self, update_time=False):
        #global install_state
        self.install_state['cur_chunk'] = 0
        self.install_state['total_chunks'] = 0
        self.install_state['cur_size'] = 0
        self.install_state['total_size'] = 0
        if update_time:
            self.install_state['update_time'] = time.time()

    def stage_start(self, stage):
        global install_worker
        global install_ws
        global last_update_time
        if self.install_state == None or len(self.install_state.keys()) == 0:
            self.install_state['stage'] = ''
            self.install_state['message'] = ''
            self.install_state['module_name'] = ''
            self.install_state['module_version'] = ''
            self.install_state['cur_chunk'] = 0
            self.install_state['total_chunks'] = 0
            self.install_state['cur_size'] = 0
            self.install_state['total_size'] = 0
            self.install_state['update_time'] = time.time()
            last_update_time = install_state['update_time']
        self.cur_stage = stage
        self.install_state['module_name'] = self._module_name
        self.install_state['module_version'] = self._module_version
        self.install_state['stage'] = self.cur_stage
        self.install_state['message'] = self._stage_msg(self.cur_stage)
        self._reset_progress()
        self.install_state['update_time'] = time.time()

    def stage_progress(self, cur_chunk, total_chunks, cur_size, total_size):
        #global install_state
        self.install_state['cur_chunk'] = cur_chunk
        self.install_state['total_chunks'] = total_chunks
        self.install_state['cur_size'] = cur_size
        self.install_state['total_size'] = total_size
        self.install_state['update_time'] = time.time()

def fetch_install_queue (install_queue, install_state):
    while True:
        try:
            data = install_queue.get()
            au.refresh_cache()
            module_name = data['module']
            module_version = data['version']
            stage_handler = InstallProgressMpDict(module_name, module_version, install_state)
            au.install_module(module_name, version=module_version, stage_handler=stage_handler, stages=100)
            au.refresh_cache()
            time.sleep(1)
        except KeyboardInterrupt:
            raise
        except:
            traceback.print_exc()

###################### start from store_handler #####################
import cravat.admin_util as au
import markdown

def get_remote_manifest(request):
    try:
        au.mic.update_remote()
        content = au.mic.remote
    except:
        content = {}
    global install_queue
    temp_q = []
    while install_queue.empty() == False:
        q = install_queue.get()
        temp_q.append([q['module'], q['version']])
    for module, version in temp_q:
        content[module]['queued'] = True
        install_queue.put({'module': module, 'version': version})
    return web.json_response(content)

def get_local_manifest (request):
    au.refresh_cache()
    content = {}
    for k, v in au.mic.local.items():
        content[k] = v.serialize()
    return web.json_response(content)

def get_storeurl (request):
    conf = au.get_system_conf()
    return web.Response(text=conf['store_url'])

def get_module_readme (request):
    module_name = request.match_info['module']
    version = request.match_info['version']
    if version == 'latest': 
        version=None
    readme_md = au.get_readme(module_name, version=version)
    if readme_md is None:
        content = ''
    else:
        content = markdown.markdown(readme_md)
        global system_conf
        global pathbuilder
        if module_name in au.mic.remote:
            imgsrceditor = ImageSrcEditor(pathbuilder.module_version_dir(module_name, au.mic.remote[module_name]['latest_version']))
            imgsrceditor.feed(content)
            content = imgsrceditor.get_parsed()
    headers = {'Content-Type': 'text/html'}
    return web.Response(body=content, headers=headers)

class ImageSrcEditor(HTMLParser):
    def __init__ (self, prefix_url):
        super().__init__()
        self.prefix_url = prefix_url
        self.parsed = ''

    def handle_starttag(self, tag, attrs):
        html = '<{}'.format(tag)
        if tag == 'img':
            attrs.append(['style', 'width:100%'])
        for name, value in attrs:
            if tag == 'img' and name == 'src':
                value = self.prefix_url + '/' + value.lstrip('/')
            html += ' {name}="{value}"'.format(name=name, value=value)
        html += '>'
        self.parsed += html

    def handle_data(self, data):
        self.parsed += data

    def handle_endtag(self, tag):
        self.parsed += '</{}>'.format(tag)

    def get_parsed(self):
        return self.parsed

async def check_admin_priv (request):
    '''
    session = await get_session(request)
    if 'logged' in session and 'username' in session and session['username'] == 'admin' and session['logged'] == True:
        response = True
    else:
        response = False
    '''
    response = True
    return response

async def install_module (request):
    isadmin = await check_admin_priv(request)
    if isadmin:
        queries = request.rel_url.query
        module_name = queries['name']
        if 'version' in queries:
            module_version = queries['version']
        else:
            module_version = None
        #au.install_module(module_name, version=module_version)
        queue_install(module_name, module_version)
        response = 'success'
    else:
        response = 'failure'
    return web.json_response(content)

def install_widgets_for_module (request):
    queries = request.rel_url.query
    module_name = queries['name']
    au.install_widgets_for_module(module_name)
    content = 'success'
    return web.json_response(content)

async def uninstall_module (request):
    isadmin = await check_admin_priv(request)
    if isadmin:
        queries = request.rel_url.query
        module_name = queries['name']
        au.uninstall_module(module_name)
        return web.json_response('uninstalled ' + module_name)
    else:
        return web.json_response('failure')

def start_worker ():
    global install_worker
    global install_queue
    global install_state
    install_queue = Queue()
    install_state = Manager().dict()
    if install_worker == None:
        install_worker = Process(target=fetch_install_queue, args=(install_queue, install_state,))
        install_worker.start()

async def connect_websocket (request):
    global install_worker
    global install_state
    global install_ws
    global last_update_time
    if install_state == None or len(install_state.keys()) == 0:
        install_state['stage'] = ''
        install_state['message'] = ''
        install_state['module_name'] = ''
        install_state['module_version'] = ''
        install_state['cur_chunk'] = 0
        install_state['total_chunks'] = 0
        install_state['cur_size'] = 0
        install_state['total_size'] = 0
        install_state['update_time'] = time.time()
        last_update_time = install_state['update_time']
    if install_ws != None:
        await install_ws.close()
    install_ws = web.WebSocketResponse()
    await install_ws.prepare(request)
    while True:
        await asyncio.sleep(1)
        if last_update_time < install_state['update_time']:
            data = {}
            data['module'] = install_state['module_name']
            data['msg'] = install_state['message']
            if data['msg'].startswith('Downloading'):
                data['msg'] = data['msg'] + ' ' + str(install_state['cur_chunk']) + '%'
            await install_ws.send_str(json.dumps(data))
            last_update_time = install_state['update_time']
    return install_ws

def queue_install (request):
    global install_queue
    queries = request.rel_url.query
    if 'version' in queries:
        module_version = queries['version']
    else:
        module_version = None
    data = {'module': queries['module'], 'version': module_version}
    install_queue.put(data)
    return web.Response(text = 'queued ' + queries['module'])

def get_base_modules (request):
    global system_conf
    base_modules = system_conf['base_modules']
    return web.json_response(base_modules)

async def install_base_modules (request):
    isadmin = await check_admin_priv(request)
    if isadmin:
        base_modules = system_conf.get(constants.base_modules_key,[])
        for module in base_modules:
            install_queue.put({'module': module, 'version': None})
        response = 'queued'
    else:
        response = 'failed'
    return web.json_response(response)

def get_md (request):
    modules_dir = au.get_modules_dir()
    return web.Response(text=modules_dir)

routes = []
routes.append(['GET', '/store/remote', get_remote_manifest])
routes.append(['GET', '/store/install', install_module])
routes.append(['GET', '/store/installwidgetsformodule', install_widgets_for_module])
routes.append(['GET', '/store/getstoreurl', get_storeurl])
routes.append(['GET', '/store/local', get_local_manifest])
routes.append(['GET', '/store/uninstall', uninstall_module])
routes.append(['GET', '/store/connectwebsocket', connect_websocket])
routes.append(['GET', '/store/queueinstall', queue_install])
routes.append(['GET', '/store/modules/{module}/{version}/readme', get_module_readme])
routes.append(['GET', '/store/getbasemodules', get_base_modules])
routes.append(['GET', '/store/installbasemodules', install_base_modules])
routes.append(['GET', '/store/getmd', get_md])
