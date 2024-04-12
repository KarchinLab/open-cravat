import subprocess
from celery import shared_task

@shared_task()
def run_job(run_args):
    subprocess.run(run_args)