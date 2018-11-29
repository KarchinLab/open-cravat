from . import util
import time
import traceback
import os
import logging
from logging.handlers import QueueHandler

def run_annotator_mp(module, cmd, log_queue):
    try:
        completion_status = 'incomplete'
        stime = time.time()
        annotator_class = util.load_class("CravatAnnotator", module.script_path)
        annotator = annotator_class(cmd)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # Otherwise many handlers get added when using multiprocessing pool
        if len(root_logger.handlers) == 0:
            root_logger.addHandler(QueueHandler(log_queue))
        annotator.run()
        completion_status = 'finished'
    except:
        traceback.print_exc()
        completion_status = 'errored'
    finally:
        rtime = time.time() - stime
        s = '\t{0:30s}\t'.format(module.title + ' (' + module.name + ')')
        s += '{0} in {1:.3f}s'.format(completion_status, rtime)
        print(s)