from cravat.gui.store.handlers import *
from cravat.gui.routing import relative_router


def load(application):
    router = relative_router("/store", application)
    router('/getstoreurl', None, get_storeurl)
    router('/getbasemodules', None, get_base_modules)
    router('/remote', None, get_remote_manifest)
    router('/local', None, get_local_manifest)

