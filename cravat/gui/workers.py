import os
import sys

from cravat.gui.config import (
    QUEUE_DEFAULT,
    QUEUE_MODULE_INSTALL,
    QUEUE_LIVE_ANNOTATE,
    celery_settings,
)


def _start(queue):
    # Pool children started with 'spawn' (billiard's default on macOS since
    # 4.3) only set up Celery's task tracer when this is set; without it every
    # task fails with "not enough values to unpack (expected 3, got 0)".
    os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')
    # When started via multiprocessing.Process (as `oc gui` does), __main__ is
    # '__mp_main__' with no __spec__. billiard then tells its spawned pool
    # children to re-import a module named '__mp_main__', which fails. Point
    # __main__ at this module so the children re-import something importable.
    main = sys.modules['__main__']
    if main.__name__ == '__mp_main__' and getattr(main, '__spec__', None) is None:
        sys.modules['__main__'] = sys.modules[__name__]
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
