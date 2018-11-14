from cravat import util
import time
import traceback
import os
import logging
from logging.handlers import QueueHandler

def run_annotator_mp(module, cmd, log_queue):
    from . import util
    try:
        formatter = logging.Formatter('%(asctime)s %(name)-20s %(message)s', '%Y/%m/%d %H:%M:%S')
        annotator_class = util.load_class("CravatAnnotator", module.script_path)
        annotator = annotator_class(cmd)
        print('run {}'.format(annotator.annotator_name))
        logging.getLogger().addHandler(QueueHandler(log_queue))
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logging.getLogger().addHandler(sh)
        annotator.run()
        print('finished {}'.format(annotator.annotator_name))
    except:
        traceback.print_exc()
        raise