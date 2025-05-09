import json
import os
import shutil
import traceback

from datetime import datetime
from distutils.version import LooseVersion

from flask import jsonify, request, abort, g, send_file
import requests
from flask import jsonify, request, abort, g
from werkzeug.utils import secure_filename

from cravat import admin_util as au, InvalidData, ConfigLoader, get_module
from cravat import constants
from cravat.gui.cravat_request import *
from cravat.gui import metadata
from cravat.gui.decorators import with_job_id_and_path
from cravat.gui.models import Job
from cravat.gui import tasks
from pathlib import Path


def server_mode():
    return jsonify({'servermode': g.is_multiuser})


def get_report_types():
    valid_report_types = metadata.supported_report_types()
    return jsonify({'valid': valid_report_types})


def get_system_conf_info():
    info = au.get_system_conf_info(json=True)
    return jsonify(info)


def get_last_assembly():
    default_assembly = au.get_default_assembly()
    if g.is_multiuser and default_assembly is not None:
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
            job = filerouter.load_job(job_id)
            if job is None:
                continue
            job.fill_reports()
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


@with_job_id_and_path
def resubmit(job_id, dbpath):
    if g.is_multiuser:
        if g.username is None:
            return jsonify({'status': 'notloggedin'})

    router = file_router()
    job = router.load_job(job_id)
    if not job.status_file_exists:
        return jsonify({'status': 'error', 'msg': 'no status file exists in job folder.'})

    assembly = job.assembly
    input_fpaths = job.orig_input_path
    note = job.note
    annotators = job.annotators

    if "original_input" in annotators:
        annotators.remove("original_input")

    cc_cohorts_path = job.info.get('cc_cohorts_path', '')

    # Subprocess arguments
    run_args = ['oc', 'run']
    for fn in input_fpaths:
        run_args.append(fn)

    # Annotators
    if len(annotators) > 0 and annotators[0] != '':
        run_args.append('-a')
        run_args.extend(annotators)
    else:
        run_args.append('-e')
        run_args.append('all')

    # Liftover assembly
    run_args.append('-l')
    run_args.append(assembly)

    # Note
    if note != '':
        run_args.append('--note')
        run_args.append(note)
    run_args.append('--keep-status')
    if cc_cohorts_path != '':
        run_args.extend(['--module-option',f'casecontrol.cohorts={cc_cohorts_path}'])

    task = tasks.run_job.s(run_args).apply_async(countdown=1)
    job.info['status'] = 'Submitted'
    job.info['celery_id'] = task.id
    job.save_status()

    return jsonify({'status': 'resubmitted'})


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

    if g.username is None:
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
    if g.is_multiuser:
        from cravat.gui.multiuser.db import AdminDb

        admindb = AdminDb()
        admindb.update_user_settings(g.username, {'lastAssembly': assembly})
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

    if g.is_multiuser:
        run_args.append('--writeadmindb')
        run_args.extend(['--jobid', job_id])

    run_args.append('--keep-status')
    if cc_cohorts_path is not None:
        run_args.extend(['--module-option', f'casecontrol.cohorts={cc_cohorts_path}'])

    job_task = tasks.run_job.delay(run_args)

    status = {'status': 'Submitted'}
    job.set_info_values(status=status)

    if g.is_multiuser:
        from cravat.gui.multiuser.db import AdminDb
        admindb = AdminDb()
        admindb.add_job_info(g.username, job)

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


def get_job_log(job_id):
    filerouter = file_router()
    job = filerouter.load_job(job_id)

    if job.log is not None:
        def file_stream():
            with open(job.log) as f:
                for line in f:
                    yield line

        return file_stream(), {"Content-Type": "text/plain"}
    else:
        return 'log file does not exist.', {"Content-Type": "text/plain"}

def get_job_err(job_id):
    filerouter = file_router()
    job = filerouter.load_job(job_id)

    if job.err is not None:
        def file_stream():
            with open(job.err) as f:
                for line in f:
                    yield line

        return file_stream(), {"Content-Type": "text/plain"}
    else:
        return 'err file does not exist.', {"Content-Type": "text/plain"}

def get_job_db(job_id):
    filerouter = file_router()
    job = filerouter.load_job(job_id)
    db_path = Path(job.db_path)
    if db_path.is_file():
        return send_file(
            db_path,
            mimetype = 'application/x-sqlite3',
            as_attachment = True,
            download_name = db_path.name,
        )
    else:
        abort(404, description='Database does not exist.')

def generate_report(job_id, report_type):
    filerouter = file_router()
    job = filerouter.load_job(job_id)
    db_path = job.db_path
    report_args = ['oc', 'report', db_path, '-t', report_type]
    tasks.run_report.delay(report_args)
    return 'done', {'Content-type': 'text/plain'}

def download_report(job_id, report_type):
    print(job_id, report_type)
    filerouter = file_router()
    job = filerouter.load_job(job_id)
    report_paths = job.reports()
    if report_type in report_paths:
        report_path = report_paths[report_type]
        return send_file(
            report_path,
            as_attachment = True,
            download_name = Path(report_path).name,
        )
    else:
        abort(404, description=f'Report of type {report_type} does not exist for job {job_id}.')

def format_hgvs_string(hgvs_input):
    hgvs_parts = hgvs_input.upper().split(':')
    if len(hgvs_parts) != 2:
        raise InvalidData('HGVS input invalid.')
    prefix = hgvs_parts[1][0].lower()
    # TODO: if HGVS API is upgraded to support p., change this here to allow it on single variant page
    if prefix not in ('g', 'c'):
        raise InvalidData('HGVS input invalid. Only g. and c. prefixes are supported.')
    end = hgvs_parts[1][1:]
    return f'{hgvs_parts[0]}:{prefix}{end}'

def get_coordinates_from_hgvs_api(queries):
    confloader = ConfigLoader()
    variant_report_config = confloader.get_module_conf('variantreport')
    if 'hgvs_api_url' not in variant_report_config:
        raise abort(500, description='"hgvs_api_url" not found in variantreport configuration.')
    hgvs_input = format_hgvs_string(queries.get('hgvs'))
    data = {'hgvs': hgvs_input}
    headers = {'Content-Type': 'application/json'}
    resp = requests.post(variant_report_config['hgvs_api_url'], data=json.dumps(data), headers=headers, timeout=20)
    try:
        resp.raise_for_status()
    except Exception as e:
        raise InvalidData(f"Error retrieving data from HGVS API. {hgvs_input} {e}")
    tokens = resp.json()
    return {
        'chrom': tokens['chrom'],
        'pos': tokens['pos'],
        'ref_base': tokens['ref'],
        'alt_base': tokens['alt'],
        'assembly': tokens['assembly']
    }

def format_allele(base):
    base_string = str(base)
    if not base_string or base_string == '':
        base_string = '-'
    return base_string

def coordinates_from_clingen_json(ca_id, data):
    genomic_alleles = data.get('genomicAlleles')
    for ga in genomic_alleles:
        if ga.get('referenceGenome') == 'GRCh38':
            coords = ga.get('coordinates')[0]
            return {
                'chrom': f'chr{ga.get("chromosome")}',
                'pos': int(coords.get('start')) + 1,
                'ref_base': format_allele(coords.get('referenceAllele')),
                'alt_base': format_allele(coords.get('allele')),
                'assembly': 'hg38'
            }
    raise abort(400, description=f'Could not find hg38 coordinates for clingen allele id {ca_id}.')


def get_coordinates_from_clingen_id(queries):
    confloader = ConfigLoader()
    VARIANT_REPORT_CONFIG = confloader.get_module_conf('variantreport')
    if 'clingen_api_url' not in VARIANT_REPORT_CONFIG:
        raise abort(500, description='"clingen_api_url" not found in variantreport configuration.')
    ca_id = queries['clingen'].strip().upper()
    headers = {'Content-Type': 'application/json'}
    request_url = f"{VARIANT_REPORT_CONFIG['clingen_api_url']}/{ca_id}"
    resp = requests.get(request_url, headers=headers, timeout=20)
    try:
        resp.raise_for_status()
    except Exception as e:
        raise InvalidData(f"Error retrieving data from Clingen Allele registry. Clingen Allele Registry Id should be formatted like 'CA12345'. {e}")
    data = resp.json()
    return coordinates_from_clingen_json(ca_id, data)


def get_coordinates_from_dbsnp(queries):
    converter_module = get_module('dbsnp-converter')
    converter = converter_module()

    dbsnp = queries.get('dbsnp').strip().lower()
    try:
        all_params = converter.convert_line(dbsnp)
    except Exception as e:
        raise InvalidData(f"Could not parse DBSNP '{dbsnp}'. Should be formatted like 'rs12345'.")
    params = all_params[0]
    params['assembly'] = 'hg38'
    alternates = None
    if len(all_params) > 1:
        alternates = all_params[1:]
    return params, alternates


def get_coordinates_from_request_params(queries):
    parameters = {}
    original_input = {}
    alternate_alleles = None
    required_coordinate_params = {'chrom', 'pos', 'ref_base', 'alt_base', 'assembly'}
    if (required_coordinate_params <= queries.keys()
        and None not in {queries[x] for x in required_coordinate_params}):
        parameters = {
            x: queries[x].upper() for x in required_coordinate_params
        }
        parameters['chrom'] = parameters['chrom'].lower()
        original_input = {'type': 'coordinates', 'input': f'{queries["assembly"]} {queries["chrom"]} {queries["pos"]} {queries["ref_base"]} {queries["alt_base"]}'}
    elif 'hgvs' in queries.keys() and queries['hgvs'] and 'assembly' in queries.keys():
        # make hgvs api call
        original_input = {'type': 'hgvs', 'input': queries['hgvs']}
        parameters = get_coordinates_from_hgvs_api(queries)
    elif 'clingen' in queries.keys() and queries.get('clingen'):
        # make clingen api call
        original_input = {'type': 'clingen', 'input': queries['clingen']}
        parameters = get_coordinates_from_clingen_id(queries)
    elif 'dbsnp' in queries.keys() and queries.get('dbsnp'):
        # use dbsnp-converter
        original_input = {'type': 'dbsnp', 'input': queries['dbsnp']}
        parameters, alternate_alleles = get_coordinates_from_dbsnp(queries)
    else:
        raise abort(400, description='Required parameters missing. Need either "chrom", "pos", "ref_base", and "alt_base", or "hgvs", or "dbsnp", or "clingen". Parameter "assembly" always required.')
    parameters['uid'] = queries.get('uid', '')
    if 'annotators' in queries.keys():
        parameters['annotators'] = queries.get('annotators', '')
    return parameters, original_input, alternate_alleles


def get_live_annotation(coordinates):
    return coordinates

def live_annotate ():
    queries = request.values if request.values else request.json
    annotators = request.values.get('annotators', None)
    try:
        coords, original_input, alternate_alleles = get_coordinates_from_request_params(queries)
    except Exception as e:
        text = str(e)
        q = {key: value for key, value in queries.items()}
        return jsonify(data={'error': text, 'originalInput': q})
    response = get_live_annotation(coords)
    # live_modules = LiveModules()
    # response = live_modules.live_annotate(coords)
    response['originalInput'] = original_input
    response['alternateAlleles'] = alternate_alleles
    return jsonify(response)
