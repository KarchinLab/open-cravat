from cravat.gui.store.handlers import *
from cravat.gui.routing import relative_router


def load(application):
    router = relative_router("/store", application)
    router('/getstoreurl', None, get_storeurl)
    router('/getbasemodules', None, get_base_modules)
    router('/remote', None, get_remote_manifest)
    router('/local', None, get_local_manifest)
    router('/localasremote', None, get_remote_manifest_from_local)
    router('/updates', None, get_module_updates)
    router("/freemodulesspace", None, get_free_modules_space)
    router("/locallogo", None, get_local_module_logo)
    router("/queueinstall", None, queue_install)
    router("/moduledependencies", None, get_module_dependencies)
    router("/uninstall", None, uninstall_module)
    router("/modules/<module_name>/<version>/readme", None, get_module_readme)
    router("/remotemoduleconfig", None, get_remote_module_config)
    # With celery, these are the same, just drop the job
    router("/killinstall", None, kill_install)
    router("/unqueue", None, kill_install)

