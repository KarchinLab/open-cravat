from . import util
import time
import traceback
import os
import logging
from logging.handlers import QueueHandler
from queue import Empty
import signal

def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def annot_from_queue(start_queue, end_queue, queue_populated, status_writer):
    try:
        while True:
            try:
                task = start_queue.get(True, 1)
            except Empty:
                if queue_populated:
                    break
                else:
                    continue
            module, cmd = task
            annotator_class = util.load_class(module.script_path, "CravatAnnotator")
            annotator = annotator_class(cmd, status_writer)
            annotator.run()
            end_queue.put(module.name)
    except:
        traceback.print_exc()
