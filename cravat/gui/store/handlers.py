import datetime
import os
import shutil
import traceback

from flask import request, current_app, jsonify
from cravat import constants, admin_util as au
from cravat.gui.models import Module
from cravat.gui.admin import is_admin_loggedin
from cravat.gui.cravat_request import is_multiuser_server, HTTP_BAD_REQUEST
from cravat.gui.tasks import install_module

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
    if is_multiuser_server():
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
