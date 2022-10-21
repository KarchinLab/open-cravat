import os
import json
import sys
import sqlite3
import requests
import fnmatch
from cravat import admin_util as au
from datetime import datetime

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
#    json_obj = json.loads(json_dump)
#    print(json_dump)
    post_metrics(json_dump,True)
    
#post metrics from current execution AND any previous failed executions to the metrics server    
def post_metrics(json_dump,is_new):
    json_obj = json.loads(json_dump)
    sys_conf = au.get_system_conf()
    metrics_url = sys_conf["metrics_url"] + "/job"
    try:
#        raise requests.exceptions.Timeout("Connection Timed Out") #use to simulate timeout
        requests.post(metrics_url, json=json_obj)  #write json to a file (hardcoded dir)
        if is_new:
            resend_local_metrics()
    except Exception as e: 
        if is_new: 
            save_metrics_local(json_obj)
        return False
    return True

#perform temporary save to user local metrics directory    
def save_metrics_local(json_obj):
    homeDir = os.getcwd()
    metricsPath = os.getcwd() +"\\metrics"
    now = datetime.now()    
    timestamp = str(datetime.timestamp(now)).replace(".","")
    if not os.path.exists(metricsPath):
        os.mkdir(metricsPath)
    outFileName= metricsPath +"\\ocmetric_"+timestamp
    outFile=open(outFileName, "w")
    outFile.write(json.dumps(json_obj))
    outFile.close()

 #resend any saved local metrics files.    
def resend_local_metrics():
    homeDir = os.getcwd()
    print("HOMEDIR: ") + homeDir
    metricsPath = os.getcwd() +"\\metrics"
    if os.path.exists(metricsPath):
         for filename in os.listdir(metricsPath):
            with open(os.path.join(metricsPath, filename)) as f:
                json_dump = f.read()
                successful = post_metrics(json_dump,False)
                f.close()
                if successful == True:
                    os.remove(metricsPath+"\\"+filename)
                else:
                    break;

       