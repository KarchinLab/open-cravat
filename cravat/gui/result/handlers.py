import json
import mimetypes
import os

from flask import request, current_app, jsonify
from sqlite3 import connect

from numpy.f2py.crackfortran import endifs

from cravat import admin_util as au
from cravat.constants import base_smartfilters
from cravat.gui.cravat_request import jobid_and_db_path
from cravat.gui.legacy import webresult
from cravat.gui.db import table_exists

from .db import get_colinfo

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

def _first_result_if_table_exists(connection, table, query):
    cursor = connection.cursor()
    if table_exists(cursor, table):
        cursor.execute(query)
        return cursor.fetchone()

    cursor.close()
    return None