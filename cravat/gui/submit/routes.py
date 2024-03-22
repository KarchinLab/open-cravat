from cravat.gui.submit.handlers import *
from cravat.gui.routing import relative_router


def load(application):
    submit_router = relative_router("/submit", application)
    submit_router("/servermode", None, server_mode)
    submit_router("/reports", None, get_report_types)
    submit_router("/getsystemconfinfo", None, get_system_conf_info)
    submit_router("/lastassembly", None, get_last_assembly)
    submit_router("/packageversions", None, get_package_versions)
    submit_router("/jobs", None, get_jobs)
