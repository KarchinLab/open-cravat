import os
import json
import sys
import sqlite3
import requests
import fnmatch
from cravat import admin_util as au
from cravat import constants
from datetime import datetime, timezone
import psutil
import platform
import socket
import uuid    
import re

class cravatMetrics:

    def __init__(self):
        self.machinedata = {}
        self.jobdata = {}
        self.jobmodules = {}
        self.jobmapper = {}
        self.jobconverter = {}
        self.jobaggregator = {}
        self.jobannotators = []
        self.jobpostaggregators = []
        self.gather_machine_data()

    def gather_machine_data(self):
        sys_conf = au.get_system_conf()
        self.machinedata['userEmail'] = sys_conf.get(constants.user_email_key)
        self.machinedata['userEmailOptOut'] = sys_conf.get(constants.user_email_opt_out_key)
        self.machinedata['OS'] = platform.system()
        self.machinedata['OSVersion'] = platform.release()
        self.machinedata['totalMemory'] = psutil.virtual_memory().total
        self.machinedata['availableMemory'] = psutil.virtual_memory().available
        self.machinedata['freeMemory'] = psutil.virtual_memory().free
        self.machinedata['amountRAM'] = psutil.virtual_memory().total
        self.machinedata['swapMemory'] = psutil.swap_memory().total
        self.machinedata['numCPU'] = os.cpu_count()
        partitions = psutil.disk_partitions()
        if len(partitions) > 0:
            self.machinedata['fileSystem'] = psutil.disk_partitions()[0].fstype
        else:
            self.machinedata['fileSystem'] = 'unknown'
        self.machinedata['machineId'] = hex(uuid.getnode())
        self.machinedata['pythonVersion'] = platform.python_version()

    def set_job_data(self,param,value):
        self.jobdata[param] = value

    def set_job_converter(self,param,value):
        self.jobconverter[param] = value
    
    def set_job_mapper(self,param,value):
        self.jobmapper[param] = value
    
    def set_job_aggregator(self,param,value):
        self.jobaggregator[param] = value
        
    def set_job_post_aggregator(self,value):
        self.jobpostaggregators.append(value)
    
    def set_job_annotator(self,value):
        self.jobannotators.append(value)
    
    def build_job_metrics_json(self):
        jsoncontent = {}
        jobmodules = {}
        jobmodules['mapper'] = self.jobmapper
        jobmodules['converter'] = self.jobconverter
        jobmodules['annotators'] = self.jobannotators
        jobmodules['aggregator'] = self.jobaggregator
        jobmodules['postaggregators'] = self.jobpostaggregators
        jobmodules['annotators'] = self.jobannotators
        self.jobdata['modules'] = jobmodules
        jsoncontent['jobData'] = self.jobdata
        jsoncontent['machineData'] = self.machinedata
        json_dump = json.dumps(jsoncontent, indent = 4)
        return json_dump

    def build_opt_metrics_json(self):
        jsoncontent = {}
        dt = datetime.now(timezone.utc)
        utc_time = dt.replace(tzinfo=timezone.utc)    
        dt_string = utc_time.strftime("%Y/%m/%d %H:%M:%S")
        jsoncontent['machineData'] = self.machinedata
        jsoncontent['currDate'] = dt_string
        json_dump = json.dumps(jsoncontent, indent = 4)
        return json_dump

    def do_opt_out(self):
        json_dump = self.build_opt_metrics_json()
        self.post_opt_metrics(json_dump)
        
    #post metrics from current execution AND any previous failed executions to the metrics server    
    def post_opt_metrics(self,json_dump):
        json_obj = json.loads(json_dump)
        sys_conf = au.get_system_conf()
        metrics_url = sys_conf[constants.metrics_url_key] + "/opt"
        try:
            requests.post(metrics_url, json=json_obj)  #write json to a file (hardcoded dir)
        except Exception as e: 
            return False
        return True

    def do_job_metrics(self,cc):
        dbpath = os.path.join(cc.output_dir, cc.run_name + ".sqlite")
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        json_dump = self.build_job_metrics_json()
        # save the run success value to the info table
        q = 'insert or replace into info values ("runsuccess", "'+ self.jobdata['success']+'")'
        cursor.execute(q)
        # save the runtime value to the info table
        q = (
            'insert or replace into info values ("runtime", "'
            +  str(self.jobdata['jobRuntime'])
            + '")'
        )
        cursor.execute(q)
        conn.commit()
        self.post_job_metrics(json_dump,True)
        
    #post metrics from current execution AND any previous failed executions to the metrics server    
    def post_job_metrics(self,json_dump,is_new):
        json_obj = json.loads(json_dump)
        sys_conf = au.get_system_conf()
        saveMetrics = sys_conf[constants.save_metrics_key]
        if saveMetrics == True:
            metrics_url = sys_conf[constants.metrics_url_key] + "/job"
            try:
#                raise requests.exceptions.Timeout("Connection Timed Out") #use to simulate timeout
                r = requests.post(metrics_url, json=json_obj)  #write json to a file (hardcoded dir)
                if r.status_code == 200:
                    if is_new:
                        self.resend_local_metrics()
                else:
                    if is_new:
                        self.save_metrics_local(json_obj)
                    return False
            except Exception as e: 
                if is_new: 
                    self.save_metrics_local(json_obj)
                return False
        return True
    
    #perform temporary save to user local metrics directory    
    def save_metrics_local(self,json_obj):
        now = datetime.now()    
        timestamp = str(datetime.timestamp(now)).replace(".","")
        sys_conf = au.get_system_conf()
        metricsPath = sys_conf[constants.metrics_dir_key]
        outFileName= os.path.join(metricsPath, f'ocmetric_{timestamp}.json')
        outFile=open(outFileName, "w")
        outFile.write(json.dumps(json_obj))
        outFile.close()
    
     #resend any saved local metrics files.    
    def resend_local_metrics(self):
        sys_conf = au.get_system_conf()
        metricsPath = sys_conf[constants.metrics_dir_key]
        if os.path.exists(metricsPath):
             for filename in os.listdir(metricsPath):
                with open(os.path.join(metricsPath, filename)) as f:
                    json_dump = f.read()
                    successful = self.post_job_metrics(json_dump,False)
                    f.close()
                    if successful == True:
                        os.remove(os.path.join(metricsPath, filename))
                    else:
                        break

