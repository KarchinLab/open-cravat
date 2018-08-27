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
import websockets

install_queue = Queue()

def get (handler):
    print('store path=', handler.request_path)
    head = handler.trim_path_head()
    if head == 'remote':
        get_remote_manifest(handler)
    elif head == 'local':
        get_local_manifest(handler)
    elif head == 'install':
        install_module(handler)
    elif head == 'installwidgetsformodule':
        install_widgets_for_module(handler)
    elif head == 'uninstall':
        uninstall_module(handler)
    elif head == 'installstream':
        get_install_stream(handler)
    elif head == 'modules':
        get_module_readme(handler)
    elif head == 'getstoreurl':
        get_storeurl(handler)
    else:
        handler.request_path = head + '/' + handler.request_path
        handler.request_path = handler.request_path.rstrip('/')
        filepath = get_filepath(handler.request_path)
        handler.serve_view(filepath)

def get_filepath (path):
    filepath = os.sep.join(path.split('/'))
    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        filepath
        )
    return filepath

class InstallProgressMpDict(au.InstallProgressHandler):
    def __init__(self, module_name, module_version, mp_dict, mp_signaler):
        super().__init__(module_name, module_version)
        self._d = mp_dict
        self._signaler = mp_signaler
        self._module_name = module_name
        self._module_version = module_version

    def _reset_progress(self, update_time=False):
        self._d['cur_chunk'] = 0
        self._d['total_chunks'] = 0
        self._d['cur_size'] = 0
        self._d['total_size'] = 0
        if update_time:
            self._d['update_time'] = time.time()

    def stage_start(self, stage):
        self.cur_stage = stage
        self._d['module_name'] = self._module_name
        self._d['module_version'] = self._module_version
        self._d['stage'] = self.cur_stage
        self._d['message'] = self._stage_msg(self.cur_stage)
        self._reset_progress()
        self._d['update_time'] = time.time()

    def stage_progress(self, cur_chunk, total_chunks, cur_size, total_size):
        self._d['cur_chunk'] = cur_chunk
        self._d['total_chunks'] = total_chunks
        self._d['cur_size'] = cur_size
        self._d['total_size'] = total_size
        self._d['update_time'] = time.time()

def install_from_queue(queue, install_state, mp_signaler):
    print('Crawler started at pid %d' %os.getpid())
    while True:
        try:
            module = queue.get()
            au.refresh_cache()
            module_name = module['name']
            module_version = module['version']
            print('Crawler is installing %s:%s' %(module_name, module_version))
            stage_handler = InstallProgressMpDict(module_name, module_version, install_state, mp_signaler)
            au.install_module(module_name, version=module_version, stage_handler=stage_handler, stages=100)
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

def send_json_sse(sse, value):
    sse.send(json.dumps(dict(value)))

def get_install_stream(request):
    print('Install stream requested')
    with sse_response(request) as resp:
        send_json_sse(resp, install_state)
        last_update_time = install_state['update_time']
        while True:
            asyncio.sleep(0.2)
            if last_update_time < install_state['update_time']:
                send_json_sse(resp, install_state)
                last_update_time = install_state['update_time']

###################### start from store_handler #####################
import cravat.admin_util as au
import markdown

def get_remote_manifest(handler):
    au.mic.update_remote()
    content = au.mic.remote
    handler.send_response(200)
    handler.send_header('Content-type', 'application/json')
    handler.end_headers()
    handler.response = bytes(json.dumps(content), 'UTF-8')
    handler.wfile.write(handler.response)

def get_storeurl (handler):
    conf = au.get_system_conf()
    content = conf['store_url']
    handler.send_response(200)
    handler.send_header('Content-type', 'text/plain')
    handler.end_headers()
    handler.response = bytes(json.dumps(content), 'UTF-8')
    handler.wfile.write(handler.response)

def get_module_readme(request):
    module_name = request.match_info['module']
    version = request.match_info['version']
    if version == 'latest': version=None
    readme_md = au.get_readme(module_name, version=version)
    if readme_md is None:
        response = web.Response()
        response.status = 404
    else:
        readme_html = markdown.markdown(readme_md)
        response = web.Response(body=readme_html,
                                content_type='text/html')
    return response

def install_module (handler):
    queries = urllib.parse.unquote(handler.request_queries)
    module_name = queries['name'][0]
    if 'version' in queries:
        module_version = queries['version'][0]
    else:
        module_version = None
    au.install_module(module_name, version=module_version)
    content = 'success'
    handler.send_response(200)
    handler.send_header('Content-type', 'application/json')
    handler.end_headers()
    handler.response = bytes(json.dumps(content), 'UTF-8')
    handler.wfile.write(handler.response)

def install_widgets_for_module (handler):
    print('queries=', handler.request_queries)
    queries = urllib.parse.unquote(handler.request_queries)
    module_name = queries['name'][0]
    if 'version' in queries:
        module_version = queries['version'][0]
    else:
        module_version = None
    au.install_module(module_name, version=module_version)
    content = 'success'
    handler.send_response(200)
    handler.send_header('Content-type', 'application/json')
    handler.end_headers()
    handler.response = bytes(json.dumps(content), 'UTF-8')
    handler.wfile.write(handler.response)

def uninstall_module(request):
    module = request.json()
    print('Uninstall requested for %s' %str(module))
    module_name = module['name']
    au.uninstall_module(module_name)
    return web.Response()

###################################### end from store_handler #######################

if __name__ == '__main__':
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
