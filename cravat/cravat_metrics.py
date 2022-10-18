import os
import json
import sys
import sqlite3
import aiosqlite
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

async def do_job_metrics(cc,jobcontent):
    dbpath = os.path.join(cc.output_dir, cc.run_name + ".sqlite")
    conn = await aiosqlite.connect(dbpath)
    cursor = await conn.cursor()
    json_dump = json.dumps(jobcontent, indent = 3)
    print("IN DO METRICS json_dump: " + json_dump)
    q = 'insert or replace into info values ("runsuccess", "'+ jobcontent['success']+'")'
    await cursor.execute(q)
    q = (
        'insert or replace into info values ("runtime", "'
        +  jobcontent['job_runtime']
        + '")'
    )
    await cursor.execute(q)
    await conn.commit()
    json_obj = json.loads(json_dump)
    post_metrics(json_obj)
    
def post_metrics(json_obj):
    sys_conf = au.get_system_conf()
    metrics_url = sys_conf["metrics_url"] + "/job"
    requests.post(metrics_url, json=json_obj)
