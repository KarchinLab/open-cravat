#import os
#packagedir = os.path.dirname(__file__)
#from .annotator_options import AnnotatorOptions
#from .inout import CravatReader
#from .inout import CravatWriter
#from .inout import ColumnDefinition
from .base_converter import BaseConverter
from .base_annotator import BaseAnnotator
from .base_mapper import BaseMapper
from .base_postaggregator import BasePostAggregator
from .cravat_report import CravatReport
from .exceptions import *
from . import util
from . import admin_util
from .config_loader import ConfigLoader
from . import constants
from .cravat_filter import CravatFilter
#from .store_utils import ProgressStager
#from .webresult.webresult import *
#from .webstore.webstore import *
from .cravat_class import Cravat

def get_annotator_for_api (module_name):
    import os
    script_path = admin_util.get_annotator_script_path(module_name)
    ModuleClass = util.load_class('CravatAnnotator', script_path)
    module = ModuleClass(None, None, for_api=True)
    module.annotator_name = os.path.basename(script_path).rstrip('.py')
    module.annotator_dir = os.path.dirname(script_path)
    module.data_dir = os.path.join(module.annotator_dir, 'data')
    module._open_db_connection()
    module.setup()
    return module
