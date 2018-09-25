import os
import time
import datetime
import subprocess
import yaml
import json
from cravat import admin_util as au
from cravat import ConfigLoader
import sys
import traceback
import shutil
from aiohttp import web

class FileRouter(object):

    def __init__(self):
        self.root = os.path.dirname(__file__)
        self.input_fname = 'input'
        self.report_extensions = {
            'text':'.tsv',
            'excel':'.xlsx'
        }
        self.db_extension = '.sqlite'
        self.update_jobs_dir()

    def update_jobs_dir (self):
        self._jobs_dir = au.get_jobs_dir()

    def static_dir(self):
        return os.path.join(self.root, 'static')

    def jobs_dir(self):
        return self._jobs_dir

    def job_dir(self, job_id):
        return os.path.join(self.jobs_dir(), job_id)

    def job_info_file(self, job_id):
        info_fname = '{}.info.yaml'.format(job_id)
        return os.path.join(self.job_dir(job_id), info_fname)

    def job_input(self, job_id):
        return os.path.join(self.job_dir(job_id), self.input_fname)

    def job_db(self, job_id):
        output_fname = self.input_fname+self.db_extension
        return os.path.join(self.job_dir(job_id), output_fname)

    def job_report(self, job_id, report_type):
        ext = self.report_extensions.get(report_type, '.'+report_type)
        report_fname = self.input_fname+ext
        return os.path.join(self.job_dir(job_id), report_fname)

    def job_status_file(self, job_id):
        status_fname = 'input.status.json'
        return os.path.join(self.job_dir(job_id), status_fname)

class WebJob(object):
    def __init__(self, job_dir, job_info_fpath):
        self.info = {}
        self.job_dir = job_dir
        self.job_info_fpath = job_info_fpath
        self.info['id'] = os.path.basename(job_dir)

    def save_job_options (self, job_options):
        self.set_values(**job_options)

    def read_info_file(self):
        with open(self.job_info_fpath) as f:
            info_dict = yaml.load(f)
        if info_dict != None:
            self.set_values(**info_dict)

    def set_info_values(self, **kwargs):
        self.set_values(**kwargs)

    def write_info_file(self):
        with open(self.job_info_fpath,'w') as wf:
            yaml.dump(self.get_info_dict(), wf, default_flow_style=False)

    def get_info_dict(self):
        return self.info

    def set_values(self, **kwargs):
        self.info.update(kwargs)
        '''
        self.orig_input_fname = self.info['orig_input_fname']
        self.submission_time = self.info['submission_time']
        self.id = self.info['id']
        self.viewable = self.info.get('viewable', False)
        self.reports = self.info.get('reports',[])
        self.db_path = self.info.get('db_path')
        self.annotators = self.info.get('job_options');
        '''

def get_next_job_id():
    return datetime.datetime.now().strftime(r'CJ-%Y%m%d-%H%M%S')

async def submit (request):
    global FILE_ROUTER
    reader = await request.multipart()
    input_file = None
    job_options = None
    while True:
        part = await reader.next()
        if not part: break 
        if part.name == 'file':
            input_file = part
            input_data = await input_file.read()
        elif part.name == 'options':
            job_options = await part.json()
        if input_file is not None and job_options is not None: 
            break
    orig_input_fname = input_file.filename
    job_id = get_next_job_id()
    job_dir = FILE_ROUTER.job_dir(job_id)
    job_info_fpath = FILE_ROUTER.job_info_file(job_id)
    os.makedirs(job_dir, exist_ok=True)
    job = WebJob(job_dir, job_info_fpath)
    job.save_job_options(job_options)
    input_fpath = os.path.join(job_dir, FILE_ROUTER.job_input(job_id))
    with open(input_fpath, 'wb') as wf:
        wf.write(input_data)
    job.set_info_values(orig_input_fname=orig_input_fname,
                        submission_time=datetime.datetime.now().isoformat(),
                        viewable=False
                        )
    # Subprocess arguments
    run_args = ['cravat',
                input_fpath]
    # Annotators
    if len(job_options['annotators']) > 0:
        run_args.append('-a')
        run_args.extend(job_options['annotators'])
    else:
        run_args.append('--sa')
    # Liftover assembly
    run_args.append('-l')
    run_args.append(job_options['assembly'])
    # Reports
    if len(job_options['reports']) > 0:
        run_args.append('-t')
        run_args.extend(job_options['reports'])
    else:
        run_args.append('--sr')
    print('Run command: \''+' '.join(run_args)+'\'')
    p = subprocess.Popen(run_args)
    # p.wait()
    status_file = FILE_ROUTER.job_status_file(job_id)
    status_d = {'status': 'Submitted'}
    job.set_info_values(status=status_d)
    job.write_info_file()
    return web.json_response(job.get_info_dict())

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

def get_all_jobs (request):
    global FILE_ROUTER
    ids = os.listdir(FILE_ROUTER.jobs_dir())
    ids.sort(reverse=True)
    all_jobs = []
    for job_id in ids:
        try:
            job_dir = FILE_ROUTER.job_dir(job_id)
            if os.path.isdir(job_dir) == False:
                continue
            job_info_fpath = FILE_ROUTER.job_info_file(job_id)
            if os.path.exists(job_info_fpath) == False:
                continue
            job = WebJob(job_dir, job_info_fpath)
            job.read_info_file()
            db_path = FILE_ROUTER.job_db(job_id)
            job_viewable = os.path.exists(db_path)
            status_file = FILE_ROUTER.job_status_file(job_id)
            try:
                with open(status_file) as f: status_d = json.load(f)
            except IOError:
                status_d = {'status':'Submitted'}
            job.set_info_values(viewable=job_viewable,
                                db_path=db_path,
                                status=status_d,
                                )
            existing_reports = []
            for report_type in get_valid_report_types():
                report_file = FILE_ROUTER.job_report(job_id, report_type)
                if os.path.exists(report_file):
                    existing_reports.append(report_type)
            job.set_info_values(reports=existing_reports)
            all_jobs.append(job)
        except:
            traceback.print_exc()
            continue
    return web.json_response([job.get_info_dict() for job in all_jobs])

def view_job(request):
    global VIEW_PROCESS
    global FILE_ROUTER
    job_id = request.match_info['job_id']
    db_path = FILE_ROUTER.job_db(job_id)
    if os.path.exists(db_path):
        if type(VIEW_PROCESS) == subprocess.Popen:
            VIEW_PROCESS.kill()
        VIEW_PROCESS = subprocess.Popen(['cravat-view', db_path])
        return web.Response()
    else:
        return web.Response(status=404)

def delete_job(request):
    global FILE_ROUTER
    job_id = request.match_info['job_id']
    job_dir = FILE_ROUTER.job_dir(job_id)
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
        return web.Response()
    else:
        return web.Response(status=404)

def download_db(request):
    global FILE_ROUTER
    job_id = request.match_info['job_id']
    db_path = FILE_ROUTER.job_db(job_id)
    db_fname = job_id+'.sqlite'
    with open(db_path) as f:
        headers = {'Content-Disposition': 'attachment; filename='+db_fname}
        return web.Response(body=db_path, headers=headers)

def download_excel (request):
    global FILE_ROUTER
    job_id = request.match_info['job_id']
    db_path = FILE_ROUTER.job_db(job_id)
    db_fname = job_id+'.xlsx'
    with open(db_path) as f:
        headers = {'Content-Disposition': 'attachment; filename='+db_fname}
        return web.Response(body=db_path, headers=headers)

def download_text (request):
    global FILE_ROUTER
    job_id = request.match_info['job_id']
    db_path = FILE_ROUTER.job_db(job_id)
    db_fname = job_id+'.tsv'
    with open(db_path) as f:
        headers = {'Content-Disposition': 'attachment; filename='+db_fname}
        return web.Response(body=db_path, headers=headers)

def get_valid_report_types():
    reporter_infos = au.get_local_module_infos(types=['reporter'])
    report_types = [x.name.split('reporter')[0] for x in reporter_infos]
    return report_types

def get_report_types(request):
    cfl = ConfigLoader()
    default_reporter = cfl.get_cravat_conf_value('reporter')
    default_type = default_reporter.split('reporter')[0]
    valid_types = get_valid_report_types()
    return web.json_response({'valid': valid_types, 'default': default_type})

def generate_report(request):
    global FILE_ROUTER
    job_id = request.match_info['job_id']
    report_type = request.match_info['report_type']
    if report_type in get_valid_report_types():
        cmd_args = ['cravat', FILE_ROUTER.job_input(job_id)]
        cmd_args.append('--str')
        cmd_args.extend(['-t', report_type])
        p = subprocess.Popen(cmd_args)
        p.wait()
    return web.Response()

def download_report(request):
    global FILE_ROUTER
    job_id = request.match_info['job_id']
    report_type = request.match_info['report_type']
    report_path = FILE_ROUTER.job_report(job_id, report_type) 
    report_name = job_id+'.'+report_path.split('.')[-1]
    with open(report_path,'rb') as f:
        headers = {
            'Content-Disposition':'attachment; filename='+report_name,
        }
        return web.Response(body=f.read(), headers=headers)

def get_jobs_dir (request):
    jobs_dir = au.get_jobs_dir()
    return web.json_response(jobs_dir)

def set_jobs_dir (request):
    queries = request.rel_url.query
    d = queries['jobsdir']
    au.set_jobs_dir(d)
    FILE_ROUTER.update_jobs_dir()
    return web.json_response(d)

FILE_ROUTER = FileRouter()
VIEW_PROCESS = None

routes = []
routes.append(['GET','/submit/jobs/{job_id}/reports/{report_type}',download_report])
routes.append(['POST','/submit/submit',submit])
routes.append(['GET','/submit/annotators',get_annotators])
routes.append(['GET','/submit/jobs',get_all_jobs])
routes.append(['GET','/submit/jobs/{job_id}',view_job])
routes.append(['DELETE','/submit/jobs/{job_id}',delete_job])
routes.append(['GET','/submit/jobs/{job_id}/db', download_db])
routes.append(['GET','/submit/jobs/{job_id}/excel', download_excel])
routes.append(['GET','/submit/jobs/{job_id}/text', download_text])
routes.append(['GET','/submit/reports',get_report_types])
routes.append(['POST','/submit/jobs/{job_id}/reports/{report_type}',generate_report])
routes.append(['GET', '/submit/getjobsdir', get_jobs_dir])
routes.append(['GET', '/submit/setjobsdir', set_jobs_dir])

if __name__ == '__main__':
    app = web.Application()
    for route in routes:
        method, path, func_name = route
        app.router.add_route(method, path, func_name)
    web.run_app(app, port=8060)
