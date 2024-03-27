import datetime
import os
import traceback

from flask import request, current_app, jsonify
from cravat import constants, admin_util as au


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

    # TODO: Rework with the store, this lists the contents of the global
    # install queue by.... removing it from the queue, adding it to the list
    # then pushing it back

    # global install_queue
    # temp_q = []
    # while install_queue.empty() == False:
    #     q = install_queue.get()
    #     temp_q.append([q['module'], q['version']])
    # for module, version in temp_q:
    #     content['data'][module]['queued'] = True
    #     install_queue.put({'module': module, 'version': version})

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
    # TODO: store rework, this is absolutely not threadsafe
    # handle_modules_changed()

    content = {}
    for k, v in au.mic.local.items():
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
    # TODO: Handle with store change
    # handle_modules_changed()

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

