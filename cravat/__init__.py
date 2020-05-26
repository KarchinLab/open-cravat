try:
    from .base_converter import BaseConverter
    from .base_annotator import BaseAnnotator
    from .base_mapper import BaseMapper
    from .base_postaggregator import BasePostAggregator
    from .base_commonmodule import BaseCommonModule
    from .cravat_report import CravatReport
    from .exceptions import *
    from . import util
    from . import admin_util
    from .config_loader import ConfigLoader
    from . import constants
    from .cravat_filter import CravatFilter
    from .cravat_class import Cravat
    from .cravat_class import run_cravat_job as run
    from .util import get_ucsc_bins, reverse_complement, translate_codon, more_severe_so, switch_strand
    from .constants import crx_def
except KeyboardInterrupt:
    import sys
    sys.exit(1)

wgs = None

def get_live_annotator (module_name):
    try:
        import os
        ModuleClass = get_module(module_name)
        module = ModuleClass(None, None, live=True)
        #module.module_name = module_name
        module.annotator_name = module_name
        #module.module_dir = os.path.dirname(script_path)
        module.annotator_dir = os.path.dirname(module.script_path)
        module.data_dir = os.path.join(module.module_dir, 'data')
        module._open_db_connection()
        #module.conf = config_loader.get_module_conf(module_name)
        module.setup()
    except:
        print('    module loading error: {}'.format(module.module_name))
        import traceback
        traceback.print_exc()
        return None
    return module

def get_live_mapper (module_name):
    try:
        import os
        ModuleClass = get_module(module_name)
        module = ModuleClass(None, None, live=True)
        #module.module_name = module_name
        module.mapper_name = module_name
        #module.module_dir = os.path.dirname(module.script_path)
        module.mapper_dir = os.path.dirname(module.script_path)
        module.data_dir = os.path.join(module.module_dir, 'data')
        #module.conf = config_loader.get_module_conf(module_name)
        module.setup()
    except Exception as e:
        print('    module loading error: {}'.format(module_name))
        import traceback
        traceback.print_exc()
        return None
    return module

def get_module (module_name):
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
        print('    module loading error: {}'.format(module_name))
        import traceback
        traceback.print_exc()
        return None

def get_wgs_reader (assembly='hg38'):
    ModuleClass = get_module(assembly + 'wgs')
    if ModuleClass is None:
        wgs = None
    else:
        wgs = ModuleClass()
        wgs.setup()
    return wgs
