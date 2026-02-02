import subprocess

from celery import shared_task, signals
from cravat import admin_util
from cravat.gui.api.live_module_cache import LiveModuleCache
from .api import live_annotate_worker
from .models import Module
from pathlib import Path

@shared_task()
def run_job(run_args):
    subprocess.run(run_args)


@shared_task(queue="module_install")
def install_module(module_name, version, use_json_handler=None):
    admin_util.install_module(module_name, version=version, use_json_handler=use_json_handler)
    Module.invalidate_cache()

@shared_task()
def run_report(db_path, report_type, tmp_flag_path):
    run_args = ['oc', 'report', db_path, '-t', report_type]
    subprocess.run(run_args)
    Path(tmp_flag_path).unlink()
                  
live_mapper = None

@signals.worker_process_init.connect
def _init_worker_state(**_):
    print(_)
    global live_mapper
    live_mapper = LiveModuleCache()

@shared_task(queue="live_annotate")
def api_live_annotate(queries, annotators, is_multiuser=False):
    global live_mapper
    return live_annotate_worker(queries, annotators, is_multiuser, live_mapper)
