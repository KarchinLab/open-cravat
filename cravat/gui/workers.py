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
    # the default prefork pool is unsupported on Windows (spawned children can't unpickle the app's local Task class).
    # Tasks that install signal handlers (module install) need the main thread, so single-slot queues use solo.
    pool = None
    if sys.platform == 'win32':
        pool = 'solo' if n == 1 else 'threads'
    celery.Worker(queues=[queue], concurrency=n, pool=pool).start()


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
