import zipfile
import shutil
import os
import sys
import yaml
import copy
import json
from . import constants
from . import store_utils as su
from . import util
import requests
import traceback
import re
from distutils.version import StrictVersion

def load_yml_conf(yml_conf_path):
    """
    Load a .yml file into a dictionary. Return an empty dictionary if file is
    empty.
    """
    with open(yml_conf_path) as f:
        conf = yaml.load(f)
    if conf == None:
        conf = {}
    return conf

def recursive_update(d1, d2):
    """
    Recursively merge two dictionaries and return a copy.
    d1 is merged into d2. Keys in d1 that are not present in d2 are preserved
    at all levels. The default Dict.update() only preserved keys at the top
    level.
    """
    d3 = copy.deepcopy(d1) # Copy perhaps not needed. Test.
    for k, v in d2.items():
        if isinstance(v, dict):
            t = recursive_update(d3.get(k,{}), v)
            d3[k] = t
        else:
            d3[k] = d2[k]
    return d3

class LocalModuleInfo (object):
    def __init__(self, dir_path, name=None):
        self.directory = dir_path
        if name is None:
            self.name = os.path.basename(self.directory)
        else:
            self.name = name
        self.script_path = os.path.join(self.directory, self.name+'.py')
        self.script_exists = os.path.exists(self.script_path)
        self.conf_path = os.path.join(self.directory, self.name+'.yml')
        self.conf_exists = os.path.exists(self.conf_path)
        self.exists = self.conf_exists
        self.data_dir = os.path.join(dir_path, 'data')
        self.data_dir_exists = os.path.isdir(self.data_dir)
        self.has_data = self.data_dir_exists \
                        and len(os.listdir(self.data_dir)) > 0
        self.test_dir = os.path.join(dir_path, 'test')
        self.test_dir_exists = os.path.isdir(self.test_dir)
        self.has_test = self.test_dir_exists \
                        and os.path.isfile(os.path.join(self.test_dir, 'input')) \
                        and  os.path.isfile(os.path.join(self.test_dir, 'key'))
        self.readme_path = os.path.join(self.directory, self.name+'.md')
        self.readme_exists = os.path.exists(self.readme_path)
        if self.readme_exists:
            with open(self.readme_path) as f:
                self.readme = f.read()
        else:
            self.readme = ''
        self.conf = {}
        if self.conf_exists:
            self.conf = load_yml_conf(self.conf_path) # THIS SHOULD NOT BE KEPT HERE, USE CONFIG LOADER
        self.type = self.conf.get('type')
        self.version = self.conf.get('version')
        self.description = self.conf.get('description')
        dev_dict = self.conf.get('developer')
        if not(type(dev_dict)==dict):
            dev_dict = {}
        self.developer = get_developer_dict(**dev_dict)
        if 'type' not in self.conf:
            self.conf['type'] = 'unknown'
        self.type = self.conf['type']
        if 'level' in self.conf:
            self.level = self.conf['level']
        else:
            self.level = None
        if 'input_format' in self.conf:
            self.input_format = self.conf['input_format']
        else:
            self.input_format = None
        if 'secondary_inputs' in self.conf:
            self.secondary_module_names = self.conf['secondary_inputs'].keys()
        else:
            self.secondary_module_names = []
        if self.type == 'annotator':
            if self.level == 'variant':
                self.output_suffix = self.name + '.var'
            elif self.level == 'gene':
                self.output_suffix = self.name + '.gen'
            else:
                self.output_suffix = self. name + '.' + self.type
        if 'title' in self.conf:
            self.title = self.conf['title']
        else:
            self.title = self.name
        self.disk_size = None

    def is_valid_module(self):
        r = self.exists
        r = r and self.name is not None
        r = r and self.conf_path is not None
        r = r and self.version is not None
        r = r and self.type is not None
        return r

    def get_size(self):
        """
        Gets the total installed size of a module
        """
        if self.disk_size is None:
            self.disk_size = util.get_directory_size(self.directory)
        return self.disk_size

    def serialize (self):
        return self.__dict__

class RemoteModuleInfo(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.versions = kwargs.get('versions',[])
        self.latest_version = kwargs.get('latest_version','')
        self.type = kwargs.get('type','')
        self.title = kwargs.get('title','')
        self.description = kwargs.get('description','')
        self.size = kwargs.get('size',0)
        dev_dict = kwargs.get('developer')
        if not(type(dev_dict)==dict):
            dev_dict = {}
        self.developer = get_developer_dict(**dev_dict)

    def has_version(self, version):
        return version in self.versions

def get_developer_dict (**kwargs):
    d = {}
    d['name'] = kwargs.get('name', '')
    d['email'] = kwargs.get('email', '')
    d['organization'] = kwargs.get('organization')
    d['citation'] = kwargs.get('citation', '')
    d['website'] = kwargs.get('website', '')
    return d

class ModuleInfoCache(object):
    def __init__(self):
        self._sys_conf = get_system_conf()
        self._modules_dir = get_modules_dir()
        self.local = {}
        self._remote_url = None
        self.remote = {}
        self._remote_fetched = False
        self.remote_readme = {}
        self.remote_config = {}
        self.update_local()
        self._store_path_builder = su.PathBuilder(self._sys_conf['store_url'],'url')

    def update_local(self):
        self.local = {}
        if not(os.path.exists(self._modules_dir)):
            return
        for mg in os.listdir(self._modules_dir):
            mg_path = os.path.join(self._modules_dir, mg)
            if not(os.path.isdir(mg_path)):
                continue
            for module_name in os.listdir(mg_path):
                module_dir = os.path.join(mg_path, module_name)
                if os.path.isdir(module_dir):
                    local_info = LocalModuleInfo(module_dir)
                    if local_info.is_valid_module():
                        self.local[module_name] = local_info

    def update_remote(self, force=False):
        if force or not(self._remote_fetched):
            self._remote_url = self._store_path_builder.manifest()
            self.remote = {}
            manifest_str = su.get_file_to_string(self._remote_url)
            if manifest_str == '':
                self.remote = {}
            else:
                self.remote = yaml.load(manifest_str)
            self._remote_fetched = True

    def get_remote_readme(self, module_name, version=None):
        self.update_remote()
        # Resolve name and version
        if module_name not in self.remote:
            raise LookupError(module_name)
        if version != None and version not in self.remote[module_name]['versions']:
            raise LookupError(version)
        if version == None:
            version = self.remote[module_name]['latest_version']
        # Try for cache hit
        try:
            readme = self.remote_readme[module_name][version]
            return readme
        except LookupError:
            readme_url = self._store_path_builder.module_readme(module_name, version)
            readme = su.get_file_to_string(readme_url)
            # add to cache
            if module_name not in self.remote_readme:
                self.remote_readme[module_name] = {}
            self.remote_readme[module_name][version] = readme
        return readme
    
    def get_remote_config(self, module_name, version=None):
        self.update_remote()
        # Resolve name and version
        if module_name not in self.remote:
            raise LookupError(module_name)
        if version != None and version not in self.remote[module_name]['versions']:
            raise LookupError(version)
        if version == None:
            version = self.remote[module_name]['latest_version']
        # Check cache
        try:
            config = self.remote_config[module_name][version]
            return config
        except LookupError:
            config_url = self._store_path_builder.module_conf(module_name, version)
            config = yaml.load(su.get_file_to_string(config_url))
            # add to cache
            if module_name not in self.remote_config:
                self.remote_config[module_name] = {}
            self.remote_config[module_name][version] = config
        return config

def get_widgets_for_annotator(annotator_name, skip_installed=False):
    """
    Get webviewer widgets that require an annotator. Optionally skip the
    widgets that are already installed.
    """
    linked_widgets = []
    for widget_name in list_remote():
        widget_info = get_remote_module_info(widget_name)
        if widget_info.type == 'webviewerwidget':
            widget_config = mic.get_remote_config(widget_name)
            linked_annotator = widget_config.get('required_annotator')
            if linked_annotator == annotator_name:
                if skip_installed and module_exists_local(widget_name):
                    continue
                else:
                    linked_widgets.append(widget_info)
    return linked_widgets

def list_local():
    """
    Returns a list of locally installed modules.
    """
    mic.update_local()
    return sorted(list(mic.local.keys()))

def list_remote():
    """
    Returns a list of remotely available modules.
    """
    mic.update_remote()
    return sorted(list(mic.remote.keys()))

def get_local_module_infos(types=[], names=[]):
    all_infos = list(mic.local.values())
    return_infos = []
    for minfo in all_infos:
        if types and minfo.type not in types:
            continue
        elif names and minfo.name not in names:
            continue
        else:
            return_infos.append(minfo)
    return return_infos

def set_jobs_dir (d):
    update_system_conf_file({'jobs_dir': d})

def get_jobs_dir():
    jobs_dir = get_system_conf().get('jobs_dir')
    if jobs_dir is None:
        home_dir = os.path.expanduser('~')
        jobs_dir = os.path.join(home_dir,'open-cravat','jobs')
        set_jobs_dir(jobs_dir)
    if not(os.path.isdir(jobs_dir)):
        os.makedirs(jobs_dir)
    return jobs_dir

def search_remote(*patterns):
    """
    Return remote module names which match any of supplied patterns
    """
    matching_names = []
    for module_name in list_remote():
        if any([re.fullmatch(pattern, module_name) for pattern in patterns]):
            matching_names.append(module_name)
    return matching_names

def search_local(*patterns):
    """
    Return local module names which match any of supplied patterns
    """
    matching_names = []
    for module_name in list_local():
        if any([re.fullmatch(pattern, module_name) for pattern in patterns]):
            matching_names.append(module_name)
    return matching_names

def module_exists_local(module_name):
    """
    Returns True if a module exists locally. False otherwise.
    """
    return module_name in mic.local

def module_exists_remote(module_name, version=None):
    """
    Returns true if a module (optionally versioned) exists in remote
    """
    mic.update_remote()
    if module_name in mic.remote:
        if version is not None:
            return version in mic.remote[module_name]['versions']
        else:
            return True
    else:
        return False

def get_remote_latest_version(module_name):
    """
    Returns latest remotely available version of a module.
    """
    mic.update_remote()
    return mic.remote[module_name]['latest_version']

def get_remote_module_info(module_name):
    """
    Returns a RemoteModuleInfo object for a module.
    """
    mic.update_remote()
    if module_exists_remote(module_name, version=None):
        mdict = mic.remote[module_name]
        module = RemoteModuleInfo(module_name, **mdict)
        return module
    else:
        return None

def get_remote_module_readme(module_name, version=None):
    """
    Get the detailed description file about a module as a string.
    """
    return mic.get_remote_readme(module_name, version=version)

def compare_version (v1, v2):
    sv1 = StrictVersion(v1)
    sv2 = StrictVersion(v2)
    if sv1 == sv2:
        return 0
    elif sv1 > sv2:
        return 1
    else:
        return -1

def get_readme(module_name, version=None):
    """
    Get the readme. Use local if available.
    """
    exists_remote = module_exists_remote(module_name, version=version)
    exists_local = module_exists_local(module_name)
    if exists_remote:
        remote_readme = mic.get_remote_readme(module_name)
    else:
        remote_readme = ''
    if exists_local:
        local_info = get_local_module_info(module_name)
        if os.path.exists(local_info.readme_path):
            local_readme = open(local_info.readme_path).read()
        else:
            local_readme = ''
    else:
        local_readme = ''
    if exists_remote == True:
        if exists_local:
            remote_version = get_remote_latest_version(module_name)
            local_version = local_info.version
            if compare_version(remote_version, local_version) > 0:
                return remote_readme
            else:
                return local_readme
        else:
            return remote_readme
    else:
        return local_readme

def get_local_module_info(module_name):
    """
    Returns a LocalModuleInfo object for a module.
    """
    if module_name in mic.local:
        return mic.local[module_name]
    else:
        return None

def print_stage_handler(cur_stage, total_stages, cur_size, total_size):
    rem_stages = total_stages - cur_stage
    perc = cur_stage/total_stages*100
    out = '\r[{1}{2}] {0:.0f}% '.format(perc, '*'*cur_stage,' '*rem_stages)
    sys.stdout.write(out)
    if cur_stage == total_stages:
        print()

class InstallProgressHandler(object):
    def __init__ (self, module_name, module_version):
        self.module_name = module_name
        self.module_version = module_version
        self._make_display_name()
        self.cur_stage = None

    def _make_display_name(self):
        ver_str = self.module_version if self.module_version is not None else ''
        self.display_name = ':'.join([self.module_name,ver_str])

    def stage_start(self, stage):
        pass

    def stage_progress(self, cur_chunk, total_chunks, cur_size, total_size):
        pass

    def set_module_version(self, module_version):
        self.module_version = module_version
        self._make_display_name()

    def set_module_name(self, module_name):
        self.module_name = module_name
        self._make_display_name()

    def _stage_msg(self, stage):
        if stage is None or stage=='':
            return ''
        elif stage=='start':
            return 'Start install of %s' %self.display_name
        elif stage=='download_code':
            return 'Downloading %s code archive' %self.display_name
        elif stage=='extract_code':
            return 'Extracting %s code archive' %self.display_name
        elif stage=='verify_code':
            return 'Verifying %s code integrity' %self.display_name
        elif stage=='download_data':
            return 'Downloading %s data' %self.display_name
        elif stage=='extract_data':
            return 'Extracting %s data' %self.display_name
        elif stage=='verify_data':
            return 'Verifying %s data integrity' %self.display_name
        elif stage=='finish':
            return 'Finished installation of %s' %self.display_name
        else:
            raise ValueError(stage)

def install_widgets_for_module (module_name):
    widget_name = 'wg' + module_name
    install_module(widget_name)

def install_module (module_name, version=None, force_data=False, stage_handler=None, **kwargs):
    """
    Installs a module.
    version=None will install the latest version.
    force_data=True will force an update to the data files, even if one is not needed.
    """
    try:
        if stage_handler is None:
            stage_handler = InstallProgressHandler(module_name, version)
        if version is None:
            version = get_remote_latest_version(module_name)
            stage_handler.set_module_version(version)
        stage_handler.stage_start('start')
        modules_dir = get_modules_dir()
        sys_conf = get_system_conf()
        store_url = sys_conf['store_url']
        store_path_builder = su.PathBuilder(store_url,'url')
        remote_data_version = get_remote_data_version(module_name, version=version)
        if module_name in list_local():
            local_info = get_local_module_info(module_name)
            if local_info.has_data:
                local_data_version = local_info.version
            else:
                local_data_version = None
        else:
            local_data_version = None
        code_url = store_path_builder.module_code(module_name, version)
        zipfile_fname = module_name + '.zip'
        remote_info = get_remote_module_info(module_name)
        module_type = remote_info.type
        module_dir = os.path.join(modules_dir, module_type+'s', module_name)
        if not(os.path.isdir(module_dir)):
            os.makedirs(module_dir)
        else:
            uninstall_module_code(module_name)
        zipfile_path = os.path.join(module_dir, zipfile_fname)
        stage_handler.stage_start('download_code')
        r = su.stream_to_file(code_url, zipfile_path, stage_handler=stage_handler.stage_progress, **kwargs)
        if r.status_code != 200:
            raise(requests.HTTPError(r))
        stage_handler.stage_start('extract_code')
        zf = zipfile.ZipFile(zipfile_path)
        zf.extractall(module_dir)
        zf.close()
        stage_handler.stage_start('verify_code')
        code_manifest_url = store_path_builder.module_code_manifest(module_name, version)
        code_manifest = yaml.load(su.get_file_to_string(code_manifest_url))
        su.verify_against_manifest(module_dir, code_manifest)
        os.remove(zipfile_path)
        mic.update_local()
        local_info = get_local_module_info(module_name)
        if (remote_data_version is not None) and (remote_data_version != local_data_version or force_data):
            data_url = store_path_builder.module_data(module_name, remote_data_version)
            if local_info.data_dir_exists:
                uninstall_module_data(module_name)
            data_fname = '.'.join([module_name,'data','zip'])
            data_path = os.path.join(module_dir, data_fname)
            stage_handler.stage_start('download_data')
            r = su.stream_to_file(data_url, data_path, stage_handler=stage_handler.stage_progress, **kwargs)
            if r.status_code != 200:
                raise(requests.HTTPError(r))
            stage_handler.stage_start('extract_data')
            zf = zipfile.ZipFile(data_path)
            zf.extractall(module_dir)
            zf.close()
            stage_handler.stage_start('verify_data')
            data_manifest_url = store_path_builder.module_data_manifest(module_name, remote_data_version)
            data_manifest = yaml.load(su.get_file_to_string(data_manifest_url))
            su.verify_against_manifest(module_dir, data_manifest)
            os.remove(data_path)
        mic.update_local()
        stage_handler.stage_start('finish')
        if module_name.startswith('wg') == False:
            try:
                install_module('wg' + module_name)
            except:
                pass
    except:
        try:
            shutil.rmtree(module_dir)
        except (NameError, FileNotFoundError):
            pass
        except:
            raise
        raise

def get_remote_data_version(module_name, version=None):
    mic.update_remote()
    if version is None:
        version = get_remote_latest_version(module_name)
    return mic.remote[module_name]['data_versions'][version]

def uninstall_module (module_name):
    """
    Uninstalls a module.
    """
    uninstalled_modules = False
    if module_name in list_local():
        local_info = get_local_module_info(module_name)
        shutil.rmtree(local_info.directory)
        uninstalled_modules = True
    if uninstalled_modules:
        mic.update_local()

def uninstall_module_code (module_name):
    """
    Uninstalls all code files from a module.
    """
    if module_name in list_local():
        module_info = get_local_module_info(module_name)
        module_dir = module_info.directory
        for item in os.listdir(module_dir):
            item_path = os.path.join(module_dir, item)
            if item_path != module_info.data_dir:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

def uninstall_module_data (module_name):
    """
    Uninstalls all data files and directories from a module.
    """
    if module_name in list_local():
        module_info = get_local_module_info(module_name)
        if module_info.data_dir_exists:
            for item in os.listdir(module_info.data_dir):
                item_path = os.path.join(module_info.data_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

def set_modules_dir (path, overwrite=False):
    """
    Set the modules_dir to the directory in path.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if not(os.path.isdir(path)):
        os.makedirs(path)
    old_conf_path = get_main_conf_path()
    update_system_conf_file({constants.modules_dir_key:path})
    if not(os.path.exists(get_main_conf_path())):
        if os.path.exists(old_conf_path):
            overwrite_conf_path = old_conf_path
        else:
            overwrite_conf_path = get_main_default_path()
        shutil.copy(overwrite_conf_path, get_main_conf_path())

#return a list of module types (e.g. annotators) in the local install
def get_local_module_types():
    types = []
    for module in mic.local:
        if mic.local[module].type not in types:
            types.append(mic.local[module].type)
    return types

def get_local_module_infos_of_type (t):
    modules = {}
    mic.update_local()
    for module_name in mic.local:
        if mic.local[module_name].type == t:
            modules[module_name] = mic.local[module_name] 
    return modules

def refresh_cache ():
    """
    Refresh the local modules cache
    """
    global mic
    mic = ModuleInfoCache()

def get_local_module_infos_by_names (module_names):
    modules = {}
    for module_name in module_names:
        module = get_local_module_info(module_name)
        if module is not None:
            modules[module_name] = module
    return modules

def get_system_conf():
    """
    Get the system config. Fill in the default modules dir if not set.
    """
    if os.path.exists(constants.system_conf_path):
        conf = load_yml_conf(constants.system_conf_path)
    else:
        conf = load_yml_conf(constants.system_conf_template_path)
    if constants.modules_dir_key not in conf:
        conf[constants.modules_dir_key] = constants.default_modules_dir
    return conf

def get_modules_dir():
    """
    Get the current modules directory
    """
    conf = get_system_conf()
    modules_dir = conf[constants.modules_dir_key]
    return modules_dir

def write_system_conf_file(d):
    """
    Fully overwrite the system config file with a new system config.
    """
    with open(constants.system_conf_path,'w') as wf:
        wf.write(yaml.dump(d, default_flow_style=False))

def update_system_conf_file(d):
    """
    Recursively update the system config and re-write to disk.
    """
    try:
        sys_conf = recursive_update(get_system_conf(), d)
        write_system_conf_file(sys_conf)
        refresh_cache()
        return True
    except:
        raise
        return False

def read_system_conf_template ():
    with open(constants.system_conf_template_path) as f:
        d = yaml.load(f)
        return d
    return None

def get_main_conf_path():
    """
    Get the path to where the main cravat config (cravat.yml) should be.
    """
    return os.path.join(get_modules_dir(), constants.main_conf_fname)

def get_main_default_path():
    """
    Get the path to the default main cravat config.(backup lives in the pip package)
    """
    return os.path.join(constants.packagedir, constants.main_conf_fname)

def publish_module(module_name, user, password, overwrite_version=False, include_data=True):
    sys_conf = get_system_conf()
    publish_url = sys_conf['publish_url']
    mic.update_local()
    local_info = get_local_module_info(module_name)
    if local_info == None:
        print(module_name + ' does not exist.')
        return
    check_url = publish_url + '/%s/%s/check' %(module_name,local_info.version)
    r = requests.get(check_url, auth=(user,password))
    if r.status_code != 200:
        print('Cannot upload')
        if r.status_code == 401:
            print('Incorrect username or password')
            exit()
        elif r.status_code == 400:
            err = json.loads(r.text)
            if err['code'] == su.VersionExists.code:
                while True:
                    if overwrite_version:
                        break
                    resp = input('Version exists. Do you wish to overwrite (y/n)? ')
                    if resp == 'y':
                        overwrite_version = True
                        break
                    if resp == 'n':
                        exit()
                    else:
                        print('Your response (\'%s\') was not one of the expected responses: y, n'%resp)
                        continue
            else:
                print(err['message'])
                exit()
        elif r.status_code == 500:
            print('Server error')
            exit()
        else:
            print('HTTP response status code: %d' %r.status_code)
            exit()
    zf_name = '%s.%s.zip' %(module_name, local_info.version)
    zf_path = os.path.join(get_modules_dir(), zf_name)
    print('Zipping module and generating checksums')
    zip_builder = su.ModuleArchiveBuilder(zf_path, base_path=local_info.directory)
    for item_name in os.listdir(local_info.directory):
            item_path = os.path.join(local_info.directory, item_name)
            if item_path == local_info.data_dir and not(include_data):
                continue
            else:
                zip_builder.add_item(item_path)
    manifest = zip_builder.get_manifest()
    zip_builder.close()
    post_url = '/'.join([publish_url, module_name, local_info.version])
    if overwrite_version:
        post_url += '?overwrite=1'
    fields={
            'manifest': (
                         'manifest.json',
                         json.dumps(manifest),
                         'application/json'
                        ),
            'archive': (
                        zf_name,
                        open(zf_path,'rb'),
                        'application/octet-stream'
                       )
            }
    print('Uploading to store')
    r = su.stream_multipart_post(post_url, fields, stage_handler=print_stage_handler, auth=(user,password))
    if r.status_code != 200:
        print('Upload failed')
        print(r.status_code)
        print(r.text)
    if r.text:
        print(r.text)

def create_account(username, password):
    sys_conf = get_system_conf()
    publish_url = sys_conf['publish_url']
    create_account_url = publish_url+'/create-account'
    d = {
         'username':username,
         'password':password,
         }
    r = requests.post(create_account_url, json=d)
    if r.status_code == 500:
        print('Server error')
    if r.text:
        print(r.text)

def change_password(username, cur_pw, new_pw):
    sys_conf = get_system_conf()
    publish_url = sys_conf['publish_url']
    change_pw_url = publish_url+'/change-password'
    r = requests.post(change_pw_url, auth=(username, cur_pw), json={'newPassword':new_pw})
    if r.status_code == 500:
        print('Server error')
    elif r.status_code == 401:
        print('Incorrect username and password')
    if r.text:
        print(r.text)

def send_reset_email(username):
    sys_conf = get_system_conf()
    publish_url = sys_conf['publish_url']
    reset_pw_url = publish_url+'/reset-password'
    r = requests.post(reset_pw_url, params={'username':username})
    if r.status_code == 500:
        print('Server error')
    if r.text:
        print(r.text)

def send_verify_email(username):
    sys_conf = get_system_conf()
    publish_url = sys_conf['publish_url']
    reset_pw_url = publish_url+'/verify-email'
    r = requests.post(reset_pw_url, params={'username':username})
    if r.status_code == 500:
        print('Server error')
    if r.text:
        print(r.text)

def check_login(username, password):
    sys_conf = get_system_conf()
    publish_url = sys_conf['publish_url']
    login_url = publish_url+'/login'
    r = requests.get(login_url, auth=(username,password))
    if r.status_code == 200:
        print('Correct username and password')
    elif r.status_code == 500:
        print('Server error')
    else:
        print('Incorrect username and password')

def new_annotator(annot_name):
    annot_root = os.path.join(get_modules_dir(),'annotators',annot_name)
    template_root = os.path.join(constants.packagedir,'annotator_template')
    shutil.copytree(template_root, annot_root)
    for dir_path, _, fnames in os.walk(annot_root):
        for old_fname in fnames:
            old_fpath = os.path.join(dir_path,old_fname)
            new_fname = old_fname.replace('annotator_template',annot_name,1)
            new_fpath = os.path.join(dir_path,new_fname)
            os.rename(old_fpath,new_fpath)
    mic.update_local()

def make_example_input (d):
    fn = 'example_input'
    ifn = os.path.join(constants.packagedir, fn)
    ofn = os.path.join(d, fn)
    shutil.copyfile(ifn, ofn)
    print(fn + ' has been created at ' + os.path.abspath(d))

def report_issue ():
    import webbrowser
    webbrowser.open('http://github.com/KarchinLab/open-cravat/issues')

def get_system_conf_info ():
    set_jobs_dir(get_jobs_dir())
    confpath = constants.system_conf_path
    if os.path.exists(confpath):
        conf = load_yml_conf(confpath)
        confexists = True
    else:
        conf = {}
        confexists = False
    if constants.modules_dir_key not in conf:
        conf[constants.modules_dir_key] = constants.default_modules_dir
    system_conf_info = {'path': confpath, 'exists': confexists, 'content': yaml.dump(conf, default_flow_style=False)}
    return system_conf_info

def show_system_conf ():
    system_conf_info = get_system_conf_info()
    print('Configuration file path:', system_conf_info['path'])
    print(system_conf_info['content'])

"""
Persistent ModuleInfoCache prevents repeated reloading of local and remote
module info
"""
mic = ModuleInfoCache()
