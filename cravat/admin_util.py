import zipfile
import shutil
import os
import sys
import oyaml as yaml
import copy
import json
from . import constants
from . import store_utils as su
from . import util
import requests
import traceback
import re
from distutils.version import LooseVersion
import pkg_resources
from collections import defaultdict
from types import SimpleNamespace
from . import exceptions
from collections.abc import MutableMapping
import multiprocessing
import importlib
import traceback
import signal
import subprocess
from urllib.error import HTTPError

class InstallProgressHandler(object):
    def __init__(self, module_name, module_version):
        self.module_name = module_name
        self.module_version = module_version
        self._make_display_name()
        self.cur_stage = None

    def _make_display_name(self):
        ver_str = self.module_version if self.module_version is not None else ""
        self.display_name = ":".join([self.module_name, ver_str])

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
        if stage is None or stage == "":
            return ""
        elif stage == "start":
            return f"[{util.get_current_time_str()}] Starting to install {self.display_name}..."
        elif stage == "download_code":
            return f"[{util.get_current_time_str()}] Downloading code archive of {self.display_name}..."
        elif stage == "extract_code":
            return f"[{util.get_current_time_str()}] Extracting code archive of {self.display_name}..."
        elif stage == "verify_code":
            return f"[{util.get_current_time_str()}] Verifying code integrity of {self.display_name}..."
        elif stage == "download_data":
            return f"[{util.get_current_time_str()}] Downloading data of {self.display_name}..."
        elif stage == "extract_data":
            return f"[{util.get_current_time_str()}] Extracting data of {self.display_name}..."
        elif stage == "verify_data":
            return f"[{util.get_current_time_str()}] Verifying data integrity of {self.display_name}..."
        elif stage == "finish":
            return f"[{util.get_current_time_str()}] Finished installation of {self.display_name}"
        elif stage == "killed":
            return f"[{util.get_current_time_str()}] Aborted installation of {self.display_name}"
        elif stage == "Unqueued":
            return f"Unqueued {self.display_name} from installation"
        else:
            raise ValueError(stage)


class LocalInfoCache(MutableMapping):
    """
    LocalInfoCache will initially store the paths to modules. When a module info
    is requested, the module info will be created from the path, stored, and returned.
    LocalInfoCache exposes the same interface as a dictionary.
    """

    def __init__(self, *args, **kwargs):
        self.store = dict()
        self.update(dict(*args, **kwargs))  # use the free update to set keys

    def __getitem__(self, key):
        if key not in self.store:
            raise KeyError(key)
        if not isinstance(self.store[key], LocalModuleInfo):
            self.store[key] = LocalModuleInfo(self.store[key])
        return self.store[key]

    def __setitem__(self, key, value):
        if not (isinstance(value, LocalModuleInfo) or os.path.isdir(value)):
            raise ValueError(value)
        self.store[key] = value

    def __delitem__(self, key):
        del self.store[key]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)


class LocalModuleInfo(object):
    def __init__(self, dir_path, name=None):
        self.directory = dir_path
        if name is None:
            self.name = os.path.basename(self.directory)
        else:
            self.name = name
        self.script_path = os.path.join(self.directory, self.name + ".py")
        self.script_exists = os.path.exists(self.script_path)
        self.conf_path = os.path.join(self.directory, self.name + ".yml")
        self.conf_exists = os.path.exists(self.conf_path)
        self.exists = self.conf_exists
        startofinstall_path = os.path.join(self.directory, "startofinstall")
        if os.path.exists(startofinstall_path):
            endofinstall_path = os.path.join(self.directory, "endofinstall")
            if os.path.exists(endofinstall_path):
                self.exists = True
            else:
                self.exists = False
        self.data_dir = os.path.join(dir_path, "data")
        self.data_dir_exists = os.path.isdir(self.data_dir)
        self.has_data = self.data_dir_exists and len(os.listdir(self.data_dir)) > 0
        self.test_dir = os.path.join(dir_path, "test")
        self.test_dir_exists = os.path.isdir(self.test_dir)
        self.tests = self.get_tests()
        self.has_test = len(self.tests) > 0
        self.readme_path = os.path.join(self.directory, self.name + ".md")
        self.readme_exists = os.path.exists(self.readme_path)
        if self.readme_exists:
            with open(self.readme_path, encoding="utf-8") as f:
                self.readme = f.read()
        else:
            self.readme = ""
        self.helphtml_path = os.path.join(self.directory, "help.html")
        self.helphtml_exists = os.path.exists(self.helphtml_path)
        self.conf = {}
        if self.conf_exists:
            from cravat.config_loader import ConfigLoader

            conf = ConfigLoader()
            self.conf = conf.get_module_conf(self.name)
        self.type = self.conf.get("type")
        self.version = self.conf.get("version")
        self.description = self.conf.get("description")
        self.hidden = self.conf.get("hidden", False)
        dev_dict = self.conf.get("developer")
        if not (type(dev_dict) == dict):
            dev_dict = {}
        self.developer = get_developer_dict(**dev_dict)
        if "type" not in self.conf:
            self.conf["type"] = "unknown"
        self.type = self.conf["type"]
        self.level = self.conf.get("level")
        self.input_format = self.conf.get("input_format")
        self.secondary_module_names = list(self.conf.get("secondary_inputs", {}))
        if self.type == "annotator":
            if self.level == "variant":
                self.output_suffix = self.name + ".var"
            elif self.level == "gene":
                self.output_suffix = self.name + ".gen"
            else:
                self.output_suffix = self.name + "." + self.type
        self.title = self.conf.get("title", self.name)
        self.disk_size = None
        self.tags = self.conf.get("tags", [])
        self.datasource = str(self.conf.get("datasource", ""))
        self.smartfilters = self.conf.get("smartfilters")
        self.groups = self.conf.get("groups", [])

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

    def get_tests(self):
        """
        Gets the module test input file(s) if the module has tests.  A test is a input file / key file pair.
        """
        tests = []
        if self.test_dir_exists:
            for i in os.listdir(self.test_dir):
                if (
                    "input" in i
                    and os.path.isfile(os.path.join(self.test_dir, i))
                    and os.path.isfile(
                        os.path.join(self.test_dir, i.replace("input", "key"))
                    )
                ):
                    tests.append(i)
        return tests

    def serialize(self):
        return self.__dict__


class ModuleInfoCache(object):
    def __init__(self):
        self._sys_conf = get_system_conf()
        self._modules_dir = get_modules_dir()
        self.local = LocalInfoCache()
        self._remote_url = None
        self.remote = {}
        self._remote_fetched = False
        self.remote_readme = {}
        self.remote_config = {}
        self.update_local()
        self._store_path_builder = su.PathBuilder(self._sys_conf["store_url"], "url")
        self.download_counts = {}
        self._counts_fetched = False

    def get_local(self):
        modules_dir = get_modules_dir()
        if self._modules_dir != modules_dir:
            self._modules_dir = modules_dir
            self.update_local()
        return self.local

    def update_download_counts(self, force=False):
        if force or not (self._counts_fetched):
            counts_url = self._store_path_builder.download_counts()
            counts_str = su.get_file_to_string(counts_url)
            self.download_counts = yaml.safe_load(counts_str).get("modules", {})
            self._counts_fetched = True

    def update_local(self):
        self.local = LocalInfoCache()
        self._modules_dir = get_modules_dir()
        if not (os.path.exists(self._modules_dir)):
            return
        for mg in os.listdir(self._modules_dir):
            if mg == constants.install_tempdir_name:
                continue
            mg_path = os.path.join(self._modules_dir, mg)
            basename = os.path.basename(mg_path)
            if (
                not (os.path.isdir(mg_path))
                or basename.startswith(".")
                or basename.startswith("_")
            ):
                continue
            for module_name in os.listdir(mg_path):
                if module_name == "hgvs":  # deprecate hgvs
                    continue
                module_dir = os.path.join(mg_path, module_name)
                if (
                    module_dir.startswith(".") == False
                    and os.path.isdir(module_dir)
                    and not module_name.startswith(".")
                    and not module_name.startswith("_")
                    and os.path.exists(os.path.join(module_dir, module_name + ".yml"))
                ):
                    self.local[module_name] = module_dir

    def update_remote(self, force=False):
        if force or not (self._remote_fetched):
            if self._remote_url is None:
                self._remote_url = self._store_path_builder.manifest()
                try:
                    manifest_str = su.get_file_to_string(self._remote_url)
                except HTTPError as e:
                    # Current version may not have a manifest if it's a dev version
                    if e.code == 404:
                        self._remote_url = self._store_path_builder.manifest_nover()
                        manifest_str = su.get_file_to_string(self._remote_url)
            else:
                manifest_str = su.get_file_to_string(self._remote_url)
            self.remote = yaml.safe_load(manifest_str)
            self.remote.pop("hgvs", None)  # deprecate hgvs annotator
            self._remote_fetched = True

    def get_remote_readme(self, module_name, version=None):
        self.update_remote()
        # Resolve name and version
        if module_name not in self.remote:
            raise LookupError(module_name)
        if version != None and version not in self.remote[module_name]["versions"]:
            raise LookupError(version)
        if version == None:
            version = self.remote[module_name]["latest_version"]
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
        if version == None:
            version = self.remote[module_name]["latest_version"]
        # Check cache
        try:
            config = self.remote_config[module_name][version]
            return config
        except LookupError:
            config_url = self._store_path_builder.module_conf(module_name, version)
            config = yaml.safe_load(su.get_file_to_string(config_url))
            # add to cache
            if module_name not in self.remote_config:
                self.remote_config[module_name] = {}
            self.remote_config[module_name][version] = config
        return config

    # def get_code_size(self, module_name, version):
    #     code_url = self._store_path_builder.module_code(module_name, version)
    #     r = requests.get(code_url)
    #     r.close()
    #     return int(r.headers['Content-Length'])


class ReadyState(object):

    READY = 0
    MISSING_MD = 1
    UPDATE_NEEDED = 2

    messages = {
        0: "",
        1: "Modules directory not found",
        2: 'Update on system modules needed. Run "oc module install-base"',
    }

    def __init__(self, code=READY):
        if code not in self.messages:
            raise ValueError(code)
        self.code = code

    @property
    def message(self):
        return self.messages[self.code]

    def __bool__(self):
        return self.code == self.READY

    def __iter__(self):
        yield "ready", bool(self)
        yield "code", self.code
        yield "message", self.message


class RemoteModuleInfo(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.versions = kwargs.get("versions", [])
        self.latest_version = kwargs.get("latest_version", "")
        self.type = kwargs.get("type", "")
        self.title = kwargs.get("title", "")
        self.description = kwargs.get("description", "")
        self.size = kwargs.get("size", 0)
        self.data_size = kwargs.get("data_size", 0)
        self.code_size = kwargs.get("code_size", 0)
        self.datasource = kwargs.get("datasource", "")
        self.hidden = kwargs.get("hidden", False)
        if self.datasource == None:
            self.datasource = ""
        dev_dict = kwargs.get("developer")
        if not (type(dev_dict) == dict):
            dev_dict = {}
        self.developer = get_developer_dict(**dev_dict)
        self.data_versions = kwargs.get("data_versions", {})
        self.data_sources = {
            x: str(y) for x, y in kwargs.get("data_sources", {}).items()
        }
        self.tags = kwargs.get("tags", [])
        self.publish_time = kwargs.get("publish_time")

    def has_version(self, version):
        return version in self.versions


def change_password(username, cur_pw, new_pw):
    sys_conf = get_system_conf()
    publish_url = sys_conf["publish_url"]
    change_pw_url = publish_url + "/change-password"
    r = requests.post(
        change_pw_url, auth=(username, cur_pw), json={"newPassword": new_pw}
    )
    if r.status_code == 500:
        print("Server error")
    elif r.status_code == 401:
        print("Incorrect username and password")
    if r.text:
        print(r.text)


def check_login(username, password):
    sys_conf = get_system_conf()
    publish_url = sys_conf["publish_url"]
    login_url = publish_url + "/login"
    r = requests.get(login_url, auth=(username, password))
    if r.status_code == 200:
        print("Correct username and password")
    elif r.status_code == 500:
        print("Server error")
    else:
        print("Incorrect username and password")


def compare_version(v1, v2):
    sv1 = LooseVersion(v1)
    sv2 = LooseVersion(v2)
    if sv1 == sv2:
        return 0
    elif sv1 > sv2:
        return 1
    else:
        return -1


def create_account(username, password):
    sys_conf = get_system_conf()
    publish_url = sys_conf["publish_url"]
    create_account_url = publish_url + "/create-account"
    d = {
        "username": username,
        "password": password,
    }
    r = requests.post(create_account_url, json=d)
    if r.status_code == 500:
        print("Server error")
    if r.text:
        print(r.text)


def get_annotator_dir(module_name):
    module_dir = os.path.join(get_modules_dir(), "annotators", module_name)
    if os.path.exists(module_dir) == False:
        module_dir = None
    return module_dir


def get_annotator_script_path(module_name):
    module_path = os.path.join(
        get_modules_dir(), "annotators", module_name, module_name + ".py"
    )
    if os.path.exists(module_path) == False:
        module_path = None
    return module_path


def get_conf_dir():
    conf = get_system_conf()
    conf_dir = conf[constants.conf_dir_key]
    return conf_dir


def get_cravat_conf():
    from cravat.config_loader import ConfigLoader

    confpath = get_main_conf_path()
    conf = ConfigLoader()
    cravat_conf = conf.get_cravat_conf()
    return cravat_conf


def get_cravat_conf_info():
    cravat_conf = get_cravat_conf()
    cravat_conf_info = {
        "path": get_main_conf_path(),
        "content": yaml.dump(cravat_conf, default_flow_style=False),
    }
    return cravat_conf_info


def get_current_package_version():
    version = pkg_resources.get_distribution("open-cravat").version
    return version


def get_default_assembly():
    conf = get_cravat_conf()
    default_assembly = conf.get("default_assembly", None)
    return default_assembly


def get_developer_dict(**kwargs):
    d = {}
    d["name"] = kwargs.get("name", "")
    d["email"] = kwargs.get("email", "")
    d["organization"] = kwargs.get("organization")
    d["citation"] = kwargs.get("citation", "")
    d["website"] = kwargs.get("website", "")
    return d


def get_download_counts():
    mic.update_download_counts()
    counts = mic.download_counts
    return counts


def get_install_deps(module_name, version=None, skip_installed=True):
    mic.update_remote()
    # If input module version not provided, set to highest
    if version is None:
        version = get_remote_latest_version(module_name)
    config = mic.get_remote_config(module_name, version=version)
    req_list = config.get("requires", [])
    deps = {}
    for req_string in req_list:
        req = pkg_resources.Requirement(req_string)
        rem_info = get_remote_module_info(req.name)
        # Skip if module does not exist
        if rem_info is None and get_local_module_info(req.name) is None:
            continue
        if skip_installed:
            # Skip if a matching version is installed
            local_info = get_local_module_info(req.name)
            if local_info and local_info.version in req:
                continue
        # Select the highest matching version
        lvers = [LooseVersion(v) for v in rem_info.versions]
        lvers.sort(reverse=True)
        highest_matching = None
        for lv in lvers:
            if lv.vstring in req:
                highest_matching = lv.vstring
                break
        # Dont include if no matching version exists
        if highest_matching is not None:
            deps[req.name] = highest_matching
    return deps


def get_jobs_dir():
    conf = get_system_conf()
    jobs_dir = conf[constants.jobs_dir_key]
    return jobs_dir


def get_last_assembly():
    conf = get_cravat_conf()
    last_assembly = conf.get("last_assembly")
    return last_assembly


def get_latest_package_version():
    """
    Return latest cravat version on pypi
    """
    all_vers = get_package_versions()
    if all_vers:
        return all_vers[-1]
    else:
        return None


def get_local_module_info(module_name):
    """
    Returns a LocalModuleInfo object for a module.
    """
    if module_name in mic.get_local():
        return mic.get_local()[module_name]
    else:
        if os.path.exists(module_name):
            module_info = LocalModuleInfo(module_name)
            return module_info
        return None


def get_local_module_infos(types=[], names=[]):
    all_infos = list(mic.get_local().values())
    return_infos = []
    for minfo in all_infos:
        if types and minfo.type not in types:
            continue
        elif names and minfo.name not in names:
            continue
        elif minfo.exists == False:
            continue
        else:
            return_infos.append(minfo)
    return return_infos


def get_local_module_infos_by_names(module_names):
    modules = {}
    for module_name in module_names:
        module = get_local_module_info(module_name)
        if module is not None:
            modules[module.name] = module
    return modules


def get_local_module_info_by_name(module_name):
    return get_local_module_info(module_name)


def get_local_reporter_module_infos_by_names(module_names):
    modules = {}
    for module_name in module_names:
        if not module_name.endswith("reporter"):
            module_name += "reporter"
        module = get_local_module_info(module_name)
        if module is not None:
            modules[module.name] = module
    return modules


def get_local_module_infos_of_type(t, update=False):
    modules = {}
    if update:
        mic.update_local()
    for module_name in mic.get_local():
        if mic.get_local()[module_name].type == t:
            modules[module_name] = mic.get_local()[module_name]
    return modules


def get_local_module_types():
    types = []
    for module in mic.get_local():
        if mic.get_local()[module].type not in types:
            types.append(mic.get_local()[module].type)
    return types


def get_main_conf_path():
    """
    Get the path to where the main cravat config (cravat.yml) should be.
    """
    return os.path.join(get_conf_dir(), constants.main_conf_fname)


def get_main_default_path():
    """
    Get the path to the default main cravat config.(backup lives in the pip package)
    """
    return os.path.join(constants.packagedir, constants.main_conf_fname)


def get_mapper_script_path(module_name):
    module_path = os.path.join(
        get_modules_dir(), "mappers", module_name, module_name + ".py"
    )
    if os.path.exists(module_path) == False:
        module_path = None
    return module_path


def get_max_num_concurrent_annotators_per_job():
    return get_system_conf()["max_num_concurrent_annotators_per_job"]


def get_module_conf_path(module_name):
    modules_dir = get_modules_dir()
    typefns = os.listdir(modules_dir)
    conf_path = None
    for typefn in typefns:
        typepath = os.path.join(modules_dir, typefn)
        if os.path.isdir(typepath):
            modulefns = os.listdir(typepath)
            for modulefn in modulefns:
                if os.path.basename(modulefn) == module_name:
                    modulepath = os.path.join(typepath, modulefn)
                    if os.path.isdir(modulepath):
                        path = os.path.join(modulepath, module_name + ".yml")
                        if os.path.exists(path):
                            conf_path = path
                            break
            if conf_path is not None:
                break
    return conf_path


def get_modules_dir():
    """
    Get the current modules directory
    """
    if constants.custom_modules_dir is not None:
        modules_dir = constants.custom_modules_dir
    else:
        modules_dir = os.environ.get(constants.modules_dir_env_key, None)
        if modules_dir is not None and modules_dir != "":
            modules_dir = os.environ.get(constants.modules_dir_env_key)
        else:
            conf = get_system_conf()
            modules_dir = conf[constants.modules_dir_key]
    modules_dir = os.path.abspath(modules_dir)
    return modules_dir


def get_package_versions():
    """
    Return available open-cravat versions from pypi, sorted asc
    """
    try:
        r = requests.get("https://pypi.org/pypi/open-cravat/json", timeout=(3, None))
    except requests.exceptions.ConnectionError:
        print("Internet connection is not available.")
        return None
    if r.status_code == 200:
        d = json.loads(r.text)
        all_vers = list(d["releases"].keys())
        all_vers.sort(key=LooseVersion)
        return all_vers
    else:
        return None


def get_readme(module_name, version=None):
    """
    Get the readme. Use local if available.
    """
    exists_remote = module_exists_remote(module_name, version=version)
    exists_local = module_exists_local(module_name)
    if exists_remote:
        remote_readme = mic.get_remote_readme(module_name)
    else:
        remote_readme = ""
    if exists_local:
        local_info = get_local_module_info(module_name)
        if os.path.exists(local_info.readme_path):
            local_readme = open(local_info.readme_path).read()
        else:
            local_readme = ""
    else:
        local_readme = ""
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


def get_remote_data_version(module_name, version):
    """
    Get the data version to install for a module.
    Return the input version if module_name or version is not found.
    """
    mic.update_remote()
    try:
        manifest_entry = mic.remote[module_name]
    except KeyError:
        return version
    try:
        return manifest_entry["data_versions"][version]
    except KeyError:
        return version


def get_remote_latest_version(module_name):
    """
    Returns latest remotely available version of a module.
    """
    mic.update_remote()
    return mic.remote[module_name]["latest_version"]


def get_remote_manifest():
    if len(mic.remote) == 0:
        mic.update_remote()
    return mic.remote


def get_remote_module_config(module_name):
    conf = mic.get_remote_config(module_name)
    return conf


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


def get_remote_module_infos_of_type(t):
    modules = {}
    mic.update_remote()
    for module_name in mic.remote:
        if mic.remote[module_name]["type"] == t:
            modules[module_name] = mic.remote[module_name]
    return modules


def get_remote_module_readme(module_name, version=None):
    """
    Get the detailed description file about a module as a string.
    """
    return mic.get_remote_readme(module_name, version=version)


au_conf = None
au_conf_file_only = None
def get_system_conf(file_only=False):
    global au_conf
    global au_conf_file_only
    if au_conf is None:
        """
        Get the system config. Fill in the default modules dir if not set.
        """
        if constants.custom_system_conf_path is not None:
            conf = load_yml_conf(constants.custom_system_conf_path)
        elif os.environ.get(constants.system_conf_path_env_key) is not None:
            conf = load_yml_conf(os.environ.get(constants.system_conf_path_env_key))
        else:
            conf = load_yml_conf(constants.system_conf_path)
        au_conf_file_only = conf


        if constants.modules_dir_key not in conf:
            conf[constants.modules_dir_key] = constants.default_modules_dir
        if constants.conf_dir_key not in conf:
            conf[constants.conf_dir_key] = constants.default_conf_dir
        if constants.jobs_dir_key not in conf:
            conf[constants.jobs_dir_key] = constants.default_jobs_dir
        if constants.log_dir_key not in conf:
            conf[constants.log_dir_key] = constants.default_log_dir
        key = "num_input_line_warning_cutoff"
        if key not in conf:
            conf[key] = constants.default_num_input_line_warning_cutoff
        key = "gui_input_size_limit"
        if key not in conf:
            conf[key] = constants.default_settings_gui_input_size_limit
        key = "max_num_concurrent_jobs"
        if key not in conf:
            conf[key] = constants.default_max_num_concurrent_jobs
        key = "max_num_concurrent_annotators_per_job"
        if key not in conf:
            conf[key] = constants.default_max_num_concurrent_annotators_per_job
        if "custom_system_conf" in globals():
            global custom_system_conf
            for k, v in custom_system_conf.items():
                conf[k] = v
        au_conf = conf
        
    if file_only == True:
        return au_conf_file_only
    else:    
        return au_conf


def get_system_conf_info(json=False):
    confpath = constants.system_conf_path
    if os.path.exists(confpath):
        conf = get_system_conf()
        confexists = True
    else:
        conf = {}
        confexists = False
    conf["package_path"] = os.path.dirname(os.path.abspath(__file__))
    if json:
        content = conf
    else:
        content = yaml.dump(conf, default_flow_style=False)
    system_conf_info = {"path": confpath, "exists": confexists, "content": content}
    return system_conf_info


async def get_updatable_async(modules=[], strategy="consensus"):
    update_vers, resolution_applied, resolution_failed = get_updatable(modules=modules, strategy=strategy)
    return [update_vers, resolution_applied, resolution_failed]

def get_updatable(modules=[], strategy="consensus"):
    if strategy not in ("consensus", "force", "skip"):
        raise ValueError('Unknown strategy "{}"'.format(strategy))
    if not modules:
        modules = list_local()
    reqs_by_dep = defaultdict(dict)
    all_versions = {}
    for mname in list_local():
        local_info = get_local_module_info(mname)
        remote_info = get_remote_module_info(mname)
        if remote_info:
            all_versions[mname] = sorted(remote_info.versions, key=LooseVersion)
        req_strings = local_info.conf.get("requires", [])
        reqs = [pkg_resources.Requirement(s) for s in req_strings]
        for req in reqs:
            dep = req.name
            reqs_by_dep[dep][mname] = req
    update_vers = {}
    resolution_applied = {}
    resolution_failed = {}
    for mname in modules:
        if mname not in list_local():
            continue
        local_info = get_local_module_info(mname)
        remote_info = get_remote_module_info(mname)
        reqs = reqs_by_dep[mname]
        versions = all_versions.get(mname, [])
        if not versions:
            continue
        selected_version = versions[-1]
        if (
            selected_version
            and local_info.version
            and LooseVersion(selected_version) <= LooseVersion(local_info.version)
        ):
            continue
        if reqs:
            resolution_applied[mname] = reqs
            if strategy == "force":
                pass
            elif strategy == "skip":
                selected_version = None
            elif strategy == "consensus":
                passing_versions = []
                for version in versions:
                    version_passes = True
                    for requester, requirement in reqs.items():
                        version_passes = version in requirement
                        if not version_passes:
                            break
                    if version_passes:
                        passing_versions.append(version)
                selected_version = passing_versions[-1] if passing_versions else None
        if (
            selected_version
            and local_info.version
            and LooseVersion(selected_version) > LooseVersion(local_info.version)
        ):
            update_data_version = get_remote_data_version(mname, selected_version)
            installed_data_version = get_remote_data_version(mname, local_info.version)
            if (
                update_data_version is not None
                and update_data_version != installed_data_version
            ):
                update_size = remote_info.size
            else:
                update_size = remote_info.code_size
            update_vers[mname] = SimpleNamespace(
                version=selected_version, size=update_size
            )
        else:
            resolution_failed[mname] = reqs
    return update_vers, resolution_applied, resolution_failed


def get_widgets_for_annotator(annotator_name, skip_installed=False):
    """
    Get webviewer widgets that require an annotator. Optionally skip the
    widgets that are already installed.
    """
    linked_widgets = []
    for widget_name in list_remote():
        widget_info = get_remote_module_info(widget_name)
        if widget_info.type == "webviewerwidget":
            widget_config = mic.get_remote_config(widget_name)
            linked_annotator = widget_config.get("required_annotator")
            if linked_annotator == annotator_name:
                if skip_installed and module_exists_local(widget_name):
                    continue
                else:
                    linked_widgets.append(widget_info)
    return linked_widgets


def input_formats():
    formats = set()
    d = os.path.join(get_modules_dir(), "converters")
    if os.path.exists(d):
        fns = os.listdir(d)
        for fn in fns:
            if fn.endswith("-converter"):
                formats.add(fn.split("-")[0])
    return formats


def install_module(
    module_name,
    version=None,
    force_data=False,
    skip_data=False,
    stage_handler=None,
    install_pypi_dependency=False,
    **kwargs,
):
    """
    Installs a module.
    version=None will install the latest version.
    force_data=True will force an update to the data files, even if one is not needed.
    """
    modules_dir = get_modules_dir()
    temp_dir = os.path.join(modules_dir, constants.install_tempdir_name, module_name)
    shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(temp_dir)
    try:
        # Ctrl-c in this func must be caught to delete temp_dir
        def raise_kbi(a, b):
            raise KeyboardInterrupt
        original_sigint = signal.signal(signal.SIGINT, raise_kbi)
        if stage_handler is None:
            stage_handler = InstallProgressHandler(module_name, version)
        if version is None:
            version = get_remote_latest_version(module_name)
            stage_handler.set_module_version(version)
        if hasattr(stage_handler, "install_state") == True:
            install_state = stage_handler.install_state
        else:
            install_state = None
        stage_handler.stage_start("start")
        # Checks and installs pip packages.
        config = mic.get_remote_config(module_name, version=version)
        pypi_deps = config.get("pypi_dependency", [])
        idx = 0
        while idx < len(pypi_deps):
            dep = pypi_deps[idx]
            r = subprocess.run(["pip", "show", dep], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                pypi_deps.remove(dep)
            else:
                idx += 1
        if len(pypi_deps) > 0:
            print(f"Following PyPI dependencies should be met before installing {module_name}.")
            for dep in pypi_deps:
                print(f"- {dep}")
            if install_pypi_dependency:
                print(f"Trying to install required PyPI packages...")
                idx = 0
                while idx < len(pypi_deps):
                    dep = pypi_deps[idx]
                    r = subprocess.run(["pip", "install", dep])
                    if r.returncode == 0:
                        pypi_deps.remove(dep)
                    else:
                        idx += 1
                if len(pypi_deps) > 0:
                    print(f"Following PyPI dependencies could not be installed.")
                    for dep in pypi_deps:
                        print(f"- {dep}")
        if len(pypi_deps) > 0:
            if version is not None:
                print(f"Skipping installation of {module_name}:{version} due to unmet requirement for PyPI packages")
            else:
                print(f"Skipping installation of {module_name} due to unmet requirement for PyPI packages")
        else:
            sys_conf = get_system_conf()
            store_url = sys_conf["store_url"]
            store_path_builder = su.PathBuilder(store_url, "url")
            remote_data_version = get_remote_data_version(module_name, version)
            if module_name in list_local():
                local_info = get_local_module_info(module_name)
                if local_info.has_data:
                    local_data_version = get_remote_data_version(
                        module_name, local_info.version
                    )
                else:
                    local_data_version = None
            else:
                local_data_version = None
            code_url = store_path_builder.module_code(module_name, version)
            zipfile_fname = module_name + ".zip"
            remote_info = get_remote_module_info(module_name)
            if remote_info is not None:
                module_type = remote_info.type
            else:
                # Private module. Fallback to remote config.
                remote_config = mic.get_remote_config(module_name, version)
                module_type = remote_config["type"]
            if install_state:
                if (
                    install_state["module_name"] == module_name
                    and install_state["kill_signal"] == True
                ):
                    raise exceptions.KillInstallException
            zipfile_path = os.path.join(temp_dir, zipfile_fname)
            stage_handler.stage_start("download_code")
            r = su.stream_to_file(
                code_url,
                zipfile_path,
                stage_handler=stage_handler.stage_progress,
                install_state=install_state,
                **kwargs,
            )
            if r.status_code != 200:
                raise (requests.HTTPError(r))
            if install_state:
                if (
                    install_state["module_name"] == module_name
                    and install_state["kill_signal"] == True
                ):
                    raise exceptions.KillInstallException
            stage_handler.stage_start("extract_code")
            zf = zipfile.ZipFile(zipfile_path)
            zf.extractall(temp_dir)
            zf.close()
            if install_state:
                if (
                    install_state["module_name"] == module_name
                    and install_state["kill_signal"] == True
                ):
                    raise exceptions.KillInstallException
            stage_handler.stage_start("verify_code")
            code_manifest_url = store_path_builder.module_code_manifest(
                module_name, version
            )
            code_manifest = yaml.safe_load(su.get_file_to_string(code_manifest_url))
            su.verify_against_manifest(temp_dir, code_manifest)
            os.remove(zipfile_path)
            if install_state:
                if (
                    install_state["module_name"] == module_name
                    and install_state["kill_signal"] == True
                ):
                    raise exceptions.KillInstallException
            data_installed = False
            if (
                not (skip_data)
                and (remote_data_version is not None)
                and (remote_data_version != local_data_version or force_data)
            ):
                data_installed = True
                data_url = store_path_builder.module_data(module_name, remote_data_version)
                data_fname = ".".join([module_name, "data", "zip"])
                data_path = os.path.join(temp_dir, data_fname)
                stage_handler.stage_start("download_data")
                r = su.stream_to_file(
                    data_url,
                    data_path,
                    stage_handler=stage_handler.stage_progress,
                    install_state=install_state,
                    **kwargs,
                )
                if install_state:
                    if (
                        install_state["module_name"] == module_name
                        and install_state["kill_signal"] == True
                    ):
                        raise exceptions.KillInstallException
                if r.status_code == 200:
                    stage_handler.stage_start("extract_data")
                    zf = zipfile.ZipFile(data_path)
                    zf.extractall(temp_dir)
                    zf.close()
                    if install_state:
                        if (
                            install_state["module_name"] == module_name
                            and install_state["kill_signal"] == True
                        ):
                            raise exceptions.KillInstallException
                    stage_handler.stage_start("verify_data")
                    data_manifest_url = store_path_builder.module_data_manifest(
                        module_name, remote_data_version
                    )
                    data_manifest = yaml.safe_load(su.get_file_to_string(data_manifest_url))
                    su.verify_against_manifest(temp_dir, data_manifest)
                    os.remove(data_path)
                    if install_state:
                        if (
                            install_state["module_name"] == module_name
                            and install_state["kill_signal"] == True
                        ):
                            raise exceptions.KillInstallException
                elif r.status_code == 404:
                    # Probably a private module that does not have data
                    pass
                else:
                    raise (requests.HTTPError(r))
            if install_state:
                if (
                    install_state["module_name"] == module_name
                    and install_state["kill_signal"] == True
                ):
                    raise exceptions.KillInstallException
            module_dir = os.path.join(modules_dir, module_type + "s", module_name)
            if os.path.isdir(module_dir):
                # Module being updated
                if data_installed:
                    # Overwrite the whole module
                    shutil.rmtree(module_dir)
                    shutil.move(temp_dir, module_dir)
                else:
                    # Remove all code items
                    for item in os.listdir(module_dir):
                        item_path = os.path.join(module_dir, item)
                        if item != "data":
                            if os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                            else:
                                os.remove(item_path)
                    # Copy in new code items
                    for item in os.listdir(temp_dir):
                        old_path = os.path.join(temp_dir, item)
                        new_path = os.path.join(module_dir, item)
                        if item != "data":
                            shutil.move(old_path, new_path)
                    shutil.rmtree(temp_dir)
            else:
                # Move the module to the right place
                shutil.move(temp_dir, module_dir)
            wf = open(os.path.join(module_dir, "startofinstall"), "w")
            wf.close()
            wf = open(os.path.join(module_dir, "endofinstall"), "w")
            wf.close()
            mic.update_local()
            stage_handler.stage_start("finish")
    except (Exception, KeyboardInterrupt, SystemExit) as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if type(e) == exceptions.KillInstallException:
            stage_handler.stage_start("killed")
        elif type(e) in (KeyboardInterrupt, SystemExit):
            pass
        else:
            raise e
    finally:
        signal.signal(signal.SIGINT, original_sigint)


def install_widgets_for_module(module_name):
    widget_name = "wg" + module_name
    install_module(widget_name)


def list_local():
    """
    Returns a list of locally installed modules.
    """
    modules_dir = get_modules_dir()
    if mic._modules_dir != modules_dir:
        mic._modules_dir = modules_dir
        mic.update_local()
    return sorted(list(mic.get_local().keys()))


def list_remote(force=False):
    """
    Returns a list of remotely available modules.
    """
    mic.update_remote(force=force)
    return sorted(list(mic.remote.keys()))


def load_yml_conf(yml_conf_path):
    """
    Load a .yml file into a dictionary. Return an empty dictionary if file is
    empty.
    """
    with open(yml_conf_path, encoding="utf-8") as f:
        conf = yaml.safe_load(f)
    if conf == None:
        conf = {}
    return conf


def make_example_input(d):
    fn = "example_input"
    ifn = os.path.join(constants.packagedir, fn)
    ofn = os.path.join(d, fn)
    shutil.copyfile(ifn, ofn)
    print(fn + " has been created at " + os.path.abspath(d))


def module_exists_local(module_name):
    """
    Returns True if a module exists locally. False otherwise.
    """
    if module_name in mic.get_local():
        return True
    else:
        if os.path.exists(module_name):
            if os.path.exists(os.path.join(module_name, os.path.basename(module_name) + '.yml')):
                return True
    return False


def module_exists_remote(module_name, version=None, private=False):
    """
    Returns true if a module (optionally versioned) exists in remote
    """
    mic.update_remote()
    found = False
    if module_name in mic.remote:
        if version is None:
            found = True
        else:
            found = version in mic.remote[module_name]["versions"]
    if private and not found:
        sys_conf = get_system_conf()
        path_builder = su.PathBuilder(sys_conf["store_url"], "url")
        if version is None:
            check_url = path_builder.module_dir(module_name)
        else:
            check_url = path_builder.module_version_dir(module_name, version)
        r = requests.get(check_url)
        found = r.status_code != 404 and r.status_code < 500
    return found


def new_annotator(annot_name):
    annot_root = os.path.join(get_modules_dir(), "annotators", annot_name)
    template_root = os.path.join(constants.packagedir, "annotator_template")
    shutil.copytree(template_root, annot_root)
    for dir_path, _, fnames in os.walk(annot_root):
        for old_fname in fnames:
            old_fpath = os.path.join(dir_path, old_fname)
            new_fname = old_fname.replace("annotator_template", annot_name, 1)
            new_fpath = os.path.join(dir_path, new_fname)
            os.rename(old_fpath, new_fpath)
    mic.update_local()


def print_stage_handler(cur_stage, total_stages, cur_size, total_size):
    rem_stages = total_stages - cur_stage
    perc = cur_stage / total_stages * 100
    out = "\r[{1}{2}] {0:.0f}% ".format(perc, "*" * cur_stage, " " * rem_stages)
    sys.stdout.write(out)
    if cur_stage == total_stages:
        print()


def publish_module(module_name, user, password, overwrite=False, include_data=True):
    sys_conf = get_system_conf()
    publish_url = sys_conf["publish_url"]
    mic.update_local()
    local_info = get_local_module_info(module_name)
    if local_info == None:
        print(module_name + " does not exist.")
        return
    check_url = publish_url + "/%s/%s/check" % (module_name, local_info.version)
    r = requests.get(check_url, auth=(user, password))
    if r.status_code != 200:
        print("Cannot upload")
        if r.status_code == 401:
            print("Incorrect username or password")
            exit()
        elif r.status_code == 400:
            err = json.loads(r.text)
            if err["code"] == su.VersionExists.code:
                while True:
                    if overwrite:
                        break
                    resp = input("Version exists. Do you wish to overwrite (y/n)? ")
                    if resp == "y":
                        overwrite = True
                        break
                    if resp == "n":
                        exit()
                    else:
                        print(
                            "Your response ('%s') was not one of the expected responses: y, n"
                            % resp
                        )
                        continue
            else:
                print(err["message"])
                exit()
        elif r.status_code == 500:
            print("Server error")
            exit()
        else:
            print("HTTP response status code: %d" % r.status_code)
            exit()
    zf_name = "%s.%s.zip" % (module_name, local_info.version)
    zf_path = os.path.join(get_modules_dir(), zf_name)
    print("Zipping module and generating checksums")
    zip_builder = su.ModuleArchiveBuilder(zf_path, base_path=local_info.directory)
    for item_name in os.listdir(local_info.directory):
        item_path = os.path.join(local_info.directory, item_name)
        if item_name.endswith("ofinstall"):
            continue
        elif item_name == "__pycache__":
            continue
        elif item_path == local_info.data_dir and not (include_data):
            continue
        else:
            zip_builder.add_item(item_path)
    manifest = zip_builder.get_manifest()
    zip_builder.close()
    post_url = "/".join([publish_url, module_name, local_info.version])
    if overwrite:
        post_url += "?overwrite=1"
    with open(zf_path, "rb") as zf:
        fields = {
            "manifest": ("manifest.json", json.dumps(manifest), "application/json"),
            "archive": (zf_name, zf, "application/octet-stream"),
        }
        print("Uploading to store")
        r = su.stream_multipart_post(
            post_url, fields, stage_handler=print_stage_handler, auth=(user, password)
        )
    if r.status_code != 200:
        print("Upload failed")
        print(r.status_code)
        print(r.text)
    if r.text:
        print(r.text)
    os.remove(zf_path)


def read_system_conf_template():
    with open(constants.system_conf_template_path) as f:
        d = yaml.safe_load(f)
        return d


def ready_resolution_console():
    rs = system_ready()
    if rs:
        return
    print(rs.message)
    if rs.code == ReadyState.MISSING_MD:
        msg = "Current modules directory is {}.\nInput a new modules directory, or press enter to exit.\n> ".format(
            get_modules_dir()
        )
        new_md = input(msg)
        if new_md:
            full_path = os.path.abspath(new_md)
            set_modules_dir(full_path)
            print(full_path)
        else:
            print("Please manually recreate/reattach the modules directory")
            exit()
    exit()


def recursive_update(d1, d2):
    """
    Recursively merge two dictionaries and return a copy.
    d1 is merged into d2. Keys in d1 that are not present in d2 are preserved
    at all levels. The default Dict.update() only preserved keys at the top
    level.
    """
    d3 = copy.deepcopy(d1)  # Copy perhaps not needed. Test.
    for k, v in d2.items():
        if k in d3:
            orig_v = d3[k]
            if isinstance(v, dict):
                if isinstance(orig_v, dict) == False:
                    d3[k] = v
                else:
                    t = recursive_update(d3.get(k, {}), v)
                    d3[k] = t
            else:
                d3[k] = d2[k]
        else:
            d3[k] = v
    return d3


def refresh_cache():
    """
    Refresh the local modules cache
    """
    global mic
    mic = ModuleInfoCache()


def report_issue():
    import webbrowser

    webbrowser.open("http://github.com/KarchinLab/open-cravat/issues")


def search_local(*patterns):
    """
    Return local module names which match any of supplied patterns
    """
    modules_dir = get_modules_dir()
    if mic._modules_dir != modules_dir:
        mic._modules_dir = modules_dir
        mic.update_local()
    matching_names = []
    for module_name in list_local():
        if any([re.fullmatch(pattern, module_name) for pattern in patterns]):
            matching_names.append(module_name)
    return matching_names


def search_remote(*patterns):
    """
    Return remote module names which match any of supplied patterns
    """
    matching_names = []
    for module_name in list_remote():
        if any([re.fullmatch(pattern, module_name) for pattern in patterns]):
            matching_names.append(module_name)
    return matching_names


def send_reset_email(username):
    sys_conf = get_system_conf()
    publish_url = sys_conf["publish_url"]
    reset_pw_url = publish_url + "/reset-password"
    r = requests.post(reset_pw_url, params={"username": username})
    if r.status_code == 500:
        print("Server error")
    if r.text:
        print(r.text)


def send_verify_email(username):
    sys_conf = get_system_conf()
    publish_url = sys_conf["publish_url"]
    reset_pw_url = publish_url + "/verify-email"
    r = requests.post(reset_pw_url, params={"username": username})
    if r.status_code == 500:
        print("Server error")
    if r.text:
        print(r.text)


def set_cravat_conf_prop(key, val):
    conf = get_cravat_conf()
    conf[key] = val
    wf = open(get_main_conf_path(), "w")
    yaml.dump(conf, wf, default_flow_style=False)
    wf.close()


def set_jobs_dir(d):
    update_system_conf_file({"jobs_dir": d})


def set_modules_dir(path, overwrite=False):
    """
    Set the modules_dir to the directory in path.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if not (os.path.isdir(path)):
        os.makedirs(path)
    old_conf_path = get_main_conf_path()
    update_system_conf_file({constants.modules_dir_key: path})
    if not (os.path.exists(get_main_conf_path())):
        if os.path.exists(old_conf_path):
            overwrite_conf_path = old_conf_path
        else:
            overwrite_conf_path = get_main_default_path()
        shutil.copy(overwrite_conf_path, get_main_conf_path())


# return a list of module types (e.g. annotators) in the local install
def show_cravat_conf():
    cravat_conf_info = get_cravat_conf_info()
    print("Configuration file path:", cravat_conf_info["path"])
    print(cravat_conf_info["content"])


def show_cravat_version():
    version = get_current_package_version()
    print(version)


def show_system_conf():
    system_conf_info = get_system_conf_info()
    print("Configuration file path:", system_conf_info["path"])
    print(system_conf_info["content"])


def system_ready():
    if not (os.path.exists(get_modules_dir())):
        return ReadyState(code=ReadyState.MISSING_MD)
    return ReadyState()


def uninstall_module(module_name):
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


def update_system_conf_file(d):
    """
    Recursively update the system config and re-write to disk.
    """
    sys_conf = get_system_conf(file_only=True)
    sys_conf = recursive_update(sys_conf, d)
    write_system_conf_file(sys_conf)
    refresh_cache()
    return True


def write_cravat_conf(cravat_conf):
    confpath = get_main_conf_path()
    wf = open(confpath, "w")
    yaml.dump(cravat_conf, wf, default_flow_style=False)
    wf.close()


def write_system_conf_file(d):
    """
    Fully overwrite the system config file with a new system config.
    """
    global au_conf
    global au_conf_file_only
    with open(constants.system_conf_path, "w") as wf:
        wf.write(yaml.dump(d, default_flow_style=False))
    #Clear the cached system conf information    
    au_conf = None
    au_conf_file_only = None    


def update_mic():
    global mic
    global custom_system_conf
    mic = ModuleInfoCache()


mic = ModuleInfoCache()
