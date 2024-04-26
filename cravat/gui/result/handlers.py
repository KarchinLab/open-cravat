import imp
import mimetypes
import os

from flask import request, current_app, jsonify
from sqlite3 import connect

from cravat import admin_util as au
from cravat.gui.cravat_request import file_router, jobid_and_db_path


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
