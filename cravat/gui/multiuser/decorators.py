from functools import wraps
from .db import AdminDb

def with_admin_db(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        admin_db = AdminDb()
        return fn(admin_db, *args, **kwargs)

    return wrapper
