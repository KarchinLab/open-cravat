import os
import json
import sys
import sqlite3
import requests
from cravat import admin_util as au

def get_job_metrics_obj():
    jobcontent = {}
    jobmodules = {}
    jobmapper = {}
    jobconverter = {}
    jobannotators = []
    jobmodules['mapper'] = jobmapper
    jobmodules['converter'] = jobconverter
    jobmodules['annotators'] = jobannotators
    jobcontent['modules'] = jobmodules
    return jobcontent

def do_job_metrics(cc,jobcontent):
    dbpath = os.path.join(cc.output_dir, cc.run_name + ".sqlite")
    conn = sqlite3.connect(dbpath)
    cursor = conn.cursor()
    json_dump = json.dumps(jobcontent, indent = 3)
    # save the run success value to the info table
    q = 'insert or replace into info values ("runsuccess", "'+ jobcontent['success']+'")'
    cursor.execute(q)
    # save the runtime value to the info table
    q = (
        'insert or replace into info values ("runtime", "'
        +  jobcontent['job_runtime']
        + '")'
    )
    cursor.execute(q)
    conn.commit()
    json_obj = json.loads(json_dump)
    post_metrics(json_obj)
    
def post_metrics(json_obj):
    sys_conf = au.get_system_conf()
    metrics_url = sys_conf["metrics_url"] + "/job"
    requests.post(metrics_url, json=json_obj)  #write json to a file (hardcoded dir)
