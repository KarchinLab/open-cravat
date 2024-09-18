import json
import mimetypes
import os
import sys
import time

from flask import request, current_app, jsonify
from importlib import util as importlib_util
from sqlite3 import connect

from cravat import admin_util as au
from cravat.cravat_filter import CravatFilter
from cravat.constants import base_smartfilters
from cravat.gui.cravat_request import jobid_and_db_path
from cravat.gui.legacy import webresult
from cravat.gui.db import table_exists

from .db import get_colinfo
from ..async_utils import run_coroutine_sync


def get_result_levels():
    job_id, dbpath = jobid_and_db_path()

    if dbpath is None:
        content = ['NODB']
    else:
        conn = connect(dbpath)
        cursor = conn.cursor()
        sql = 'select name from sqlite_master where type="table" and ' +\
            'name like "%_header"'
        cursor.execute(sql)
        ret = cursor.fetchall()

        if len(ret) > 0:
            content = [v[0].split('_')[0] for v in ret]
            content.insert(0, 'info')
            content.insert(1,'filter')
        else:
            content = []

        content.remove('sample')
        content.remove('mapping')
        cursor.close()
        conn.close()

    return jsonify(content)


def serve_widgetfile(module, filename):
    filepath = os.path.join(
        au.get_modules_dir(),
        'webviewerwidgets',
         module,
         filename
        )

    if os.path.exists(filepath):
        ct, encoding = mimetypes.guess_type(str(filepath))
        if not ct:
            ct = "application/octet-stream"

        def file_stream():
            with open(filepath) as f:
                for line in f:
                    yield line
        headers = {
            "Content-Type": ct,
            "Cache-Control": "no-cache"
        }

        if encoding:
            headers['Content-Encoding'] = encoding

        return file_stream(), headers

def get_variant_cols():
    job_id, dbpath = jobid_and_db_path()
    queries = request.values

    confpath = queries.get('confpath', None)
    filterstring = queries.get('filter', None)

    data = {'data': {}, 'stat': {}, 'status': {}, 'columns': {}}

    colinfo = get_colinfo(dbpath, confpath, filterstring)

    if 'variant' in colinfo:
        data['columns']['variant'] = webresult.get_colmodel('variant', colinfo)
    if 'gene' in colinfo:
        data['columns']['gene'] = webresult.get_colmodel('gene', colinfo)
    if 'sample' in colinfo:
        data['columns']['sample'] = webresult.get_colmodel('sample', colinfo)

    return jsonify(data)

def get_widgets():
    content = []
    modules = au.get_local_module_infos_of_type('webviewerwidget')
    content = [{'name': module_name,
                'title': modules[module_name].title,
                'required_annotator': modules[module_name].conf.get('required_annotator', module_name[2:]),
                'helphtml_exists': modules[module_name].helphtml_exists}
               for module_name
               in modules]

    return jsonify(content)

def get_smartfilters():
    job_id, dbpath = jobid_and_db_path()

    sfs = {'base': base_smartfilters}
    conn = connect(dbpath)
    cursor = conn.cursor()

    sf_table = 'smartfilters'

    if table_exists(cursor, sf_table):
        q = 'select name, definition from {};'.format(sf_table)
        cursor.execute(q)
        r = cursor.fetchall()
        sfs = {**sfs, **{ k:json.loads(v) for (k,v) in r }}

    cursor.close()
    conn.close()

    return jsonify(sfs)

def get_samples():
    job_id, dbpath = jobid_and_db_path()

    conn = connect(dbpath)
    cursor = conn.cursor()

    sample_table = 'sample'
    samples = []
    if table_exists(cursor, sample_table):
        q = f'select distinct base__sample_id from {sample_table};'
        cursor.execute(q)
        rows = cursor.fetchall()
        samples = [r[0] for r in rows]
    cursor.close()
    conn.close()

    return jsonify(samples)

def load_filter_setting():
    job_id, dbpath = jobid_and_db_path()
    queries = request.values
    name = queries['name']

    conn = connect(dbpath)
    q = 'select viewersetup from viewersetup where datatype="filter" and name="' + name + '"'
    r = _first_result_if_table_exists(conn, 'filterSet', q)

    content = {"filterSet": {}}
    if r is not None:
        data = r[0]
        content = json.loads(data)

    conn.close()
    return jsonify(content)

def load_layout_setting():
    job_id, dbpath = jobid_and_db_path()
    queries = request.values
    name = queries['name']

    conn = connect(dbpath)
    q = 'select viewersetup from viewersetup where datatype="layout" and name="' + name + '"'
    r = _first_result_if_table_exists(conn, 'viewersetup', q)

    content = {"widgetSettings": {}}
    if r is not None:
        data = r[0]
        content = json.loads(data)

    conn.close()
    return jsonify(content)

def get_filter_save_names():
    job_id, dbpath = jobid_and_db_path()

    conn = connect(dbpath)
    cursor = conn.cursor()
    content = []

    try:
        if table_exists(cursor, 'viewersetup'):
            q = 'select distinct name from viewersetup where datatype="filter"'
            cursor.execute(q)
            rs = cursor.fetchall()
            content = [r[0] for r in rs]
    except:
        raise
    finally:
        cursor.close()
        conn.close()

    return jsonify(content)

def get_status():
    job_id, dbpath = jobid_and_db_path()

    conn = connect(dbpath)
    cursor = conn.cursor()

    q = 'select * from info where colkey not like "\_%" escape "\\"'
    cursor.execute(q)
    content = {}
    for row in cursor.fetchall():
        content[row[0]] = row[1]

    cursor.close()
    conn.close()

    return jsonify(content)

def get_count():
    job_id, dbpath = jobid_and_db_path()
    queries = request.values

    tab = queries['tab']
    filterstring = queries.get('filter', None)

    cf = CravatFilter.create(dbpath=dbpath,
                             mode='sub',
                             filterstring=filterstring)
    dbbasename = os.path.basename(dbpath)
    print('calling count for {}'.format(dbbasename))
    t = time.time()
    n = cf.exec_db(cf.getcount, level=tab)
    cf.close_db()
    t = round(time.time() - t, 3)
    print('count obtained from {} in {}s'.format(dbbasename, t))
    content = {'n': n}
    return jsonify(content)

def get_result():
    from cravat.gui.legacy import jsonreporter

    queries = request.values
    job_id, dbpath = jobid_and_db_path()

    dbname = os.path.basename(dbpath)
    tab = queries['tab']

    print('(Getting result of [{}]:[{}]...)'.format(dbname, tab))
    start_time = time.time()
    filterstring = queries.get('filter', None)
    confpath = queries.get('confpath', None)

    arg_dict = {'dbpath': dbpath,
                'module_name': 'jsonreporter',
                'nogenelevelonvariantlevel': True,
                'reporttypes': ['text']}
    if confpath is not None:
        arg_dict['confpath'] = confpath
    if filterstring is not None:
        arg_dict['filterstring'] = filterstring
    separatesample = queries.get('separatesample', False)
    separatesample = separatesample == 'true' # boolean coercion
    if separatesample:
        arg_dict['separatesample'] = True
    reporter = jsonreporter.Reporter(arg_dict)

    reporter.prep()
    data = reporter.run(tab=tab)
    data['modules_info'] = _get_modules_info()

    content = {}
    content['stat'] = {'rowsreturned': True,
                   'wherestr':'',
                   'filtered': True,
                   'filteredresultmessage': '',
                   'maxnorows': 100000,
                   'norows': data['info']['norows']}
    content['columns'] = _get_colmodel(tab, data['colinfo'])
    content["data"] = _get_datamodel(data[tab])
    content["status"] = "normal"
    content['modules_info'] = data['modules_info']
    content['warning_msgs'] = data['warning_msgs']
    t = round(time.time() - start_time, 3)
    print('Done getting result of [{}][{}] in {}s'.format(dbname, tab, t))
    return jsonify(content)

def serve_runwidget(widget_module):
    queries = request.values
    job_id, dbpath = jobid_and_db_path()
    path = 'wg' + widget_module

    if ('dbpath' not in queries or queries['dbpath'] == '') and dbpath is not None:
        new_queries = queries.copy()
        new_queries['dbpath'] = dbpath
        queries = new_queries

    m = _load_cravat_module(path)

    content = run_coroutine_sync(m.get_data(queries))
    return jsonify(content)

def serve_runwidget_post(widget_module):
    # NOTE: This method seems to not be called either in the OpenCravat or OpenCravat modules code
    queries = request.values
    job_id, dbpath = jobid_and_db_path()
    path = 'wg' + widget_module

    new_queries = {}
    for k in queries:
        val = queries[k]
        if val == '':
            val = '""'
        elif val.startswith('{') and val.endswith('}') or \
             val.startswith('[') and val.endswith(']'):
            pass
        else:
            val = '"' + val + '"'
        if sys.platform == 'win32':
            val = val.replace('\\', '\\\\')
        val = json.loads(val)
        new_queries[k] = val

    queries = new_queries

    if ('dbpath' not in queries or queries['dbpath'] == '') and dbpath is not None:
        new_queries = queries.copy()
        new_queries['dbpath'] = dbpath
        queries = new_queries

    m = _load_cravat_module(path)

    content = run_coroutine_sync(m.get_data(queries))
    return jsonify(content)

def save_layout_setting():
    queries = request.values
    job_id, dbpath = jobid_and_db_path()

    name = queries['name']
    savedata = queries['savedata']

    conn = connect(dbpath)
    cursor = conn.cursor()

    table = 'viewersetup'
    exists = table_exists(cursor, table)
    if not exists:
        q = 'create table ' + table + ' (datatype text, name text, viewersetup text, unique (datatype, name))'
        cursor.execute(q)

    try:
        q = 'replace into ' + table + ' values ("layout", "' + name + '", \'' + savedata + '\')'
        cursor.execute(q)
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    content = 'saved'
    return jsonify(content)

def save_filter_setting():
    queries = request.values
    job_id, dbpath = jobid_and_db_path()

    name = queries['name']
    savedata = queries['savedata']

    conn = connect(dbpath)
    cursor = conn.cursor()

    table = 'viewersetup'
    r = table_exists(cursor, table)
    if not r:
        q = 'create table ' + table + ' (datatype text, name text, viewersetup text, unique (datatype, name))'
        cursor.execute(q)

    try:
        q = 'select * from viewersetup where datatype="filter" and name=?'
        cursor.execute(q, (name,))

        r = cursor.fetchone()
        if r is not None:
            q = 'delete from viewersetup where datatype="filter" and name=?'
            cursor.execute(q, (name,))
            conn.commit()

        q = 'replace into viewersetup values ("filter", ?, ?)'
        cursor.execute(q, (name, savedata))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    content = 'saved'
    return jsonify(content)

def _load_cravat_module(path):
    info = au.get_local_module_info(path)
    spec = importlib_util.spec_from_file_location(path, info.script_path)
    m = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _first_result_if_table_exists(connection, table, query):
    cursor = connection.cursor()
    if table_exists(cursor, table):
        cursor.execute(query)
        return cursor.fetchone()

    cursor.close()
    return None

def _get_modules_info():
    job_id, dbpath = jobid_and_db_path()

    conn = connect(dbpath)
    cursor = conn.cursor()

    q = 'select colval from info where colkey="_annotator_desc"'
    cursor.execute(q)
    r = cursor.fetchone()

    if r is None or r[0] == '{}':
        content = {}
    else:
        s = r[0].strip('{').strip('}')
        toks = s.split("', '")
        d = {}
        for tok in toks:
            t2 = tok.split(':')
            k = t2[0].strip().strip("'").replace("'", "\'")
            v = t2[1].strip().strip("'").replace("'", "\'")
            d[k] = v
        content = d

    cursor.close()
    conn.close()
    return content

def _get_colmodel(tab, colinfo):
    colModel = []
    groupkeys_ordered = []
    groupnames = {}
    for d in colinfo[tab]['colgroups']:
        groupnames[d['name']] = [d['displayname'], d['count']]
        groupkeys_ordered.append(d['name'])
    dataindx = 0
    for groupkey in groupkeys_ordered:
        [grouptitle, col_count] = groupnames[groupkey]
        columngroupdef = {'name': groupkey, 'title': grouptitle, 'colModel': []}
        startidx = dataindx
        endidx = startidx + col_count
        genesummary_present = False
        for d in colinfo[tab]['columns'][startidx:endidx]:
            cats = d['col_cats']
            column = {
                "col": d['col_name'],
                'colgroupkey': groupkey,
                'colgroup': grouptitle,
                "title": d['col_title'],
                "align":"center",
                "dataIndx": dataindx,
                "retfilt":False,
                "retfilttype":"None",
                "multiseloptions":[],
                'reportsub': d['reportsub'] if 'reportsub' in d else {},
                'categories': cats,
                'width': d['col_width'],
                'desc': d['col_desc'],
                'type': d['col_type'],
                'hidden': d['col_hidden'],
                'default_hidden': d['col_hidden'],
                'ctg': d['col_ctg'],
                'filterable': d['col_filterable'],
                'link_format': d.get('link_format'),
                }
            if d['col_type'] == 'string':
                column['align'] = 'left'
                if d['col_ctg'] == 'single':
                    column['filter'] = {
                        'type': 'select',
                        'attr': 'multiple',
                        'condition': 'equal',
                        'options': cats,
                        'listeners': ['change']}
                    column['retfilt'] = True
                    column['retfilttype'] = 'select'
                    column['multiseloptions'] = cats
                elif d['col_ctg'] == 'multi':
                    column['filter'] = {
                        'type': 'select',
                        'attr': 'multiple',
                        'condition': 'contain',
                        'options': cats,
                        'listeners': ['change']}
                    column['retfilt'] = True
                    column['retfilttype'] = 'select'
                    column['multiseloptions'] = cats
                else:
                    column['filter'] = {
                        "type":"textbox",
                        "condition":"contain",
                        "listeners":["keyup"]}
                    column['retfilt'] = True
                    column['retfilttype'] = 'regexp'
                    column['multiseloptions'] = []
            elif d['col_type'] == 'float' or d['col_type'] == 'int':
                column['align'] = 'right'
                column['filter'] = {
                    "type":"textbox",
                    "condition":"between",
                    "listeners":["keyup"]}
                column['retfilt'] = True
                column['retfilttype'] = 'between'
                column['dataType'] = 'float'
                column['multiseloptions'] = []
            if 'col_genesummary' in d and d['col_genesummary'] == True:
                genesummary_present = True
            columngroupdef['colModel'].append(column)
            dataindx += 1
        if genesummary_present:
            columngroupdef['genesummary'] = True
        colModel.append(columngroupdef)
    return colModel

def _get_datamodel(data):
    ret = []
    for row in data:
        ret.append(list(row))
    return ret