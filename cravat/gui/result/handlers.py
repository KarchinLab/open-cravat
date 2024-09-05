import json
import mimetypes
import os

from flask import request, current_app, jsonify
from sqlite3 import connect

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