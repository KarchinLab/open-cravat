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
    router("/submit", None, submit, methods=['POST'])
    router("/jobs/<job_id>", None, delete_job, methods=['DELETE'])
    router("/jobs/<job_id>/log", None, get_job_log)
    router("/jobs/<job_id>/err", None, get_job_err)
    router("/jobs/<job_id>/db", None, get_job_db)
    router("/jobs/<job_id>/reports/<report_type>", None, generate_report, methods=['POST'])
    router("/jobs/<job_id>/reports/<report_type>", None, download_report, methods=['GET'])
    router("/resubmit", None, resubmit)
    router("/annotate", None, live_annotate, methods=['GET', 'POST'])
