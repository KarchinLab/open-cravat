import subprocess

from celery import shared_task
from cravat import admin_util

@shared_task()
def run_job(run_args):
    subprocess.run(run_args)


@shared_task(queue="module_install")
def install_module(module_name, version):
    admin_util.install_module(module_name, version=version)