from functools import wraps
from sqlite3 import connect

from flask import g

from cravat.gui import admin
from cravat.gui.cravat_request import jobid_and_db_path

def with_job_id_and_path(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        job_id, dbpath = jobid_and_db_path()
        return fn(job_id=job_id, dbpath=dbpath, *args, **kwargs)

    return wrapper

def with_job_database(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        job_id, dbpath = jobid_and_db_path()
        if dbpath is None:
            return fn(db=None, *args, **kwargs)
        else:
            with connect(dbpath) as db:
                return fn(db=db, *args, **kwargs)

    return wrapper

def require_multiuser(multiuser_error='no multiuser mode'):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if g.is_multiuser:
                return fn(*args, **kwargs)
            else:
                return multiuser_error

        return wrapper
    return decorator

def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if admin.is_admin_loggedin():
            return fn(*args, **kwargs)
        else:
            return 'no admin'

    return wrapper
