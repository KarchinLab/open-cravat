import importlib
import os

from flask import request, jsonify
from importlib import util as importlib_util

from cravat import admin_util as au
from cravat.gui.cravat_request import HTTP_NOT_FOUND
from .async_utils import run_coroutine_sync


def webapp_proxy_handler():
    webapps_dir = os.path.join(au.get_modules_dir(), "webapps")
    module_handlers = {}

    if not os.path.exists(webapps_dir):
        os.mkdir(webapps_dir)

    module_names = os.listdir(webapps_dir)

    for module_name in module_names:
        module_dir = os.path.join(webapps_dir, module_name)
        pypath = os.path.join(module_dir, "route.py")

        if os.path.exists(pypath):
            handlers = {}
            module_handlers[module_name] = handlers

            spec = importlib.util.spec_from_file_location("route", pypath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for route in module.routes:
                method, path, func = route
                handler_methods = handlers.get(path, {})
                handler_methods[method] = func
                handlers[path] = handler_methods

    def _proxy(cravat_module, action):
        handler_func = module_handlers.get(cravat_module, {}) \
                                      .get(action, {}) \
                                      .get(request.method, None)

        if handler_func:
            return handler_func(request)
        else:
            return HTTP_NOT_FOUND

    return _proxy

def serve_webapp_runwidget(module_name, widget):
    queries = request.values

    mutable_queries_dict = { k: queries[k] for k in queries }
    queries = mutable_queries_dict
    widget_name = f'wg{widget}'

    m = _load_widget_module(module_name, widget_name)
    content = run_coroutine_sync(m.get_data(queries))

    return jsonify(content)

def initialize(application):
    application.add_url_rule('/webapps/<module_name>/widgets/<widget>', None,
                             serve_webapp_runwidget)
    application.add_url_rule('/webapps/<cravat_module>/<action>', None,
                             webapp_proxy_handler(),
                             methods=['GET', 'POST'])

def _load_widget_module(module_name, name):
    widget_path = os.path.join(au.get_modules_dir(), 'webapps', module_name, 'widgets', name, f'{name}.py')
    spec = importlib_util.spec_from_file_location(name, widget_path)
    m = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

