from . import util
import time
import traceback
import os
import logging
from logging.handlers import QueueHandler

def run_annotator_mp(module, cmd, d, log_queue):
    completion_status = 'incomplete'
    stime = time.time()
    annotator_class = util.load_class("CravatAnnotator", module.script_path)
    annotator = annotator_class(cmd, d)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    annotator.run()
    completion_status = 'finished'
