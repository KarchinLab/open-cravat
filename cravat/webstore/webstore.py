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

def get_filepath (path):
    filepath = os.sep.join(path.split('/'))
    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        filepath
        )
    return filepath

class InstallProgressMpDict(au.InstallProgressHandler):
    def __init__(self, module_name, module_version):
        super().__init__(module_name, module_version)
        self._module_name = module_name
        self._module_version = module_version
        #self._d = {}

    def _reset_progress(self, update_time=False):
        install_state['cur_chunk'] = 0
        install_state['total_chunks'] = 0
        install_state['cur_size'] = 0
        install_state['total_size'] = 0
        if update_time:
            install_state['update_time'] = time.time()

    def stage_start(self, stage):
        print('@@@ entered stage_start. stage=' + stage)
        self.cur_stage = stage
        install_state['module_name'] = self._module_name
        install_state['module_version'] = self._module_version
        install_state['stage'] = self.cur_stage
        install_state['message'] = self._stage_msg(self.cur_stage)
        self._reset_progress()
        install_state['update_time'] = time.time()

    def stage_progress(self, cur_chunk, total_chunks, cur_size, total_size):
        print('@@@ entered stage_progress. cur_chunk=' + str(cur_chunk))
        install_state['cur_chunk'] = cur_chunk
        install_state['total_chunks'] = total_chunks
        install_state['cur_size'] = cur_size
        install_state['total_size'] = total_size
        install_state['update_time'] = time.time()

def fetch_install_queue ():
    global install_queue
    print('Crawler started at pid %d' %os.getpid())
    while True:
        try:
            data = install_queue.get()
            print('@@@ queue gotten. data=' + str(data))
            au.refresh_cache()
            module_name = data['module']
            module_version = data['version']
            print('Crawler is installing %s:%s' %(module_name, module_version))
            stage_handler = InstallProgressMpDict(module_name, module_version)
            print('@@@ stage_handler=' + str(stage_handler))
            au.install_module(module_name, version=module_version, stage_handler=stage_handler, stages=100)
            print('@@@ installed: [' + module_name + ']')
            au.refresh_cache()
        except KeyboardInterrupt:
            raise
        except:
            traceback.print_exc()
'''
def install_module (handler):
    module_name = urllib.parse.unquote(queries['name'][0])
    module_version = urllib.parse.unquote(queries['version'][0])
    print('Install requested for %s:%s' %(module_name, module_version))
    install_queue.put(module)
    return web.Response()
'''

###################### start from store_handler #####################
import cravat.admin_util as au
import markdown

def get_remote_manifest(request):
    au.mic.update_remote()
    content = au.mic.remote
    return web.json_response(content)

def get_local_manifest (request):
    au.mic.update_local()
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
    return web.Response(text=content)

def install_module (request):
    queries = request.rel_url.query
    module_name = queries['name']
    if 'version' in queries:
        module_version = queries['version']
    else:
        module_version = None
    #au.install_module(module_name, version=module_version)
    queue_install(module, version)
    content = 'success'
    return web.Response(text=content)

def install_widgets_for_module (request):
    queries = request.rel_url.query
    module_name = queries['name']
    au.install_widgets_for_module(module_name)
    content = 'success'
    return web.json_response(content)

def uninstall_module (request):
    queries = request.rel_url.query
    module_name = queries['name']
    au.uninstall_module(module_name)
    print('uninstalled', module_name)
    return web.Response(text='uninstalled ' + module_name)

def start_worker ():
    global install_worker
    if install_worker == None:
        install_worker = Process(target=fetch_install_queue)
        install_worker.start()
        print('install worker started')
    
async def connect_websocket (request):
    global install_worker
    global install_state
    global install_ws
    #install_queue = Queue()
    #manager = Manager()
    #install_state = manager.dict()
    install_state['stage'] = ''
    install_state['message'] = ''
    install_state['module_name'] = ''
    install_state['module_version'] = ''
    install_state['cur_chunk'] = 0
    install_state['total_chunks'] = 0
    install_state['cur_size'] = 0
    install_state['total_size'] = 0
    install_state['update_time'] = time.time()
    if install_ws != None:
        await install_ws.close()
    install_ws = web.WebSocketResponse()
    await install_ws.prepare(request)
    last_update_time = install_state['update_time']
    while True:
        await asyncio.sleep(1)
        print('@@@ ' + str(last_update_time) + ':' + str(install_state['update_time']))
        if last_update_time < install_state['update_time']:
            data = {}
            data['module'] = install_state['module_name']
            data['msg'] = install_state['message']
            if data['msg'].startswith('Downloading'):
                data['msg'] = data['msg'] + ' ' + str(install_state['cur_chunk']) + '%'
            print('@@@ data=' + json.dumps(data))
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
    print('queue=', install_queue)
    return web.Response(text = 'queued ' + queries['module'])

install_queue = Queue()
install_state = Manager().dict()
install_worker = None
install_ws = None
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
