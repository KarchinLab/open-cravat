from bottle import app, route, get, post, request, response, run, static_file
import os
import time
import datetime
import subprocess
import yaml
import json
import cravat
import sys
import traceback

class FileRouter(object):

    def __init__(self):
        self.root = os.path.dirname(__file__)

    def static_dir(self):
        return os.path.join(self.root, 'static')

    def jobs_dir(self):
        return os.path.join('C:\\','Users','Kyle','a','cravat-jobs','websubmitter')

    def job_dir(self, job_id):
        return os.path.join(self.jobs_dir(), job_id)

    def job_info_file(self, job_id):
        info_fname = '{}.info.yaml'.format(job_id)
        return os.path.join(self.job_dir(job_id), info_fname)

    def job_input_file(self, job_id):
        input_fname = 'input'
        return os.path.join(self.job_dir(job_id), input_fname)

    def job_output_db(self, job_id):
        output_fname = 'input.sqlite'
        return os.path.join(self.job_dir(job_id), output_fname)

class WebJob(object):
    def __init__(self, job_dir, job_info_fpath):
        self.job_dir = job_dir
        self.job_info_fpath = job_info_fpath
        self.info = JobInfo(id=os.path.basename(job_dir))

    def read_info_file(self):
        with open(self.job_info_fpath) as f:
            info_dict = yaml.load(f)
        self.info.set_values(**info_dict)

    def set_info_values(self, **kwargs):
        self.info.set_values(**kwargs)

    def write_info_file(self):
        with open(self.job_info_fpath,'w') as wf:
            yaml.dump(self.get_info_dict(), wf, default_flow_style=False)

    def get_info_dict(self):
        return vars(self.info)

class JobInfo(object):

    def __init__(self, **kwargs):
        self.set_values(**kwargs)
        
    def set_values(self, **kwargs):
        all_vars = vars(self)
        all_vars.update(kwargs)
        self.orig_input_fname = all_vars.get('orig_input_fname')
        self.submission_time = all_vars.get('submission_time')
        self.id = all_vars.get('id')
        self.viewable = all_vars.get('viewable')

FILE_ROUTER = FileRouter()
VIEW_PROCESS = None

def get_next_job_id():
    return datetime.datetime.now().strftime(r'job-%Y-%m-%d-%H-%M-%S')

@post('/rest/submit')
def submit():
    global FILE_ROUTER
    file_formpart = request.files.get('file')
    orig_input_fname = file_formpart.raw_filename
    job_id = get_next_job_id()
    job_dir = FILE_ROUTER.job_dir(job_id)
    job_info_fpath = FILE_ROUTER.job_info_file(job_id)
    os.mkdir(job_dir)
    job = WebJob(job_dir, job_info_fpath)
    input_fpath = os.path.join(job_dir, FILE_ROUTER.job_input_file(job_id))
    with open(input_fpath,'wb') as wf:
        wf.write(file_formpart.file.read())
    job.set_info_values(orig_input_fname=orig_input_fname,
                        submission_time=datetime.datetime.now().isoformat(),
                        viewable=False)
    job_options = json.loads(request.forms.get('options'))
    run_args = ['cravat',
                input_fpath]
    if len(job_options['annotators'] > 0):
        run_args.append('-a')
        for annot_name in job_options['annotators']:
            run_args.append(annot_name)
    else:
        run_args.append('--sa')
    run_args.append('-l')
    run_args.append(job_options['assembly'])
    subprocess.Popen(run_args)
    job.write_info_file()
    return job.get_info_dict()

@get('/rest/annotators')
def get_annotators():
    module_names = cravat.admin_util.list_local()
    out = {}
    for module_name in module_names:
        local_info = cravat.admin_util.get_local_module_info(module_name)
        if local_info.type == 'annotator':
            out[module_name] = {
                                'name':module_name,
                                'version':local_info.version,
                                'type':local_info.type,
                                'title':local_info.title,
                                'description':local_info.description,
                                'developer':vars(local_info.developer)
                            }
    return out

@get('/rest/jobs')
def get_all_jobs():
    global FILE_ROUTER
    ids = os.listdir(FILE_ROUTER.jobs_dir())
    ids.sort(reverse=True)
    all_jobs = []
    for job_id in ids:
        try:
            job_dir = FILE_ROUTER.job_dir(job_id)
            job_info_fpath = FILE_ROUTER.job_info_file(job_id)
            job = WebJob(job_dir, job_info_fpath)
            job.read_info_file()
            job_viewable = os.path.exists(FILE_ROUTER.job_output_db(job_id))
            job.set_info_values(viewable=job_viewable)
            all_jobs.append(job)
        except:
            traceback.print_exc()
            continue
    response.content_type = 'application/json'
    return json.dumps([job.get_info_dict() for job in all_jobs])

@post('/rest/view')
def view():
    global VIEW_PROCESS
    global FILE_ROUTER
    job_id = request.json['jobId']
    db_path = FILE_ROUTER.job_output_db(job_id)
    if os.path.exists(db_path):
        if type(VIEW_PROCESS) == subprocess.Popen:
            VIEW_PROCESS.kill()
        VIEW_PROCESS = subprocess.Popen(['cravat-view', db_path])
            
@get('/static/<filepath:path>')
def static(filepath):
    return static_file(filepath, root=FILE_ROUTER.static_dir())

if __name__ == '__main__':
    run(host='localhost', port=8080, debug=True)