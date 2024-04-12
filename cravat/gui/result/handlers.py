from flask import request, current_app, jsonify
from sqlite3 import connect

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

def get_variant_cols():
    queries = request.values
    job_id, dbpath = jobid_and_db_path()

    confpath = queries.get('confpath', None)
    filterstring = queries.get('filter', None)

    data = {
        'data': {},
        'stat': {},
        'status': {},
        'columns': {}
    }

    colinfo = get_colinfo(dbpath, confpath, filterstring)

    if 'variant' in colinfo:
        data['columns']['variant'] = get_colmodel('variant', colinfo)

    if 'gene' in colinfo:
        data['columns']['gene'] = get_colmodel('gene', colinfo)

    return jsonify(data)