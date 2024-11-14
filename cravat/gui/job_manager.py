import os

import celery
from celery import current_app, states

def celery_init_app(flask_app):
    class FlaskTask(celery.Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery_config = flask_app.config["CELERY"]

    os.makedirs(flask_app.config["CACHE_DIR"], exist_ok=True)
    os.makedirs(celery_config['broker_transport_options']['data_folder_in'], exist_ok=True)
    os.makedirs(celery_config['broker_transport_options']['data_folder_out'], exist_ok=True)
    os.makedirs(flask_app.config["CELERY_RESULTS_PATH"], exist_ok=True)

    celery_app = celery.Celery(flask_app.name, task_cls=FlaskTask)
    celery_app.config_from_object(celery_config)
    celery_app.set_default()
    flask_app.extensions["celery"] = celery_app
    return celery_app


def queue_messages(queue_name, filter=None):
    cnn = current_app.connection()
    q = cnn.SimpleQueue(queue_name)
    queue_size = q.qsize()
    messages = []
    try:
        for i in range(queue_size):
            message = q.get(block=False)
            if filter and filter(message):
                messages.append(message)
            else:
                messages.append(message)
    except q.Empty:
        # it is empty or we read everything left
        pass
    finally:
        cnn.close()

    return messages


class Task(object):
    def __init__(self, task_id):
        self.id = task_id

    @property
    def result(self):
        return current_app.AsyncResult(self.id)

    @property
    def aborted(self):
        return self.result.state in [
            states.REVOKED,
            states.REJECTED,
            'ABORTED',
            states.IGNORED
        ]

    @property 
    def cravat_status(self):
        {
            # PENDING is complicated.
            #
            # If we send a task to celery, and it
            # hasn't been received by a worker yet, it's pending.
            #
            # If we ask for a status of an unknown task id, celery
            # assumes you know what you are asking for and replies
            # `pending`, so pending may mean celery has no idea what
            # you are talking about.
            #
            # I think the assumption is safe, and we can say submitted,
            # however, if we run into a case of lost job, we may need
            # to reach into the queue and go looking on "PENDING"
            states.PENDING: 'Submitted',
            states.RECEIVED: 'Starting',
            states.STARTED: 'Running',
            states.SUCCESS: 'Finished',
            states.FAILURE: 'Error',
            states.REVOKED: 'Aborted',
            states.REJECTED: 'Aborted',
            states.RETRY: 'Submitted',
            states.IGNORED: 'Aborted',
            'ABORTED': 'Aborted',
        }.get(self.result.state, 'Aborted')
        
    def cancel(self):
        if not self.result.ready():
            self.result.revoke()
