import importlib
import os

from cravat import admin_util as au
from cravat.gui.routing import relative_router

def initialize(application):
    router = relative_router("/result", application)

    webapps_dir = os.path.join(au.get_modules_dir(), "webapps")

    if not os.path.exists(webapps_dir):
        os.mkdir(webapps_dir)

    module_names = os.listdir(webapps_dir)
    for module_name in module_names:
        module_dir = os.path.join(webapps_dir, module_name)
        pypath = os.path.join(module_dir, "route.py")

        if os.path.exists(pypath):
            spec = importlib.util.spec_from_file_location("route", pypath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for route in module.routes:
                method, path, func_name = route
                path = f"/webapps/{module_name}/" + path
                router(path, None, func_name, methods=[method])



