from . import util
import time
import traceback
import os
import logging
from logging.handlers import QueueHandler

def run_annotator_mp(module, cmd, d):
    completion_status = 'incomplete'
    stime = time.time()
    annotator_class = util.load_class("CravatAnnotator", module.script_path)
    annotator = annotator_class(cmd, d)
    annotator.run()
    completion_status = 'finished'
