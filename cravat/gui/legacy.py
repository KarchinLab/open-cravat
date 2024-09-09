import os
from glob import glob

from cravat import admin_util as au, CravatFilter
from cravat.cravat_util import can_migrate_result
from cravat.gui import metadata
from cravat.gui.models import Job
from . import async_utils

# this module is to wrap code from the legacy web codebase
# ideally anything imported or declared here should be replaced

###
# Re-exports
from cravat.websubmit import websubmit
from cravat.webresult import webresult

###
# Wrappers


class UserFileRouter(object):
    def __init__(self, username, multiuser):
        self.username = username
        self.wrapped_router = websubmit.FileRouter()
        self.multiuser = multiuser

        self.report_extensions = {
            'text':'.tsv',
            'excel':'.xlsx',
            'vcf': '.vcf'
        }
        self.log_extension = '.log'
        self.status_extension = '.status.json'


    @property
    def job_dirs(self):
        return self.wrapped_router.job_dirs_for_user(self.username)

    @property
    def is_admin(self):
        return self.username == 'admin'

    def job_dir(self, job_id):
        job_dir = None
        job_dirs = self.job_dirs

        if job_dirs:
            if self.multiuser:
                if self.is_admin:
                    for jobs_dir in job_dirs:
                        job_dir = os.path.join(jobs_dir, job_id)
                        if os.path.exists(job_dir):
                            break
                else:
                    job_dir = os.path.join(os.path.dirname(job_dirs[0]), self.username, job_id)
            else:
                job_dir = os.path.join(job_dirs[0], job_id)

        return job_dir

    def job_report(self, job_id, report_type):
        run_path = self.job_dir(job_id)
        if run_path is None:
            return None

        run_name = os.path.basename(run_path)
        report_path = None
        if report_type in self.report_extensions:
            ext = self.report_extensions.get(report_type, '.' + report_type)
            report_path = [run_path + ext]
        else:
            reporter = au.get_local_module_info(report_type + 'reporter')
            if reporter is None:
                return None
            conf = reporter.conf
            if 'output_filename_schema' in conf:
                output_filename_schemas = conf['output_filename_schema']
                report_path = []
                for output_filename_schema in output_filename_schemas:
                    output_filename = output_filename_schema.replace('{run_name}', run_name)
                    report_path.append(output_filename)

        return report_path

    def load_job(self, job_id):
        job_dir = self.job_dir(job_id)

        if not (os.path.exists(job_dir) and
                os.path.isdir(job_dir)):
            job = Job(job_dir, None)
            job.info['status'] = 'Error'
            return job

        status_files = glob(f"{job_dir}/*.status.json")
        if len(status_files) < 1:
            job = Job(job_dir, None)
            job.info['status'] = 'Error'
            return job

        status_path = status_files[0]
        job = Job(job_dir, status_path)
        job.read_info_file()

        if 'status' not in job.info:
            if job.task:
                job.info['status'] = job.task.cravat_status
            else:
                job.info['status'] = 'Aborted'
        elif not job.ended:
            if job.task and job.task.aborted:
                job.info['status'] = 'Aborted'

        db_files = glob(f"{job_dir}/*.sqlite")
        if len(db_files) > 0:
            db_path = db_files[0]
        else:
            db_path = ''

        job.set_info_values(
            viewable=os.path.exists(db_path),
            db_path=db_path,
            status=job.info['status'],
            username=self.username,
        )

        existing_reports = []
        reports_being_generated = []
        for report_type in metadata.supported_report_types():
            report_paths = self.job_report(job_id, report_type)
            if report_paths is not None:
                report_exist = True
                for p in report_paths:
                    if not os.path.exists(os.path.join(job_dir, p)):
                        report_exist = False
                        break
                if os.path.exists(os.path.join(job_dir, job_id + '.report_being_generated.' + report_type)):
                    report_exist = False
                    reports_being_generated.append(report_type)

                if report_exist:
                    existing_reports.append(report_type)
                else:
                    # TODO: Check Celery, requires an intermediate state store for
                    # running report task id, probably the .report_being_generated.type file
                    if True:
                        pass

        job.set_info_values(reports=existing_reports,
                            reports_being_generated=reports_being_generated)

        if 'open_cravat_version' not in job.info:
            job.info['open_cravat_version'] = '0.0.0'

        job.info['result_available'] = not can_migrate_result(job.info['open_cravat_version'])

        for annot_to_del in ['extra_vcf_info', 'extra_variant_info']:
            if annot_to_del in job.info['annotators']:
                job.info['annotators'].remove(annot_to_del)

        return job