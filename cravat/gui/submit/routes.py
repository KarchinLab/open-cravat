from cravat.gui.submit.handlers import *
from cravat.gui.routing import relative_router


def load(application):
    router = relative_router("/submit", application)
    router("/servermode", None, server_mode)
    router("/reports", None, get_report_types)
    router("/getsystemconfinfo", None, get_system_conf_info)
    router("/lastassembly", None, get_last_assembly)
    router("/packageversions", None, get_package_versions)
    router("/jobs", None, list_jobs)
    router("/getjobs", None, get_jobs)
    router("/annotators", None, get_annotators)
    router("/packages", None, get_packages)
