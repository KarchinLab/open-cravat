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
from cravat.gui.decorators import with_job_id_and_path, with_job_database

from .db import get_colinfo
from ..async_utils import run_coroutine_sync


@with_job_database
def get_result_levels(db):
    if db is None:
        content = ['NODB']
    else:
        cursor = db.cursor()
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

@with_job_id_and_path
def get_variant_cols(job_id, dbpath):
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

@with_job_database
def get_smartfilters(db):
    cursor = db.cursor()
    sfs = {'base': base_smartfilters}

    sf_table = 'smartfilters'

    if table_exists(cursor, sf_table):
        q = 'select name, definition from {};'.format(sf_table)
        cursor.execute(q)
        r = cursor.fetchall()
        sfs = {**sfs, **{ k:json.loads(v) for (k,v) in r }}

    cursor.close()

    return jsonify(sfs)

@with_job_database
def get_samples(db):
    cursor = db.cursor()

    sample_table = 'sample'
    samples = []
    if table_exists(cursor, sample_table):
        q = f'select distinct base__sample_id from {sample_table};'
        cursor.execute(q)
        rows = cursor.fetchall()
        samples = [r[0] for r in rows]
    cursor.close()

    return jsonify(samples)

@with_job_database
def load_filter_setting(db):
    queries = request.values
    name = queries['name']

    q = 'select viewersetup from viewersetup where datatype="filter" and name="' + name + '"'
    r = _first_result_if_table_exists(db, 'viewersetup', q)

    content = {"filterSet": {}}
    if r is not None:
        data = r[0]
        content = json.loads(data)

    return jsonify(content)

@with_job_database
def load_layout_setting(db):
    queries = request.values
    name = queries['name']

    q = 'select viewersetup from viewersetup where datatype="layout" and name="' + name + '"'
    r = _first_result_if_table_exists(db, 'viewersetup', q)

    content = {"widgetSettings": {}}
    if r is not None:
        data = r[0]
        content = json.loads(data)

    return jsonify(content)

@with_job_database
def get_filter_save_names(db):
    cursor = db.cursor()
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

    return jsonify(content)

@with_job_database
def get_status(db):
    cursor = db.cursor()

    q = 'select * from info where colkey not like "\_%" escape "\\"'
    cursor.execute(q)
    content = {}
    for row in cursor.fetchall():
        content[row[0]] = row[1]

    cursor.close()

    return jsonify(content)

@with_job_id_and_path
def get_count(job_id, dbpath):
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

@with_job_id_and_path
def get_result(job_id, dbpath):
    from cravat.gui.legacy import jsonreporter

    queries = request.values

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

@with_job_id_and_path
def serve_runwidget(widget_module, job_id, dbpath):
    queries = request.values
    path = 'wg' + widget_module

    if ('dbpath' not in queries or queries['dbpath'] == '') and dbpath is not None:
        new_queries = queries.copy()
        new_queries['dbpath'] = dbpath
        queries = new_queries

    m = _load_cravat_module(path)

    content = run_coroutine_sync(m.get_data(queries))
    return jsonify(content)

@with_job_id_and_path
def serve_runwidget_post(widget_module, job_id, dbpath):
    # NOTE: This method seems to not be called either in the OpenCravat or OpenCravat modules code
    queries = request.values
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

@with_job_database
def save_layout_setting(db):
    queries = request.values

    name = queries['name']
    savedata = queries['savedata']

    cursor = db.cursor()

    table = 'viewersetup'
    exists = table_exists(cursor, table)
    if not exists:
        q = 'create table ' + table + ' (datatype text, name text, viewersetup text, unique (datatype, name))'
        cursor.execute(q)

    try:
        q = 'replace into ' + table + ' values ("layout", "' + name + '", \'' + savedata + '\')'
        cursor.execute(q)
        db.commit()
    finally:
        cursor.close()

    content = 'saved'
    return jsonify(content)

@with_job_database
def save_filter_setting(db):
    queries = request.values

    name = queries['name']
    savedata = queries['savedata']


    cursor = db.cursor()

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
            db.commit()

        q = 'replace into viewersetup values ("filter", ?, ?)'
        cursor.execute(q, (name, savedata))
        db.commit()
    finally:
        cursor.close()

    content = 'saved'
    return jsonify(content)

@with_job_database
def jobpackage(db):
    try:
        queries = request.values

        packageName = queries['packagename']
        cursor = db.cursor()

        # check for overwrite setting
        overwrite = True

        q = 'select colval from info where colkey = "_annotators"'
        cursor.execute(q)
        r = cursor.fetchone()
        annots = r[0]

        annotators = []
        for a in annots.split(','):
            if a.startswith('extra_vcf_info') or a.startswith('original_input'):
                continue
            # Currently throwing away version number - preserve it??
            annotators.append(a.split(':')[0])

        reports = []
        q = 'select colval from info where colkey = "_reports"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r is not None:
            for rep in r[0].split(','):
                reports.append(rep)

        filter = ""
        q = 'select viewersetup from viewersetup where datatype = "filter" and name = "quicksave-name-internal-use"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r is not None:
            filter = r[0]

        viewer = ""
        q = 'select viewersetup from viewersetup where datatype = "layout" and name = "quicksave-name-internal-use"'
        cursor.execute(q)
        r = cursor.fetchone()
        if r is not None:
            viewer = r[0]

        name = packageName
        package_conf = {}
        package_conf['type'] = 'package'
        package_conf['description'] = 'Package ' + name + " created from user job with --saveaspackage"
        package_conf['title'] = name
        package_conf['version'] = '1.0'
        package_conf['requires'] = annotators.copy()

        run = {}
        run['annotators'] = annotators.copy()
        run['reports'] = reports
        if filter != "":
            run['filter'] = filter
        if viewer != "":
            run['viewer'] = viewer

        package_conf['run'] = run

        au.create_package(name, package_conf, overwrite)

        print(
            "Successfully created package " + name + ".  Package can now be used to run jobs or published for other users.")

    except (Exception, ValueError) as e:
        print("Error - " + str(e))

    content = 'saved'
    return jsonify(content)

@with_job_database
def delete_layout_setting(db):
    queries = request.values
    name = queries['name']

    cursor = db.cursor()
    if table_exists(cursor, 'viewersetup'):
        q = 'DELETE FROM viewersetup WHERE datatype="layout" and name=?'
        cursor.execute(q, (name,))

    db.commit()
    cursor.close()

    content = {}
    return jsonify(content)

@with_job_database
def get_layout_save_names(db):
    cursor = db.cursor()

    table = 'viewersetup'
    content = []
    r = table_exists(cursor, table)
    if r:
        q = 'select distinct name from viewersetup where datatype="layout"'
        cursor.execute(q)
        rs = cursor.fetchall()
        content = [r[0] for r in rs]
    cursor.close()
    return jsonify(content)

@with_job_database
def rename_layout_setting(db):
    queries = request.values

    name = queries['name']
    new_name = queries['newname']

    cursor = db.cursor()
    table = 'viewersetup'
    r = table_exists(cursor, table)
    if r:
        q = 'update viewersetup set name=? where datatype="layout" and name=?'
        cursor.execute(q, (new_name, name))
    db.commit()
    cursor.close()

    content = {}
    return jsonify(content)

@with_job_database
def delete_filter_setting(db):
    queries = request.values

    name = queries['name']
    cursor = db.cursor()

    table = 'viewersetup'
    r = table_exists(cursor, table)
    if r:
        q = 'delete from viewersetup where name=? and datatype="filter"'
        cursor.execute(q, (name, ))
        db.commit()
        content = 'deleted'
    else:
        content = 'no such table'
    cursor.close()

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