import os
import json
import sys
import sqlite3
import requests
import fnmatch
from cravat import admin_util as au
from datetime import datetime
import psutil
import platform
import socket
import uuid    

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
        self.machinedata['OS'] = platform.system()
        self.machinedata['OSVersion'] = platform.release()
        self.machinedata['totalMemory'] = psutil.virtual_memory().total
        self.machinedata['availableMemory'] = psutil.virtual_memory().available
        self.machinedata['freeMemory'] = psutil.virtual_memory().free
        self.machinedata['amountRAM'] = psutil.virtual_memory().total
        self.machinedata['swapMemory'] = psutil.swap_memory().total
        self.machinedata['numCPU'] = len(psutil.Process().cpu_affinity())
        self.machinedata['fileSystem'] = psutil.disk_partitions()[0].fstype
        self.machinedata['machineId'] = str(uuid.UUID(int=uuid.getnode()))
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
    
    def build_metrics_json(self):
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
#        print("metrics2: " + json_dump)
        return json_dump

    def do_job_metrics(self,cc):
        dbpath = os.path.join(cc.output_dir, cc.run_name + ".sqlite")
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        json_dump = self.build_metrics_json()
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
    #    print(json_dump)
        conn.commit()
        self.post_metrics(json_dump,True)
        
    #post metrics from current execution AND any previous failed executions to the metrics server    
    def post_metrics(self,json_dump,is_new):
        json_obj = json.loads(json_dump)
        sys_conf = au.get_system_conf()
        saveMetrics = sys_conf["save_metrics"]
        if saveMetrics == True:
            metrics_url = sys_conf["metrics_url"] + "/job"
            try:
#                raise requests.exceptions.Timeout("Connection Timed Out") #use to simulate timeout
                requests.post(metrics_url, json=json_obj)  #write json to a file (hardcoded dir)
                if is_new:
                    self.resend_local_metrics()
            except Exception as e: 
                if is_new: 
                    self.save_metrics_local(json_obj)
                return False
        return True
    
    #perform temporary save to user local metrics directory    
    def save_metrics_local(self,json_obj):
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
    def resend_local_metrics(self):
        metricsPath = os.getcwd() +"\\metrics"
        if os.path.exists(metricsPath):
             for filename in os.listdir(metricsPath):
                with open(os.path.join(metricsPath, filename)) as f:
                    json_dump = f.read()
                    successful = self.post_metrics(json_dump,False)
                    f.close()
                    if successful == True:
                        os.remove(metricsPath+"\\"+filename)
                    else:
                        break;

