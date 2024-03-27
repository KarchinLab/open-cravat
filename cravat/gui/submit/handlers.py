import json
import os
import traceback

from distutils.version import LooseVersion

from flask import jsonify, request
from cravat import admin_util as au
from cravat.gui.cravat_request import is_multiuser_server, request_user, file_router
from cravat.gui import metadata


def server_mode():
    return jsonify({'servermode': is_multiuser_server()})


def get_report_types():
    valid_report_types = metadata.supported_report_types()
    return jsonify({'valid': valid_report_types})


def get_system_conf_info():
    info = au.get_system_conf_info(json=True)
    return jsonify(info)


def get_last_assembly():
    default_assembly = au.get_default_assembly()
    if is_multiuser_server() and default_assembly is not None:
        assembly = default_assembly
    else:
        last_assembly = au.get_last_assembly()
        assembly = last_assembly
    return jsonify(assembly)


def get_package_versions():
    cur_ver = au.get_current_package_version()
    lat_ver = au.get_latest_package_version()
    if lat_ver is not None:
        cur_drop_patch = '.'.join(cur_ver.split('.')[:-1])
        lat_drop_patch = '.'.join(lat_ver.split('.')[:-1])
        update = LooseVersion(lat_drop_patch) > LooseVersion(cur_drop_patch)
    else:
        update = False
    d = {
        'current': cur_ver,
        'latest': lat_ver,
        'update': update
    }
    return jsonify(d)

def list_jobs():
    filerouter = file_router()
    jobs_dirs = filerouter.job_dirs

    if jobs_dirs is None:
        return jsonify([])

    all_jobs = []
    for jobs_dir in jobs_dirs:
        if not os.path.exists(jobs_dir):
            os.makedirs(jobs_dir)

        dir_it = os.scandir(jobs_dir)
        de_names = [entry.name
                    for entry
                    in dir_it
                    if not entry.name.startswith('.')]
        all_jobs.extend(de_names)
    all_jobs.sort(reverse=True)

    return jsonify(all_jobs)


def get_jobs():
    filerouter = file_router()

    if not filerouter.job_dirs:
        return jsonify([])

    ids = json.loads(request.values['ids'])
    jobs = []
    for job_id in ids:
        try:
            job =filerouter.load_job(job_id)
            if job is not None:
                jobs.append(job)
        except:
            traceback.print_exc()
            continue

    return jsonify([job.get_info_dict() for job in jobs])


def get_annotators():
    out = _filtered_module_list('annotator')
    return jsonify(out)


def get_packages():
    out = _filtered_module_list('package')
    return jsonify(out)


def _filtered_module_list(type):
    out = {
        local_info.name: {
            'name': local_info.name,
            'version': local_info.version,
            'type': local_info.type,
            'title': local_info.title,
            'description': local_info.description,
            'developer': local_info.developer
        }
        for local_info
        in au.get_local_module_infos(types=[type])
        if local_info.type == type}
    return out
