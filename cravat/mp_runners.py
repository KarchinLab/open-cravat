from cravat import util
import time
import traceback
import os
import logging
from logging.handlers import QueueHandler

def run_annotator_mp(module, cmd, log_queue):
    from . import util
    try:
        annotator_class = util.load_class("CravatAnnotator", module.script_path)
        annotator = annotator_class(cmd)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # Otherwise many handlers get added when using multiprocessing pool
        if len(root_logger.handlers) == 0:
            root_logger.addHandler(QueueHandler(log_queue))
        stime = time.time()
        annotator.run()
        rtime = time.time() - stime
        s = '\t{0:30s}\t'.format(module.title + ' (' + module.name + ')')
        s += 'finished in {0:.3f}s'.format(rtime)
        print(s)
    except:
        traceback.print_exc()
        raise