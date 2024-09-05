from sqlite3 import connect

from cravat.webresult import jsonreporter
from cravat.gui.async_utils import run_coroutine_sync

def get_colinfo (dbpath, confpath, filterstring):
    arg_dict = {'dbpath': dbpath, 'module_name': 'jsonreporter', 'reporttypes': 'text'}
    if confpath:
        arg_dict['confpath'] = confpath
    if filterstring:
        arg_dict['filterstring'] = filterstring

    colinfo = run_coroutine_sync(_async_getcolinfo(**arg_dict))
    return colinfo


async def _async_getcolinfo(**kwargs):
    reporter = jsonreporter.Reporter(kwargs)
    try:
        await reporter.prep()
        colinfo = await reporter.get_variant_colinfo()
        await reporter.close_db()
        if reporter.cf is not None:
            await reporter.cf.close_db()
    except:
        await reporter.close_db()
        if reporter.cf is not None:
            await reporter.cf.close_db()
        raise

    return colinfo