from . import util
import time
import traceback
import os
import logging
from logging.handlers import QueueHandler
from queue import Empty
import signal
import cravat.admin_util as au

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
            module, kwargs = task
            kwargs['status_writer'] = status_writer
            annotator_class = util.load_class(module.script_path, "CravatAnnotator")
            annotator = annotator_class(kwargs)
            annotator.run()
            end_queue.put(module.name)
    except:
        traceback.print_exc()

def mapper_runner (crv_path, seekpos, chunksize, run_name, output_dir, status_writer, module_name, pos_no, primary_transcript):
    module = au.get_local_module_info(module_name)
    kwargs = {'script_path': module.script_path, 'input_file': crv_path, 'run_name': run_name, 'seekpos': seekpos, 'chunksize': chunksize, 'slavemode': True, 'postfix': f'.{pos_no:010.0f}', 'output_dir': output_dir}
    if primary_transcript is not None:
        kwargs['primary_transcript'] = primary_transcript.split(';')
    kwargs['status_writer'] = status_writer
    genemapper_class = util.load_class(module.script_path, 'Mapper')
    genemapper = genemapper_class(kwargs)
    output = genemapper.run_as_slave(pos_no)
    return output
