import subprocess

from celery import shared_task
from cravat import admin_util
from .api import live_annotate_worker
from .models import Module
from pathlib import Path

@shared_task()
def run_job(run_args):
    subprocess.run(run_args)


@shared_task(queue="module_install")
def install_module(module_name, version):
    admin_util.install_module(module_name, version=version)
    Module.invalidate_cache()

@shared_task()
def run_report(db_path, report_type, tmp_flag_path):
    run_args = ['oc', 'report', db_path, '-t', report_type]
    subprocess.run(run_args)
    Path(tmp_flag_path).unlink()

@shared_task(queue="live_annotate")
def api_live_annotate(queries, annotators, is_multiuser=False):
    return live_annotate_worker(queries, annotators, is_multiuser)
