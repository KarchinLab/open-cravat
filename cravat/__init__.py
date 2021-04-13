def raise_break(signal_number, stack_frame):
    import os
    import platform
    import psutil

    pl = platform.platform()
    if pl.startswith("Windows"):
        pid = os.getpid()
        ppid = os.getppid()
        for child in psutil.Process(pid).children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        os.kill(pid, signal.SIGTERM)
    elif pl.startswith("Linux"):
        pid = os.getpid()
        ppid = os.getppid()
        for child in psutil.Process(pid).children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        os.kill(pid, signal.SIGTERM)
    elif pl.startswith("Darwin") or pl.startswith("macOS"):
        pid = os.getpid()
        ppid = os.getppid()
        for child in psutil.Process(pid).children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        os.kill(pid, signal.SIGTERM)


import signal

signal.signal(signal.SIGINT, raise_break)

from .base_converter import BaseConverter
from .base_annotator import BaseAnnotator
from .base_mapper import BaseMapper
from .base_postaggregator import BasePostAggregator
from .base_commonmodule import BaseCommonModule
from .cravat_report import CravatReport, run_reporter
from .exceptions import *
from . import util
from . import admin_util
from .config_loader import ConfigLoader
from . import constants
from .cravat_filter import CravatFilter
from .cravat_class import Cravat
from .cravat_class import run_cravat_job as run
from .util import get_ucsc_bins, reverse_complement, translate_codon, switch_strand
from .constants import crx_def

wgs = None


def get_live_annotator(module_name):
    try:
        import os

        ModuleClass = get_module(module_name)
        module = ModuleClass(input_file="__dummy__", live=True)
        # module.module_name = module_name
        module.annotator_name = module_name
        # module.module_dir = os.path.dirname(script_path)
        module.annotator_dir = os.path.dirname(module.script_path)
        module.data_dir = os.path.join(module.module_dir, "data")
        module._open_db_connection()
        # module.conf = config_loader.get_module_conf(module_name)
        module.setup()
    except:
        print("    module loading error: {}".format(module.module_name))
        import traceback

        traceback.print_exc()
        return None
    return module


def get_live_mapper(module_name):
    try:
        import os

        ModuleClass = get_module(module_name)
        module = ModuleClass(
            {
                "script_path": os.path.abspath(ModuleClass.script_path),
                "input_file": "__dummy__",
                "live": True,
            }
        )
        module.base_setup()
    except Exception as e:
        print("    module loading error: {}".format(module_name))
        import traceback

        traceback.print_exc()
        return None
    return module


def get_module(module_name):
    try:
        import os

        config_loader = ConfigLoader()
        module_info = admin_util.get_local_module_info(module_name)
        script_path = module_info.script_path
        ModuleClass = util.load_class(script_path)
        ModuleClass.script_path = script_path
        ModuleClass.module_name = module_name
        ModuleClass.module_dir = os.path.dirname(script_path)
        ModuleClass.conf = config_loader.get_module_conf(module_name)
        return ModuleClass
    except Exception as e:
        print("    module loading error: {}".format(module_name))
        import traceback

        traceback.print_exc()
        return None


def get_wgs_reader(assembly="hg38"):
    ModuleClass = get_module(assembly + "wgs")
    if ModuleClass is None:
        wgs = None
    else:
        wgs = ModuleClass()
        wgs.setup()
    return wgs


class LiveAnnotator:
    def __init__(self, mapper="hg38", annotators=[]):
        self.live_annotators = {}
        self.load_live_modules(mapper, annotators)
        self.variant_uid = 1

    def load_live_modules(self, mapper, annotator_names):
        self.live_mapper = get_live_mapper(mapper)
        for module_name in admin_util.mic.local.keys():
            if module_name in annotator_names:
                module = admin_util.mic.local[module_name]
                if "secondary_inputs" in module.conf:
                    continue
                annotator = get_live_annotator(module.name)
                if annotator is None:
                    continue
                self.live_annotators[module.name] = annotator

    def clean_annot_dict(self, d):
        keys = d.keys()
        for key in keys:
            value = d[key]
            if value == "" or value == {}:
                d[key] = None
            elif type(value) is dict:
                d[key] = self.clean_annot_dict(value)
        if type(d) is dict:
            all_none = True
            for key in keys:
                if d[key] is not None:
                    all_none = False
                    break
            if all_none:
                d = None
        return d

    def annotate(self, crv):
        from .inout import AllMappingsParser
        from cravat.constants import all_mappings_col_name

        if "uid" not in crv:
            crv["uid"] = self.variant_uid
            self.variant_uid += 1
        response = {}
        crx_data = self.live_mapper.map(crv)
        crx_data = self.live_mapper.live_report_substitute(crx_data)
        crx_data["tmp_mapper"] = AllMappingsParser(crx_data[all_mappings_col_name])
        for k, v in self.live_annotators.items():
            try:
                annot_data = v.annotate(input_data=crx_data)
                annot_data = v.live_report_substitute(annot_data)
                if annot_data == "" or annot_data == {}:
                    annot_data = None
                elif type(annot_data) is dict:
                    annot_data = self.clean_annot_dict(annot_data)
                response[k] = annot_data
            except Exception as e:
                import traceback

                traceback.print_exc()
                response[k] = None
        del crx_data["tmp_mapper"]
        response["base"] = crx_data
        return response
