from . import routes
from .db import AdminDb


def initialize(application):
    admindb = AdminDb()

    application.secret_key = admindb.secret_key
    routes.load(application)


