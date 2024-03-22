import os

from cravat import constants, admin_util as au
from cravat.gui.handlers import *


def relative_router(base, application):
    def add_relative_route(route, *args, **kwargs):
        application.add_url_rule(f'{base}{route}', *args, **kwargs)

    return add_relative_route


def load(application, static_router):
    from . import submit, store

    submit.initialize(application)
    store.initialize(application)

    sysconf = au.get_system_conf()
    modules_dir = sysconf[constants.modules_dir_key]
    source_dir = os.path.dirname(au.__file__)

    static_router.add_files(os.path.join(source_dir, "webstore"), prefix="/store")
    static_router.add_files(os.path.join(source_dir, "websubmit"), prefix="/submit")
    static_router.add_files(os.path.join(source_dir, "webresult"), prefix="/result")
    static_router.add_files(os.path.join(modules_dir, "webapps"), prefix="/webapps")

    root_route = relative_router("/", application)
    root_route('/', None, redirect_to_index)
    root_route('/heartbeat', None, heartbeat)
    root_route("/issystemready", None, is_system_ready)
