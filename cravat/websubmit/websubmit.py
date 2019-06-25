import os
import time
import datetime
import subprocess
import yaml
import json
from cravat import admin_util as au
from cravat import ConfigLoader, run_cravat_job
import sys
import traceback
import shutil
from aiohttp import web
#from cryptography import fernet
#from aiohttp_session import get_session, new_session
import aiosqlite3
import hashlib
from distutils.version import LooseVersion
import glob
import platform
import signal
import multiprocessing as mp
import asyncio

cfl = ConfigLoader()

class FileRouter(object):

    def __init__(self):
        self.root = os.path.dirname(__file__)
        self.input_fname = 'input'
        self.report_extensions = {
            'text':'.tsv',
            'excel':'.xlsx'
        }
        self.db_extension = '.sqlite'
        self.log_extension = '.log'

    async def get_jobs_dir (self, request):
        root_jobs_dir = au.get_jobs_dir()
        '''
        session = await get_session(request)
        if servermode:
            if 'logged' in session:
                if session['logged'] != True:
                    session['username'] = ''
                    session['logged'] = False
                    return None
                else:
                    username = session['username']
            else:
                session['logged'] = False
                session['username'] = ''
                return None
        else:
            username = 'default'
        session['username'] = username
        '''
        username = 'default'
        jobs_dir = os.path.join(root_jobs_dir, username)
        return jobs_dir

    async def job_dir(self, request, job_id):
        jobs_dir = await self.get_jobs_dir(request)
        if jobs_dir == None:
            return None
        else:
            return os.path.join(jobs_dir, job_id)

    async def job_input(self, request, job_id):
        job_dir, statusjson = await self.job_status(request, job_id)
        orig_input_fname = None
        if 'orig_input_fname' in statusjson:
            orig_input_fname = statusjson['orig_input_fname']
        else:
            fns = os.listdir(job_dir)
            for fn in fns:
                if fn.endswith('.crv'):
                    orig_input_fname = fn[:-4]
                    break
        if orig_input_fname is not None:
            orig_input_path = os.path.join(job_dir, orig_input_fname)
        else:
            orig_input_path = None
        return orig_input_path
    
    async def job_run_name(self, request, job_id):
        job_dir, statusjson = await self.job_status(request, job_id)
        run_name = statusjson.get('run_name')
        if run_name is None:
            fns = os.listdir(job_dir)
            for fn in fns:
                if fn.endswith('.crv'):
                    run_name = fn[:-4]
                    break
        return run_name

    async def job_run_path(self, request, job_id):
        job_dir, _ = await self.job_status(request, job_id)
        run_name = await self.job_run_name(request, job_id)
        if run_name is not None:
            run_path = os.path.join(job_dir, run_name)
        else:
            run_path = None
        return run_path

    async def job_db(self, request, job_id):
        run_path = await self.job_run_path(request, job_id)
        output_fname = run_path + self.db_extension
        return output_fname

    async def job_report(self, request, job_id, report_type):
        ext = self.report_extensions.get(report_type, '.'+report_type)
        run_path = await self.job_run_path(request, job_id)
        if run_path is None:
            return None
        report_path = run_path + ext
        return report_path

    async def job_status (self, request, job_id):
        job_dir = await self.job_dir(request, job_id)
        fns = os.listdir(job_dir)
        statusjson = {}
        for fn in fns:
            if fn.endswith('.status.json'):
                with open(os.path.join(job_dir, fn)) as f:
                    statusjson = json.loads(f.readline())
            elif fn.endswith('.info.yaml'):
                with open(os.path.join(job_dir, fn)) as f:
                    statusjson = yaml.load(f)
        return job_dir, statusjson

    '''
    def get_orig_input_path (self, request, job_id):
        job_dir = await self.job_dir(request, job_id)
        fns = os.listdir(job_dir)
        orig_input_fname = None
        for fn in fns:
            if fn.endswith('.status.json'):
                with open(os.path.join(job_dir, fn)) as f:
                    statusjson = json.loads(f.readline())
                    if 'orig_input_fname' in statusjson:
                        orig_input_fname = statusjson['orig_input_fname']
            elif fn.endswith('.info.yaml'):
                with open(os.path.join(job_dir, fn)) as f:
                    infojson = yaml.load(f)
                    if 'orig_input_fname' in infojson:
                        orig_input_fname = infojson['orig_input_fname']
        if orig_input_fname is not None:
            orig_input_path = os.path.join(job_dir, orig_input_fname + '.log')
            if os.path.exists(orig_input_path) == False:
                orig_input_path = None
        else:
            orig_input_path = None
        return orig_input_path
    '''

    async def job_log (self, request, job_id):
        run_path = await self.job_run_path(request, job_id)
        if run_path is not None:
            log_path = run_path + '.log'
            if os.path.exists(log_path) == False:
                log_path = None
        else:
            log_path = None
        return log_path

class WebJob(object):
    def __init__(self, job_dir, job_status_fpath):
        self.info = {}
        self.job_dir = job_dir
        self.job_status_fpath = job_status_fpath
        self.info['id'] = os.path.basename(job_dir)

    def save_job_options (self, job_options):
        self.set_values(**job_options)

    def read_info_file(self):
        with open(self.job_status_fpath) as f:
            info_dict = yaml.load(f)
        if info_dict != None:
            self.set_values(**info_dict)

    def set_info_values(self, **kwargs):
        self.set_values(**kwargs)

    def get_info_dict(self):
        return self.info

    def set_values(self, **kwargs):
        self.info.update(kwargs)

def get_next_job_id():
    return datetime.datetime.now().strftime(r'%y%m%d-%H%M%S')

async def submit (request):
    global filerouter
    global job_tracker
    job_id = get_next_job_id()
    jobs_dir = await filerouter.get_jobs_dir(request)
    job_id = get_next_job_id()
    job_dir = os.path.join(jobs_dir, job_id)
    os.makedirs(job_dir, exist_ok=True)
    reader = await request.multipart()
    job_options = None
    input_files = []
    while True:
        part = await reader.next()
        if not part: 
            break 
        if part.name.startswith('file_'):
            input_files.append(part)
            # Have to write to disk here
            wfname = part.filename
            wpath = os.path.join(job_dir, wfname)
            with open(wpath,'wb') as wf:
                wf.write(await part.read())
        elif part.name == 'options':
            job_options = await part.json()
    input_fnames = [fp.filename for fp in input_files]
    if len(input_fnames) == 1:
        orig_input_fname = input_fnames[0]
    elif len(input_fnames) > 1:
        orig_input_fname = ', '.join([os.path.basename(x) for x in input_fnames])
    info_fname = '{}.status.json'.format(orig_input_fname)
    job_info_fpath = os.path.join(job_dir, info_fname)
    job = WebJob(job_dir, job_info_fpath)
    job.save_job_options(job_options)
    job.set_info_values(
                        orig_input_fname=orig_input_fname,
                        orig_input_files=input_fnames,
                        submission_time=datetime.datetime.now().isoformat(),
                        viewable=False
                        )
    # Subprocess arguments
    input_fpaths = [os.path.join(job_dir, fn) for fn in input_fnames]
    tot_lines = 0
    for fpath in input_fpaths:
        with open(fpath) as f:
            tot_lines += count_lines(f)
    #expected_runtime = get_expected_runtime(tot_lines, job_options['annotators'])
    run_args = ['cravat']
    for fn in input_fnames:
        run_args.append(os.path.join(job_dir, fn))
    # Annotators
    if len(job_options['annotators']) > 0:
        run_args.append('-a')
        run_args.extend(job_options['annotators'])
    else:
        run_args.append('-e')
        run_args.append('*')
    # Liftover assembly
    run_args.append('-l')
    run_args.append(job_options['assembly'])
    au.set_cravat_conf_prop('last_assembly', job_options['assembly'])
    # Reports
    if len(job_options['reports']) > 0:
        run_args.append('-t')
        run_args.extend(job_options['reports'])
    else:
        run_args.append('--sr')
    # Note
    if 'note' in job_options:
        run_args.append('--note')
        run_args.append(job_options['note'])
    # Forced input format
    if 'forcedinputformat' in job_options:
        run_args.append('--forcedinputformat')
        run_args.append(job_options['forcedinputformat'])
    p = subprocess.Popen(run_args)
    job_tracker.add_job(job_id, p)
    status = {'status': 'Submitted'}
    job.set_info_values(status=status)
    # admin.sqlite
    # if servermode:
    #     root_jobs_dir = au.get_jobs_dir()
    #     admin_db_path = os.path.join(root_jobs_dir, 'admin.sqlite')
    #     db = await aiosqlite3.connect(admin_db_path)
    #     cursor = await db.cursor()
    #     '''
    #     session = await get_session(request)
    #     username = session['username']
    #     '''
    #     username = 'default'
    #     await cursor.execute('insert into jobs values ("{}", "{}", "{}", {}, {}, "{}", "{}")'.format(job_id, username, job.get_info_dict()['submission_time'], -1, -1, '', job_options['assembly']))
    #     await db.commit()
    #     cursor.close()
    #     db.close()
    return web.json_response(job.get_info_dict())

def count_lines(f):
    n = 0
    for _ in f:
        n+=1
    return n

def get_expected_runtime(num_lines, annotators):
    mapper_vps = 1000
    annot_vps = 5000
    agg_vps = 8000
    return num_lines*(1/mapper_vps + len(annotators)/annot_vps + 1/agg_vps)

def get_annotators(request):
    out = {}
    for local_info in au.get_local_module_infos(types=['annotator']):
        module_name = local_info.name
        if local_info.type == 'annotator':
            out[module_name] = {
                                'name':module_name,
                                'version':local_info.version,
                                'type':local_info.type,
                                'title':local_info.title,
                                'description':local_info.description,
                                'developer': local_info.developer
                                }
    return web.json_response(out)

def find_files_by_ending (d, ending):
    fns = os.listdir(d)
    files = []
    for fn in fns:
        if fn.endswith(ending):
            files.append(fn)
    return files

async def get_job (job_id, request):
    global filerouter
    jobs_dir = await filerouter.get_jobs_dir(request)
    if jobs_dir is None:
        return None
    if os.path.exists(jobs_dir) == False:
        os.mkdir(jobs_dir)
    job_dir = os.path.join(jobs_dir, job_id)
    if os.path.exists(job_dir) == False:
        return None
    if os.path.isdir(job_dir) == False:
        return None
    fns = find_files_by_ending(job_dir, '.status.json')
    if len(fns) < 1:
        return None
    status_fname = fns[0]
    status_fpath = os.path.join(job_dir, status_fname)
    job = WebJob(job_dir, status_fpath)
    job.read_info_file()
    fns = find_files_by_ending(job_dir, '.info.yaml')
    if len(fns) > 0:
        info_fpath = os.path.join(job_dir, fns[0])
        with open (info_fpath) as f:
            info_json = yaml.load('\n'.join(f.readlines()))
            for k, v in info_json.items():
                if k == 'status' and 'status' in job.info:
                    continue
                job.info[k] = v
    fns = find_files_by_ending(job_dir, '.sqlite')
    if len(fns) > 0:
        db_path = os.path.join(job_dir, fns[0])
    else:
        db_path = ''
    job_viewable = os.path.exists(db_path)
    job.set_info_values(
        viewable=job_viewable,
        db_path=db_path,
        status=job.info['status'],
    )
    existing_reports = []
    for report_type in get_valid_report_types():
        # ext = filerouter.report_extensions.get(report_type, '.'+report_type)
        # job_input = await filerouter.job_input(request, job_id)
        # if job_input is None:
        #     continue
        # report_fname = job_input + ext
        # report_file = os.path.join(job_dir, report_fname)
        report_path = await filerouter.job_report(request, job_id, report_type)
        if report_path is not None and os.path.exists(report_path):
            existing_reports.append(report_type)
    job.set_info_values(reports=existing_reports)
    return job

async def get_jobs (request):
    global filerouter
    jobs_dir = await filerouter.get_jobs_dir(request)
    if jobs_dir is None:
        return web.json_response([])
    if os.path.exists(jobs_dir) == False:
        os.mkdir(jobs_dir)
    queries = request.rel_url.query
    ids = json.loads(queries['ids'])
    jobs = []
    for job_id in ids:
        try:
            job = await get_job(job_id, request)
            if job is not None:
                jobs.append(job)
        except:
            traceback.print_exc()
            continue
    return web.json_response([job.get_info_dict() for job in jobs])

async def get_all_jobs (request):
    global filerouter
    jobs_dir = await filerouter.get_jobs_dir(request)
    if jobs_dir is None:
        return web.json_response([])
    if os.path.exists(jobs_dir) == False:
        os.mkdir(jobs_dir)
    ids = os.listdir(jobs_dir)
    ids.sort(reverse=True)
    all_jobs = []
    for job_id in ids:
        try:
            job = await get_job(job_id, request)
            if job is None:
                continue
            all_jobs.append(job)
        except:
            traceback.print_exc()
            continue
    return web.json_response([job.get_info_dict() for job in all_jobs])

async def view_job(request):
    global VIEW_PROCESS
    global filerouter
    job_id = request.match_info['job_id']
    db_path = await filerouter.job_db(request, job_id)
    if os.path.exists(db_path):
        if type(VIEW_PROCESS) == subprocess.Popen:
            VIEW_PROCESS.kill()
        VIEW_PROCESS = subprocess.Popen(['cravat-view', db_path])
        return web.Response()
    else:
        return web.Response(status=404)

async def delete_job(request):
    global filerouter
    global job_tracker
    job_id = request.match_info['job_id']
    if job_tracker.get_process(job_id) is not None:
        print('\nKilling job {}'.format(job_id))
        await job_tracker.cancel_job(job_id)
    job_dir = await filerouter.job_dir(request, job_id)
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
        return web.Response()
    else:
        return web.Response(status=404)

async def download_db(request):
    global filerouter
    job_id = request.match_info['job_id']
    db_path = await filerouter.job_db(request, job_id)
    db_fname = job_id+'.sqlite'
    headers = {'Content-Disposition': 'attachment; filename='+db_fname}
    return web.FileResponse(db_path, headers=headers)

async def get_job_log (request):
    global filerouter
    job_id = request.match_info['job_id']
    log_path = await filerouter.job_log(request, job_id)
    if log_path is not None:
        with open(log_path) as f:
            return web.Response(text=f.read())
    else:
        return web.Response(text='log file does not exist.')

def get_valid_report_types():
    reporter_infos = au.get_local_module_infos(types=['reporter'])
    report_types = [x.name.split('reporter')[0] for x in reporter_infos]
    return report_types

def get_report_types(request):
    global cfl
    default_reporter = cfl.get_cravat_conf_value('reporter')
    default_type = default_reporter.split('reporter')[0]
    valid_types = get_valid_report_types()
    return web.json_response({'valid': valid_types, 'default': default_type})

async def generate_report(request):
    global filerouter
    job_id = request.match_info['job_id']
    report_type = request.match_info['report_type']
    if report_type in get_valid_report_types():
        job_input = await filerouter.job_run_path(request, job_id)
        cmd_args = ['cravat', job_input]
        cmd_args.append('--str')
        cmd_args.extend(['-t', report_type])
        p = subprocess.Popen(cmd_args)
        p.wait()
    return web.Response()

async def download_report(request):
    global filerouter
    job_id = request.match_info['job_id']
    report_type = request.match_info['report_type']
    report_path = await filerouter.job_report(request, job_id, report_type) 
    report_name = job_id+'.'+report_path.split('.')[-1]
    headers = {'Content-Disposition':'attachment; filename='+report_name}
    return web.FileResponse(report_path, headers=headers)

def get_jobs_dir (request):
    jobs_dir = au.get_jobs_dir()
    return web.json_response(jobs_dir)

def set_jobs_dir (request):
    queries = request.rel_url.query
    d = queries['jobsdir']
    au.set_jobs_dir(d)
    return web.json_response(d)

async def get_system_conf_info (request):
    info = au.get_system_conf_info(json=True)
    global filerouter
    return web.json_response(info)

async def update_system_conf (request):
    queries = request.rel_url.query
    sysconf = json.loads(queries['sysconf'])
    try:
        success = au.update_system_conf_file(sysconf)
        if 'modules_dir' in sysconf:
            modules_dir = sysconf['modules_dir']
            cravat_yml_path = os.path.join(modules_dir, 'cravat.yml')
            if os.path.exists(cravat_yml_path) == False:
                au.set_modules_dir(modules_dir)
    except:
        raise
        sysconf = {}
        success = False
    return web.json_response({'success': success, 'sysconf': sysconf})

def reset_system_conf (request):
    d = au.read_system_conf_template()
    md = au.get_modules_dir()
    jobs_dir = au.get_jobs_dir()
    d['modules_dir'] = md
    d['jobs_dir'] = jobs_dir
    au.write_system_conf_file(d)
    return web.json_response({'status':'success', 'dict':yaml.dump(d)})

async def create_user_dir (request, username):
    global filerouter
    jobs_dir = await filerouter.get_jobs_dir(request)
    if os.path.exists(jobs_dir) == False:
        os.mkdir(jobs_dir)

async def signup (request):
    #session = await new_session(request)
    queries = request.rel_url.query
    username = queries['username']
    password = queries['password']
    m = hashlib.sha256()
    m.update(password.encode('utf-16be'))
    passwordhash = m.hexdigest()
    question = queries['question']
    answer = queries['answer']
    m = hashlib.sha256()
    m.update(answer.encode('utf-16be'))
    answerhash = m.hexdigest()
    root_jobs_dir = au.get_jobs_dir()
    admin_db_path = os.path.join(root_jobs_dir, 'admin.sqlite')
    db = await aiosqlite3.connect(admin_db_path)
    cursor = await db.cursor()
    await cursor.execute('select * from users where email="{}"'.format(username))
    r = await cursor.fetchone()
    if r is not None:
        return web.json_response('already registered')
    await cursor.execute('insert into users values ("{}", "{}", "{}", "{}")'.format(username, passwordhash, question, answerhash))
    await db.commit()
    await cursor.close()
    await db.close()
    '''
    session['username'] = username
    session['logged'] = True
    '''
    await create_user_dir(request, username)
    return web.json_response('success')

async def login (request):
    #session = await new_session(request)
    queries = request.rel_url.query
    username = queries['username']
    password = queries['password']
    m = hashlib.sha256()
    m.update(password.encode('utf-16be'))
    passwordhash = m.hexdigest()
    root_jobs_dir = au.get_jobs_dir()
    admin_db_path = os.path.join(root_jobs_dir, 'admin.sqlite')
    db = await aiosqlite3.connect(admin_db_path)
    cursor = await db.cursor()
    await cursor.execute('select * from users where email="{}" and passwordhash="{}"'.format(username, passwordhash))
    r = await cursor.fetchone()
    if r is not None:
        response = 'success'
        '''
        session['username'] = username
        session['logged'] = True
        '''
        await create_user_dir(request, username)
    else:
        response = 'fail'
    await cursor.close()
    await db.close()
    return web.json_response(response)

async def get_password_question (request):
    #session = await get_session(request)
    queries = request.rel_url.query
    email = queries['email']
    root_jobs_dir = au.get_jobs_dir()
    admin_db_path = os.path.join(root_jobs_dir, 'admin.sqlite')
    db = await aiosqlite3.connect(admin_db_path)
    cursor = await db.cursor()
    await cursor.execute('select question from users where email="{}"'.format(email))
    r = await cursor.fetchone()
    if r is None:
        return web.json_response({'status':'fail', 'msg':'No such email'})
    answer = r[0]
    await cursor.close()
    await db.close()
    return web.json_response({'status':'success', 'msg':answer})

async def check_password_answer (request):
    #session = await get_session(request)
    queries = request.rel_url.query
    email = queries['email']
    answer = queries['answer']
    m = hashlib.sha256()
    m.update(answer.encode('utf-16be'))
    answerhash = m.hexdigest()
    root_jobs_dir = au.get_jobs_dir()
    admin_db_path = os.path.join(root_jobs_dir, 'admin.sqlite')
    db = await aiosqlite3.connect(admin_db_path)
    cursor = await db.cursor()
    await cursor.execute('select * from users where email="{}" and answerhash="{}"'.format(email, answerhash))
    r = await cursor.fetchone()
    if r is not None:
        temppassword = 'open_cravat_temp_password'
        m = hashlib.sha256()
        m.update(temppassword.encode('utf-16be'))
        temppasswordhash = m.hexdigest()
        await cursor.execute('update users set passwordhash="{}" where email="{}"'.format(temppasswordhash, email))
        await db.commit()
        await cursor.close()
        await db.close()
        return web.json_response({'success': True, 'msg': temppassword})
    else:
        await cursor.close()
        await db.close()
        return web.json_response({'success': False, 'msg': 'Wrong answer'})

async def change_password (request):
    '''
    session = await get_session(request)
    email = session['username']
    '''
    email = 'default'
    root_jobs_dir = au.get_jobs_dir()
    admin_db_path = os.path.join(root_jobs_dir, 'admin.sqlite')
    db = await aiosqlite3.connect(admin_db_path)
    cursor = await db.cursor()
    queries = request.rel_url.query
    oldpassword = queries['oldpassword']
    newpassword = queries['newpassword']
    m = hashlib.sha256()
    m.update(oldpassword.encode('utf-16be'))
    oldpasswordhash = m.hexdigest()
    await cursor.execute('select * from users where email="{}" and passwordhash="{}"'.format(email, oldpasswordhash))
    r = await cursor.fetchone()
    if r is None:
        await cursor.close()
        await db.close()
        return web.json_response('User authentication failed.')
    else:
        m = hashlib.sha256()
        m.update(newpassword.encode('utf-16be'))
        newpasswordhash = m.hexdigest()
        await cursor.execute('update users set passwordhash="{}" where email="{}"'.format(newpasswordhash, email))
        await db.commit()
        await cursor.close()
        await db.close()
        return web.json_response('success')

async def check_logged (request):
    '''
    session = await get_session(request)
    username = session['username']
    logged = session['logged']
    '''
    username = 'default'
    logged = False
    if logged:
        return web.json_response({'logged': True, 'email': username})
    else:
        return web.json_response({'logged': False, 'email': ''})

async def logout (request):
    '''
    session = await new_session(request)
    session['username'] = None
    '''
    return web.json_response('success')
    '''
    username = session['username']
    root_jobs_dir = au.get_jobs_dir()
    admin_db_path = os.path.join(root_jobs_dir, 'admin.sqlite')
    db = await aiosqlite3.connect(admin_db_path)
    cursor = await db.cursor()
    await cursor.execute('select * from users where email="{}" and passwordhash="{}"'.format(username, passwordhash))
    r = await cursor.fetchone()
    if r is not None:
        response = 'success'
        session['username'] = username
        session['logged'] = True
        await create_user_dir(request, username)
    else:
        response = 'fail'
    await cursor.close()
    await db.close()
    return web.json_response(response)
    '''

def get_servermode (request):
    servermode=False
    return web.json_response({'servermode': servermode})

async def get_package_versions(request):
    cur_ver = au.get_current_package_version()
    lat_ver = au.get_latest_package_version()
    update = LooseVersion(lat_ver) > LooseVersion(cur_ver)
    d = {
        'current': cur_ver,
        'latest': lat_ver,
        'update': update
    }
    return web.json_response(d)

def open_terminal (request):
    filedir = os.path.dirname(os.path.abspath(__file__))
    python_dir = os.path.dirname(sys.executable)
    p = sys.platform
    if p.startswith('win'):
        cmd = {'cmd': ['start', 'cmd'], 'shell': True}
    elif p.startswith('darwin'):
        cmd = {'cmd': '''
osascript -e 'tell app "Terminal"
do script "export PATH=''' + python_dir + ''':$PATH"
do script "echo Welcome to OpenCRAVAT" in window 1
end tell'
''', 'shell': True}
    elif p.startswith('linux'):
        p2 = platform.platform()
        if p2.startswith('Linux') and 'Microsoft' in p2:
            cmd = {'cmd': ['ubuntu1804.exe'], 'shell': True}
        else:
            return
    else:
        return
    subprocess.call(cmd['cmd'], shell=cmd['shell'])
    response = 'done'
    return web.json_response(response)

class JobTracker (object):

    def __init__(self):
        self._jobs = {}

    def add_job(self, id, proc):
        # Add a job to tracking
        self._jobs[id] = proc

    def get_process(self, id):
        # Return the process for a job
        return self._jobs.get(id)

    async def cancel_job(self, id):
        p = self._jobs.get(id)
        if p:
            if platform.platform().lower().startswith('windows'):
                # proc.kill() doesn't work well on windows
                subprocess.Popen("TASKKILL /F /PID {pid} /T".format(pid=p.pid),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                while True:
                    await asyncio.sleep(0.25)
                    if p.poll() is not None:
                        break
            else:
                p.kill()

    def clean_jobs(self, id):
        # Clean up completed jobs
        to_del = []
        for id, p in self._jobs.items():
            if p.poll() is not None:
                to_del.append(id)
        for id in to_del:
            del self._jobs[id]
    
    def list_jobs(self):
        # List currently tracked jobs
        return list(self._jobs.keys())

job_tracker = JobTracker()

def get_last_assembly (request):
    last_assembly = au.get_last_assembly()
    return web.json_response(last_assembly)

filerouter = FileRouter()
VIEW_PROCESS = None

routes = []
routes.append(['POST','/submit/submit',submit])
routes.append(['GET','/submit/annotators',get_annotators])
routes.append(['GET','/submit/jobs',get_all_jobs])
routes.append(['GET','/submit/jobs/{job_id}',view_job])
routes.append(['DELETE','/submit/jobs/{job_id}',delete_job])
routes.append(['GET','/submit/jobs/{job_id}/db', download_db])
routes.append(['GET','/submit/reports',get_report_types])
routes.append(['POST','/submit/jobs/{job_id}/reports/{report_type}',generate_report])
routes.append(['GET','/submit/jobs/{job_id}/reports/{report_type}',download_report])
routes.append(['GET','/submit/jobs/{job_id}/log',get_job_log])
routes.append(['GET', '/submit/getjobsdir', get_jobs_dir])
routes.append(['GET', '/submit/setjobsdir', set_jobs_dir])
routes.append(['GET', '/submit/getsystemconfinfo', get_system_conf_info])
routes.append(['GET', '/submit/updatesystemconf', update_system_conf])
routes.append(['GET', '/submit/resetsystemconf', reset_system_conf])
routes.append(['GET', '/submit/login', login])
routes.append(['GET', '/submit/servermode', get_servermode])
routes.append(['GET', '/submit/signup', signup])
routes.append(['GET', '/submit/logout', logout])
routes.append(['GET', '/submit/passwordquestion', get_password_question])
routes.append(['GET', '/submit/passwordanswer', check_password_answer])
routes.append(['GET', '/submit/changepassword', change_password])
routes.append(['GET', '/submit/checklogged', check_logged])
routes.append(['GET', '/submit/packageversions', get_package_versions])
routes.append(['GET', '/submit/openterminal', open_terminal])
routes.append(['GET', '/submit/lastassembly', get_last_assembly])
routes.append(['GET', '/submit/getjobs', get_jobs])

if __name__ == '__main__':
    app = web.Application()
    for route in routes:
        method, path, func_name = route
        app.router.add_route(method, path, func_name)
    web.run_app(app, port=8060)
