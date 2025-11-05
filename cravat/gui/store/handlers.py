import datetime
import os
import shutil
import traceback

from celery import current_app as celery_app
from flask import request, current_app, jsonify, g
from cravat import constants, admin_util as au, store_utils as su
from cravat.gui.models import Module
from cravat.gui.job_manager import queue_messages
from cravat.gui.admin import is_admin_loggedin
from cravat.gui.cravat_request import HTTP_BAD_REQUEST
from cravat.gui.tasks import install_module
from cravat.gui import cache


def get_storeurl():
    conf = current_app.config['CRAVAT_SYSCONF']
    store_url = conf['store_url']
    if request.is_secure:
        store_url = store_url.replace('http://', 'https://')

    return store_url


def get_base_modules():
    conf = current_app.config['CRAVAT_SYSCONF']
    base_modules = conf['base_modules']
    return jsonify(base_modules)


def get_remote_manifest():
    content = {'data': {}, 'tagdesc': {}}
    try:
        content['data'] = au.get_remote_manifest()
    except:
        traceback.print_exc()
        content = {'data': {}, 'tagdesc': {}}

    install_queue = Module.install_queue()
    for module, _ in install_queue:
        content['data'][module]['queued'] = True

    try:
        counts = au.get_download_counts()
    except:
        traceback.print_exc()
        counts = {}

    for mname in content['data']:
        content['data'][mname]['downloads'] = counts.get(mname,0)

    content['tagdesc'] = constants.module_tag_desc

    return jsonify(content)


def get_local_manifest():
    content = {}
    for k, v in Module.local().items():
        content[k] = v.serialize()
    return jsonify(content)


def get_remote_manifest_from_local():
    queries = request.values
    module = queries.get('module', None)

    if module is None:
        return jsonify([])

    module_info = au.mic.local[module]
    module_conf = module_info.conf
    response = {}
    module_dir = module_info.directory
    response['code_size'] = os.path.getsize(module_dir)
    response['commercial_warning'] = module_conf.get('commercial_warning', None)

    if not os.path.exists(module_info.data_dir):
        response['data_size'] = 0
    else:
        response['data_size'] = os.path.getsize(module_info.data_dir)

    version = module_conf.get('version', '')
    response['data_sources'] = {version: module_info.datasource}
    response['data_versions'] = {version: version}
    response['downloads'] = 0
    response['groups'] = module_info.groups
    response['has_logo'] = os.path.exists(os.path.join(module_dir, 'logo.png'))
    response['hidden'] = module_conf.get('hidden', False)
    response['latest_version'] = version
    response['publish_time'] = str(datetime.datetime.now())
    response['requires'] = module_conf.get('requires', [])
    response['size'] = response['code_size'] + response['data_size']
    response['tags'] = module_conf.get('tags', [])
    response['title'] = module_conf.get('title', '')
    response['type'] = module_conf.get('type', '')
    response['version'] = version
    response['versions'] = [version]
    response['private'] = module_conf.get('private', False)
    response['uselocalonstore'] = module_conf.get('uselocalonstore', False)
    return jsonify(response)


def get_module_updates():
    smodules = request.values.get('modules','')
    if smodules:
        modules = smodules.split(',')
    else:
        modules = []

    ret = au.get_updatable(modules=modules)
    [updates, _, conflicts] = ret
    sconflicts = {}
    for mname, reqd in conflicts.items():
        sconflicts[mname] = {}
        for req_name, req in reqd.items():
            sconflicts[mname][req_name] = str(req)

    updatesd = {
        mname: {
            'version': info.version,
            'size': info.size
        }
        for mname, info
        in updates.items()
    }

    out = {'updates': updatesd, 'conflicts': sconflicts}
    return jsonify(out)

def get_free_modules_space():
    modules_dir = au.get_modules_dir()
    free_space = shutil.disk_usage(modules_dir).free
    return jsonify(free_space)


def get_local_module_logo():
    queries = request.values
    module = queries.get('module', None)

    module_info = au.mic.local[module]
    module_dir = module_info.directory
    logo_path = os.path.join(module_dir, 'logo.png')

    return jsonify(logo_path)


def get_module_dependencies():
    queries = request.values
    module = queries.get('module')
    if module is None:
        return HTTP_BAD_REQUEST

    deps = au.get_install_deps(module)
    return jsonify(deps)

def queue_install():
    if g.is_multiuser:
        if not is_admin_loggedin():
            return 'notadmin'

    queries = request.values
    module_version = queries.get('version', None)
    module_name = queries['module']
    install_module.delay(module_name, module_version)

    deps = au.get_install_deps(module_name, module_version)
    for dep_name, dep_version in deps.items():
        install_module.delay(dep_name, dep_version)

    return f'queued {module_version}'


def uninstall_module():
    if g.is_multiuser:
        if not is_admin_loggedin():
            return 'notadmin'

    queries = request.values
    module_name = queries['name']

    au.uninstall_module(module_name)
    cache.cache.delete(Module.local.make_cache_key())

    return f'uninstalled {module_name}'

def get_module_readme(module_name, version):
    if version == 'latest':
        version=None
    readme_md = au.get_readme(module_name, version=version)
    return readme_md

def get_remote_module_config():
    queries = request.values
    module = queries['module']
    conf = au.get_remote_module_config(module)
    if 'tags' not in conf:
        conf['tags'] = []
    response = conf
    return jsonify(response)

def kill_install():
    module = request.values.get('module', None)

    # payload[0] is the job arguments, payload[0][0] is the first argument
    install_jobs = queue_messages('module_install', lambda m: m.payload[0][0] == module)

    # there should only be one, but if we happen to somehow have multiples
    # in the queue, kill them all.
    for job in install_jobs:
        task_id = job.properties.get('correlation_id')
        res = celery_app.AsyncResult(task_id)
        if not res.ready():
            res.revoke()

    return jsonify('done')

def update_remote():
    if g.is_multiuser:
        if not is_admin_loggedin():
            return 'notadmin'

    au.mic.update_remote(force=True)
    au.mic.update_local()

    return jsonify('done')

def get_featured_module_lists():
    pb = su.PathBuilder(au.get_system_conf()['store_url'], "url")
    list_url = pb.featured_module_list()
    featured_list = su.get_file_to_json(list_url)
    return jsonify(featured_list)
