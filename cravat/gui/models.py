import imp
import os
import yaml

from datetime import datetime
from functools import cached_property
from glob import glob

from cravat import constants, admin_util as au
from .cache import cache
from .job_manager import Task, queue_messages

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

    @staticmethod
    def next_id():
        return datetime.now().strftime(r'%y%m%d-%H%M%S')

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
        if not self.task_id:
            return False

        if self.task.result.queued:
            return True

        return False

    @property
    def task_id(self):
        return self.info.get('celery_id', None)

    @property
    def task(self):
        if self.task_id is None:
            return None

        return Task(self.task_id)

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
    def run_path(self):
        return os.path.join(self.job_dir, self.run_name)

    @property
    def db_path(self):
        return self.run_path + Job.DB_EXTENSION

    @property
    def log(self):
        log_path = self.run_path + '.log'
        if not os.path.exists(log_path):
            log_path = None

        return log_path

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


class Module(object):
    @staticmethod
    @cache.cached(key_prefix='runtime/models/Module/local', timeout=60*60*24)
    def local():
        mic = au.ModuleInfoCache()
        mic.update_local()
        return {k: v for k, v in mic.local.items()}


    @staticmethod
    def install_queue():
        install_queue = queue_messages('manage.module')

        # message.payload is a array of arguments and metadata about the message, structured as:
        # [
        #   [args],
        #   {kwargs},
        #   {callbacks, errbacks, chain, chord}
        # ]
        # so the following just pulls the arguments passed to the `install_module` task
        # as a tuple
        return [m.payload[0] for m in install_queue]


    @staticmethod
    def _get_modules_dir():
        """
        Get the current modules directory
        """
        if constants.custom_modules_dir is not None:
            modules_dir = constants.custom_modules_dir
        else:
            modules_dir = os.environ.get(constants.modules_dir_env_key, None)
            if modules_dir is not None and modules_dir != "":
                modules_dir = os.environ.get(constants.modules_dir_env_key)
            else:
                conf = au.get_system_conf()
                modules_dir = conf[constants.modules_dir_key]
        modules_dir = os.path.abspath(modules_dir)
        return modules_dir
