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
import cravat.admin_util as au
import markdown
import shutil
import copy

system_conf = au.get_system_conf()
pathbuilder = su.PathBuilder(system_conf['store_url'],'url')
install_queue = None
install_state = None
install_worker = None
install_ws = None

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
        self.module_name = module_name
        self.module_version = module_version
        self.install_state = install_state

    def _reset_progress(self, update_time=False):
        self.install_state['cur_chunk'] = 0
        self.install_state['total_chunks'] = 0
        self.install_state['cur_size'] = 0
        self.install_state['total_size'] = 0
        if update_time:
            self.install_state['update_time'] = time.time()

    def stage_start(self, stage):
        global install_worker
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
            last_update_time = self.install_state['update_time']
        self.cur_stage = stage
        self.install_state['module_name'] = self.module_name
        self.install_state['module_version'] = self.module_version
        self.install_state['stage'] = self.cur_stage
        self.install_state['message'] = self._stage_msg(self.cur_stage)
        self.install_state['kill_signal'] = False
        self._reset_progress()
        self.install_state['update_time'] = time.time()
        print(self.install_state['message'])

    def stage_progress(self, cur_chunk, total_chunks, cur_size, total_size):
        self.install_state['cur_chunk'] = cur_chunk
        self.install_state['total_chunks'] = total_chunks
        self.install_state['cur_size'] = cur_size
        self.install_state['total_size'] = total_size
        self.install_state['update_time'] = time.time()

def fetch_install_queue (install_queue, install_state):
    while True:
        try:
            data = install_queue.get()
            au.mic.update_local()
            module_name = data['module']
            module_version = data['version']
            install_state['kill_signal'] = False
            stage_handler = InstallProgressMpDict(module_name, module_version, install_state)
            au.install_module(module_name, version=module_version, stage_handler=stage_handler, stages=100)
            au.mic.update_local()
            time.sleep(1)
        except:
            sys.exit()

###################### start from store_handler #####################

async def get_remote_manifest(request):
    try:
        if au.mic.remote == {}:
            au.mic.update_remote()
        content = au.mic.remote
    except:
        traceback.print_exc()
        content = {}
    global install_queue
    temp_q = []
    while install_queue.empty() == False:
        q = install_queue.get()
        temp_q.append([q['module'], q['version']])
    for module, version in temp_q:
        content[module]['queued'] = True
        install_queue.put({'module': module, 'version': version})
    try:
        counts = au.get_download_counts()
    except:
        traceback.print_exc()
        counts = {}
    for mname in content:
        content[mname]['downloads'] = counts.get(mname,0)
    return web.json_response(content)

async def get_remote_module_config (request):
    queries = request.rel_url.query
    module = queries['module']
    conf = au.get_remote_module_config(module)
    if 'tags' not in conf:
        conf['tags'] = []
    response = conf
    return web.json_response(response)

async def get_local_manifest (request):
    #au.refresh_cache()
    au.mic.update_local()
    content = {}
    for k, v in au.mic.local.items():
        content[k] = v.serialize()
    return web.json_response(content)

async def get_storeurl (request):
    conf = au.get_system_conf()
    return web.Response(text=conf['store_url'])

async def get_module_readme (request):
    module_name = request.match_info['module']
    version = request.match_info['version']
    if version == 'latest': 
        version=None
    readme_md = au.get_readme(module_name, version=version)
    if readme_md is None:
        content = ''
    else:
        content = markdown.markdown(readme_md, extensions=['tables'])
        global system_conf
        global pathbuilder
        if module_name in au.mic.remote:
            imgsrceditor = ImageSrcEditor(pathbuilder.module_version_dir(module_name, au.mic.remote[module_name]['latest_version']))
            imgsrceditor.feed(content)
            content = imgsrceditor.get_parsed()
            linkouteditor = LinkOutEditor(pathbuilder.module_version_dir(module_name, au.mic.remote[module_name]['latest_version']))
            linkouteditor.feed(content)
            content = linkouteditor.get_parsed()
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
            attrs.append(['style', 'display:block;margin:auto;max-width:100%'])
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

class LinkOutEditor(HTMLParser):
    def __init__ (self, prefix_url):
        super().__init__()
        self.prefix_url = prefix_url
        self.parsed = ''
    def handle_starttag(self, tag, attrs):
        html = '<{}'.format(tag)
        if tag == 'a':
            attrs.append(['target', '_blank'])
        for name, value in attrs:
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

'''
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
'''

async def install_widgets_for_module (request):
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

async def send_socket_msg ():
    global install_ws
    data = {}
    data['module'] = install_state['module_name']
    data['msg'] = install_state['message']
    if data['msg'].startswith('Downloading'):
        data['msg'] = data['msg'] + ' ' + str(install_state['cur_chunk']) + '%'
    await install_ws.send_str(json.dumps(data))
    last_update_time = install_state['update_time']
    return last_update_time

async def connect_websocket (request):
    global install_state
    global install_ws
    if not install_state:
        install_state['stage'] = ''
        install_state['message'] = ''
        install_state['module_name'] = ''
        install_state['module_version'] = ''
        install_state['cur_chunk'] = 0
        install_state['total_chunks'] = 0
        install_state['cur_size'] = 0
        install_state['total_size'] = 0
        install_state['update_time'] = time.time()
        install_state['kill_signal'] = False
    last_update_time = install_state['update_time']
    install_ws = web.WebSocketResponse(timeout=60*60*24*365)
    await install_ws.prepare(request)
    while True:
        await asyncio.sleep(1)
        if last_update_time < install_state['update_time']:
            last_update_time = await send_socket_msg()
    return install_ws

async def queue_install (request):
    global install_queue
    queries = request.rel_url.query
    if 'version' in queries:
        module_version = queries['version']
    else:
        module_version = None
    module_name = queries['module']
    data = {'module': module_name, 'version': module_version}
    install_queue.put(data)
    deps = au.get_install_deps(module_name, module_version)
    for dep_name, dep_version in deps.items():
        install_queue.put({'module':dep_name,'version':dep_version})
    return web.Response(text = 'queued ' + queries['module'])

async def get_base_modules (request):
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

async def get_md (request):
    modules_dir = au.get_modules_dir()
    return web.Response(text=modules_dir)

async def get_module_updates (request):
    queries = request.rel_url.query
    smodules = queries.get('modules','')
    if smodules:
        modules = smodules.split(',')
    else:
        modules = []
    updates, _, conflicts = au.get_updatable(modules=modules)
    sconflicts = {}
    for mname, reqd in conflicts.items():
        sconflicts[mname] = {}
        for req_name, req in reqd.items():
            sconflicts[mname][req_name] = str(req)
    updatesd = {mname:{'version':info.version,'size':info.size} for mname, info in updates.items()}
    out = {'updates':updatesd,'conflicts':sconflicts}
    return web.json_response(out)

async def get_free_modules_space (request):
    modules_dir = au.get_modules_dir()
    free_space = shutil.disk_usage(modules_dir).free
    return web.json_response(free_space)

def unqueue (module):
    global install_queue
    if module is not None:
        tmp_queue_data = []
        while True:
            if install_queue.empty():
                break
            data = install_queue.get()
            if data['module'] != module:
                tmp_queue_data.append([data['module'], data.get('version', '')])
    for data in tmp_queue_data:
        install_queue.put({'module': data[0], 'version': data[1]})

async def kill_install (request):
    global install_queue
    global install_state
    queries = request.rel_url.query
    module = queries.get('module', None)
    if 'module_name' in install_state and install_state['module_name'] == module:
        install_state['kill_signal'] = True
    return web.json_response('done')

async def unqueue_install (request):
    global install_state
    queries = request.rel_url.query
    module = queries.get('module', None)
    unqueue(module)
    module_name_bak = install_state['module_name']
    msg_bak = install_state['message']
    install_state['module_name'] = module
    install_state['message'] = 'Unqueued'
    await send_socket_msg()
    install_state['module_name'] = module_name_bak
    install_state['message'] = msg_bak

    return web.json_response('done')

routes = []
routes.append(['GET', '/store/remote', get_remote_manifest])
#routes.append(['GET', '/store/install', install_module])
routes.append(['GET', '/store/installwidgetsformodule', install_widgets_for_module])
routes.append(['GET', '/store/getstoreurl', get_storeurl])
routes.append(['GET', '/store/local', get_local_manifest])
routes.append(['GET', '/store/uninstall', uninstall_module])
routes.append(['GET', '/store/connectwebsocket', connect_websocket])
routes.append(['GET', '/store/queueinstall', queue_install])
routes.append(['GET', '/store/modules/{module}/{version}/readme', get_module_readme])
routes.append(['GET', '/store/getbasemodules', get_base_modules])
routes.append(['GET', '/store/installbasemodules', install_base_modules])
routes.append(['GET', '/store/remotemoduleconfig', get_remote_module_config])
routes.append(['GET', '/store/getmd', get_md])
routes.append(['GET', '/store/updates', get_module_updates])
routes.append(['GET', '/store/freemodulesspace', get_free_modules_space])
routes.append(['GET', '/store/killinstall', kill_install])
routes.append(['GET', '/store/unqueue', unqueue_install])
