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