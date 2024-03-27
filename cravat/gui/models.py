import os
import yaml

from functools import cached_property
from glob import glob


class Job(object):
    DB_EXTENSION = ".sqlite"

    def __init__(self, job_dir, job_status_fpath):
        self.job_status_fpath = job_status_fpath
        self.job_dir = job_dir
        job_id = os.path.basename(job_dir)
        self.info = {
            'id': job_id,
            'orig_input_fname': '',
            'assembly': '',
            'note': '',
            'db_path': '',
            'viewable': False,
            'reports': [],
            'annotators': '',
            'annotator_version': '',
            'open_cravat_version': '',
            'num_input_var': '',
            'submission_time': '',
            'reports_being_generated': []
        }

    @property
    def id(self):
        return self.info['id']

    @property
    def error(self):
        return self.info['status'] == 'Error'

    @property
    def ended(self):
        return self.info['status'] in ['Finished', 'Error']

    @property
    def queued(self):
        # TODO: Check Celery
        return True

    @cached_property
    def run_name(self):
        run_name = self.info['run_name']
        if run_name is None:
            fns = glob(f"{self.job_dir}/*.crv")
            for fn in fns:
                run_name = fn[:-4]
                break

        return run_name

    @property
    def db_path(self):
        return os.path.join(self.job_dir, self.run_name) + Job.DB_EXTENSION

    def save_options(self, job_options):
        self.set_values(**job_options)

    def read_info_file(self):
        if not os.path.exists(self.job_status_fpath):
            info_dict = {'status': 'Error'}
        else:
            with open(self.job_status_fpath) as f:
                info_dict = yaml.safe_load(f)
        if info_dict is not None:
            self.set_values(**info_dict)

    def set_info_values(self, **kwargs):
        self.set_values(**kwargs)

    def get_info_dict(self):
        return self.info

    def set_values(self, **kwargs):
        self.info.update(kwargs)