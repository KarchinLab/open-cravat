from .handlers import *
from cravat.gui.routing import relative_router


def load(application):
    server_router = relative_router("/server", application)
    server_router(r'/login', None, login)
    server_router(r'/logout', None, logout)
    server_router(r'/usersettings', None, get_user_settings)
    server_router(r'/signup', None, signup)
    server_router(r'/checklogged', None, check_logged)