import asyncio
from aiohttp import web
from cravat import admin_util as au
from cravat import ConfigLoader
import os
import yaml
import json
from aiohttp_sse import sse_response
from multiprocessing import Process, Pipe, Value, Manager, Queue
import time
import traceback
import store_handlers
import sys

PROJECT_ROOT = os.path.dirname(__file__)
INSTALL_QUEUE = Queue()

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
    
async def install_module(request):
    module = await request.json()
    module_name = module['name']
    module_version = module['version']
    print('Install requested for %s:%s' %(module_name, module_version))
    INSTALL_QUEUE.put(module)
    return web.Response()

async def send_json_sse(sse, value):
    await sse.send(json.dumps(dict(value)))

async def get_install_stream(request):
    print('Install stream requested')
    async with sse_response(request) as resp:
        await send_json_sse(resp, INSTALL_STATE)
        last_update_time = INSTALL_STATE['update_time']
        while True:
            await asyncio.sleep(0.2)
            if last_update_time < INSTALL_STATE['update_time']:
                await send_json_sse(resp, INSTALL_STATE)
                last_update_time = INSTALL_STATE['update_time']


def add_routes(app):
    app.router.add_static('/static',
                          path=PROJECT_ROOT)
    app.router.add_get('/remote',
                       store_handlers.get_remote_manifest)
    app.router.add_get('/local',
                       store_handlers.get_local_manifest)
    app.router.add_get('/modules/{module}/{version}/readme',
                       store_handlers.get_module_readme)
    app.router.add_post('/install',
                        install_module)
    app.router.add_post('/uninstall',
                        store_handlers.uninstall_module)
    app.router.add_get('/installstream',
                       get_install_stream)
    
if __name__ == '__main__':
    manager = Manager()
    INSTALL_STATE = manager.dict()
    SSE_UPDATE_CONDITION = manager.Condition()
    SSE_UPDATE_EVENT = manager.Event()
    INSTALL_STATE['stage'] = ''
    INSTALL_STATE['message'] = ''
    INSTALL_STATE['module_name'] = ''
    INSTALL_STATE['module_version'] = ''
    INSTALL_STATE['cur_chunk'] = 0
    INSTALL_STATE['total_chunks'] = 0
    INSTALL_STATE['cur_size'] = 0
    INSTALL_STATE['total_size'] = 0
    INSTALL_STATE['update_time'] = time.time()
    install_worker = Process(target=install_from_queue, args=(INSTALL_QUEUE, INSTALL_STATE, SSE_UPDATE_EVENT))
    install_worker.start()
    
    app = web.Application()
    add_routes(app)
    conf_loader = ConfigLoader()
    conf = conf_loader.get_cravat_conf()
    port = conf['gui_port']
    web.run_app(app, host='localhost', port=port)