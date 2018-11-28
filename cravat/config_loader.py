import os
import yaml
import copy
from cravat import admin_util as au

class ConfigLoader():
    
    def __init__(self, job_conf_path = None):
        self.job_conf_path = job_conf_path
        self.main_conf_path = au.get_main_conf_path()
        self._main = {}
        self._job = {}
        self._modules = {}
        self._all = {}
        self._load_main_conf(build_all=False)
        self._load_job_conf(build_all=False)
        self._build_all()
        
    def _load_main_conf(self, build_all=True):
        self._main = {}
        if os.path.exists(self.main_conf_path):
            self._main = au.load_yml_conf(self.main_conf_path)
        if build_all:
            self._build_all()
        
    def _load_job_conf(self, build_all=True):
        self._job = {}
        if self.job_conf_path:
            self._job = au.load_yml_conf(self.job_conf_path)
        if build_all:
            self._build_all()
    
    def _load_module_conf(self, module_name, build_all=True):
        module_info = au.get_local_module_info(module_name)
        self._modules[module_name] = au.load_yml_conf(module_info.conf_path)
        if build_all:
            self._build_all()
            
    def _build_all(self):
        self._all = {}
        if self._modules:
            self._all['modules'] = copy.deepcopy(self._modules)
        if self._main:
            self._all['cravat'] = copy.deepcopy(self._main)
        self._all = au.recursive_update(self._all, self._job)
        
    def save(self, path, modules=[]):
        """
        Save all the config settings to a file.
        A list of modules to include may be passed in. An empty list results
        in all module configs being saved.
        """
        # Load all modules, or only requested modules
        if len(modules) == 0:
            modules = au.list_local()
        for module_name in modules:
            self._load_module_conf(module_name, build_all=False)
        self._build_all()
        # Delete configs for modules in the job conf but not in the modules list
        extra_modules = list(set(self._all['modules']) - set(modules))
        for module_name in extra_modules:
            del self._all['modules'][module_name]
        # Write to a file
        with open(path,'w') as wf:
            wf.write(yaml.dump(self._all, default_flow_style=False))
    
    def has_key (self, key):
        present = key in self._all
        return present
    
    def get_val (self, key):
        if key in self._all:
            val = self._all[key]
        else:
            val = None
        return val
    
    def get_all_conf (self):
        return self._all
    
    def get_module_conf(self, module_name):
        if module_name not in self._modules:
            self._load_module_conf(module_name)
        return self._all['modules'][module_name]
    
    def get_cravat_conf(self):
        return self._all['cravat']
    
    def get_cravat_conf_value (self, key):
        if 'cravat' in self._all:
            if key in self._all['cravat']:
                return self._all['cravat'][key]
            else:
                return None
        else:
            return None
        
    def override_cravat_conf (self, cravat_conf):
        self._all['cravat'] = au.recursive_update(self._all['cravat'],
                                               cravat_conf)
    
    def get_local_module_confs (self):
        return self._all['modules']
