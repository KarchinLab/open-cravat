from . import util
import time
import traceback
import os
import logging
from queue import Empty
import signal
import cravat.admin_util as au


def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def annot_from_queue(start_queue, end_queue, queue_populated, status_writer):
    """
    Annotator worker. Multiple workers are run by Cravat class. Receives annotator
    to run, and arguments in start_queue. On completion, puts message in end_queue.

    Some annotators depend on the output of others and cannot start until the
    required annotator is finished. So, a case could arise where a desired annotator 
    is blocked from starting. In that case the main process will hold the annotator
    out from start_queue until it can be safely started. When all desired annotators
    have been placed in start_queue, the queue_populated semaphore is set to True. When
    start_queue is empty, and queue_populated is true, this worker will exit.

    Annotators place status updates (% completed) into status_writer, where they are
    sent to the main process and displayed to the user. 
    """
    while True:
        try:
            task = start_queue.get(True, 1)
        except Empty:
            if queue_populated:
                break
            else:
                continue
        module, kwargs = task
        logger = logging.getLogger(module.name)
        log_handler = logging.FileHandler(kwargs["log_path"], "a")
        formatter = logging.Formatter(
            "%(asctime)s %(name)-20s %(message)s", "%Y/%m/%d %H:%M:%S"
        )
        log_handler.setFormatter(formatter)
        logger.addHandler(log_handler)
        try:
            kwargs["status_writer"] = status_writer
            annotator_class = util.load_class(module.script_path, "CravatAnnotator")
            annotator = annotator_class(kwargs)
        except Exception as e:
            print(f"        Error with {module.name}: {e}")
            logger.error(e)
            raise
        annotator.run()
        end_queue.put(module.name)


def mapper_runner(
    crv_path,
    seekpos,
    chunksize,
    run_name,
    output_dir,
    status_writer,
    module_name,
    pos_no,
    primary_transcript,
):
    module = au.get_local_module_info(module_name)
    kwargs = {
        "script_path": module.script_path,
        "input_file": crv_path,
        "run_name": run_name,
        "seekpos": seekpos,
        "chunksize": chunksize,
        "slavemode": True,
        "postfix": f".{pos_no:010.0f}",
        "output_dir": output_dir,
    }
    if primary_transcript is not None:
        kwargs["primary_transcript"] = primary_transcript.split(";")
    kwargs["status_writer"] = status_writer
    genemapper_class = util.load_class(module.script_path, "Mapper")
    genemapper = genemapper_class(kwargs)
    output = genemapper.run_as_slave(pos_no)
    return output
