from sqlite3 import connect

def table_exists (cursor, table):
    q = 'select name from sqlite_master where type="table" and ' +\
        'name="' + table + '"'
    cursor.execute(q)
    r = cursor.fetchone()

    return r is not None