from sqlite3 import connect

from cravat.webresult import jsonreporter
from cravat.gui.async_utils import run_coroutine_sync

def get_colinfo (dbpath, confpath, filterstring):
    arg_dict = {'dbpath': dbpath, 'module_name': 'jsonreporter', 'reporttypes': ['text']}
    if confpath:
        arg_dict['confpath'] = confpath
    if filterstring:
        arg_dict['filterstring'] = filterstring

    reporter = jsonreporter.Reporter(arg_dict)
    try:
        reporter.prep()
        colinfo = reporter.get_variant_colinfo()
        reporter.close_db()
        if reporter.cf is not None:
            reporter.cf.close_db()
    except:
        reporter.close_db()
        if reporter.cf is not None:
            reporter.cf.close_db()
        raise

    return colinfo
