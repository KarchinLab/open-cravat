import sys

from cravat.gui.config import (
    QUEUE_DEFAULT,
    QUEUE_MODULE_INSTALL,
    QUEUE_LIVE_ANNOTATE,
    celery_settings,
)


def _start(queue):
    from cravat.gui import celery
    n = celery_settings()[queue]['concurrency']
    celery.Worker(queues=[queue], concurrency=n).start()


def default_worker():
    _start(QUEUE_DEFAULT)


def store_worker():
    _start(QUEUE_MODULE_INSTALL)


def live_annotation_worker():
    _start(QUEUE_LIVE_ANNOTATE)


_WORKERS = {
    'default': default_worker,
    'store': store_worker,
    'live': live_annotation_worker,
}


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in _WORKERS:
        sys.exit(f'usage: python -m cravat.gui.workers {{{"|".join(_WORKERS)}}}')
    _WORKERS[sys.argv[1]]()
