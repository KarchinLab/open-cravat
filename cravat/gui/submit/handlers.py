import json
import os
import shutil
import traceback

from datetime import datetime
from distutils.version import LooseVersion

from flask import jsonify, request, abort
from werkzeug.utils import secure_filename

from cravat import admin_util as au
from cravat import constants
from cravat.gui.cravat_request import *
from cravat.gui import metadata
from cravat.gui.models import Job
from cravat.gui import tasks


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


def submit():
    sysconf = au.get_system_conf()
    size_cutoff = sysconf['gui_input_size_limit']

    if request.content_length is None:
        return jsonify({
            'status': 'fail',
            'msg': 'Content-Length header required'
        }), 411

    if request.content_length > size_cutoff * 1024 * 1024:
        return jsonify({
            'status': 'fail',
            'msg': f'Input is too big. Limit is {size_cutoff}MB.'
        }), 413

    if request_user() is None:
        return jsonify({'status': 'notloggedin'})

    filerouter = file_router()
    jobs_dirs = filerouter.job_dirs

    jobs_dir = jobs_dirs[0]
    job_id = Job.next_id()

    job_dir = os.path.join(jobs_dir, job_id)
    os.makedirs(job_dir, exist_ok=True)

    job_options = {}
    input_files = []
    cc_cohorts_path = None
    for part_name, part in request.files.items():
        secure_partname = secure_filename(part.filename)
        if part_name.startswith('file_'):
            input_files.append(secure_partname)
            # Have to write to disk here
            wpath = os.path.join(job_dir, secure_partname)
            part.save(wpath)
        elif part.name == 'casecontrol':
            cc_cohorts_path = os.path.join(job_dir, secure_partname)
            part.save(cc_cohorts_path)

    job_options = json.loads(request.values.get('options', ''))

    use_server_input_files = False
    if "inputServerFiles" in job_options and len(job_options["inputServerFiles"]) > 0:
        input_files = job_options["inputServerFiles"]
        input_fnames = [os.path.basename(fn) for fn in input_files]
        use_server_input_files = True
    else:
        input_fnames = input_files

    run_name = input_fnames[0]
    if len(input_fnames) > 1:
        run_name += '_and_' + str(len(input_fnames) - 1) + '_files'
    info_fname = '{}.status.json'.format(run_name)
    job_info_fpath = os.path.join(job_dir, info_fname)
    job = Job(job_dir, job_info_fpath)
    job.set_info_values(
        **job_options,
        orig_input_fname=input_fnames,
        run_name=run_name,
        submission_time=datetime.now().isoformat(),
        viewable=False
    )

    # Subprocess arguments
    input_fpaths = [os.path.join(job_dir, fn) for fn in input_fnames]
    run_args = ['oc', 'run']
    if use_server_input_files:
        for fp in input_files:
            run_args.append(fp)
        run_args.extend(['-d', job_dir])
    else:
        for fn in input_fnames:
            run_args.append(os.path.join(job_dir, fn))

    ''' Packages or Annotators '''
    if 'packages' in job_options and job_options['packages'] != '':
        packs = job_options['packages']
        run_args.append('--package')
        run_args.append(packs)
    else:
        if 'annotators' in job_options and len(job_options['annotators']) > 0 and job_options['annotators'][0] != '':
            annotators = job_options['annotators']
            annotators.sort()
            run_args.append('-a')
            run_args.extend(annotators)
        else:
            annotators = ''
            run_args.append('-e')
            run_args.append('all')
    # Liftover assembly
    run_args.append('-l')
    if 'assembly' in job_options:
        assembly = job_options['assembly']
    else:
        assembly = constants.default_assembly
    run_args.append(assembly)
    if is_multiuser_server():
        # TODO: User settings
        # await cravat_multiuser.update_user_settings(request, {'lastAssembly': assembly})
        pass
    else:
        au.set_cravat_conf_prop('last_assembly', assembly)

    # Reports
    if 'reports' in job_options and len(job_options['reports']) > 0:
        run_args.append('-t')
        run_args.extend(job_options['reports'])

    # Note
    if 'note' in job_options:
        note = job_options['note']
        if note != '':
            run_args.append('--note')
            run_args.append(note)
    # Forced input format
    if 'forcedinputformat' in job_options and job_options['forcedinputformat']:
        run_args.append('--input-format')
        run_args.append(job_options['forcedinputformat'])

    if is_multiuser_server():
        run_args.append('--writeadmindb')
        run_args.extend(['--jobid', job_id])

    run_args.append('--keep-status')
    if cc_cohorts_path is not None:
        run_args.extend(['--module-option', f'casecontrol.cohorts={cc_cohorts_path}'])

    job_task = tasks.run_job.delay(run_args)

    status = {'status': 'Submitted'}
    job.set_info_values(status=status)

    if is_multiuser_server():
        import cravat_multiuser.sync
        admindb = cravat_multiuser.sync.ServerAdminDb()
        admindb.add_job_info(request_user(), job)

    # makes temporary status.json
    status_json = {}
    status_json['job_dir'] = job_dir
    status_json['id'] = job_id
    status_json['run_name'] = run_name
    status_json['assembly'] = assembly
    status_json['db_path'] = ''
    status_json['orig_input_fname'] = input_fnames
    status_json['orig_input_path'] = input_fpaths
    status_json['submission_time'] = datetime.now().isoformat()
    status_json['viewable'] = False
    status_json['note'] = note
    status_json['status'] = 'Submitted'
    status_json['reports'] = []
    pkg_ver = au.get_current_package_version()
    status_json['open_cravat_version'] = pkg_ver
    status_json['celery_id'] = job_task.id
    if cc_cohorts_path is not None:
        status_json['cc_cohorts_path'] = cc_cohorts_path
    else:
        status_json['cc_cohorts_path'] = ''

    with open(os.path.join(job_dir, run_name + '.status.json'), 'w') as wf:
        json.dump(status_json, wf, indent=2, sort_keys=True)

    return jsonify(job.get_info_dict())


def delete_job(job_id):
    filerouter = file_router()
    job = filerouter.load_job(job_id)

    if job.task_id:
        job.task.cancel()

    if os.path.exists(job.job_dir):
        shutil.rmtree(job.job_dir)

    return HTTP_NO_CONTENT

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
