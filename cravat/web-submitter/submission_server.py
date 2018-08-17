from bottle import app, route, get, post, request, response, run, static_file
import os
import time
import datetime
import subprocess

class FileRouter(object):
    def __init__(self):
        self.root = os.path.dirname(__file__)
    def static_dir(self):
        return os.path.join(self.root, 'static')
    def jobs_dir(self):
        return os.path.join(self.root, 'jobs')
    def job_dir(self, job_id):
        return os.path.join(self.jobs_dir(), job_id)
FILE_ROUTER = FileRouter()
VIEW_PROCESS = None
RUN_PROCESS = None

def get_next_job_id():
    jobs_dir = FILE_ROUTER.jobs_dir()
    cur_jobs = os.listdir(jobs_dir)
    return str(len(cur_jobs)+1)

@post('/rest/submit')
def submit():
    file_formpart = request.files.get('file')
    input_file = file_formpart.file
    fname = file_formpart.raw_filename
    job_id = get_next_job_id()
    job_dir = os.path.join(FILE_ROUTER.jobs_dir(), job_id)
    os.mkdir(job_dir)
    input_fpath = os.path.join(job_dir, fname)
    with open(input_fpath,'wb') as wf:
        wf.write(input_file.read())
    RUN_PROCESS = subprocess.run(['cravat',input_fpath])
    return job_id

@get('/rest/jobs')
def get_all_job_ids():
    ids = os.listdir(FILE_ROUTER.jobs_dir())
    return {'jobIds':ids}

@post('/rest/view')
def view():
    global VIEW_PROCESS
    global FILE_ROUTER
    reqObj = request.json
    job_id = reqObj['jobId']
    job_dir = FILE_ROUTER.job_dir(job_id)
    db_path = None
    for fname in os.listdir(job_dir):
        if fname.endswith('.sqlite'):
            db_path = os.path.join(job_dir, fname)
            break
    if db_path:
        if type(VIEW_PROCESS) == subprocess.Popen:
            VIEW_PROCESS.kill()
        VIEW_PROCESS = subprocess.Popen(['cravat-view', db_path])
            
    

@get('/hello')
def hello():
    return 'Hi! I\'m the cravat submission server.'

@get('/static/<filepath:path>')
def static(filepath):
    return static_file(filepath, root=FILE_ROUTER.static_dir())

if __name__ == '__main__':
    run(host='localhost', port=8080, debug=True)