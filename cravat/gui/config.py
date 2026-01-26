from cravat import admin_util, constants
from kombu import Exchange, Queue
from pathlib import Path
import platform

## WHere is this used can we use system conf
CRAVAT_SYSCONF = admin_util.get_system_conf()

default_exchange = Exchange('default', type='direct')
management_exchange = Exchange('management', type='direct')
live_annotate_exchange = Exchange('live_annotate', type='direct')

# COOKIE CONFIGURATION (https://flask.palletsprojects.com/en/2.3.x/config/)

# This is the string used for signing the session cookies, it should not be stored in the codebase, in a
# multiuser server scenario this was loaded from the admin database.  A cleaner solution may be to
# load it from an environment variable.

# You may generate a value by using:
# $ python -c 'import secrets; print(secrets.token_hex())'
# '192b9bdd22ab9ed4d12e236c78afcb9a393ec15f71bbf5dc987d54727823bcbf'
# SECRET_KEY = 'a random string'

SESSION_COOKIE_NAME = 'session'

# None is the default and forces the browser to only send cookies to the exact domain name from which it was set
SESSION_COOKIE_DOMAIN = None

# flag to make the cookie is inaccessible from Javascript
SESSION_COOKIE_HTTPONLY = True

# Set the secure flag on the cookie. False is the default value, and needed for the
# laptop use case but for a server deployment behind SSL this should be True.
# again, an excellent candidate for configuration via environment variable.
SESSION_COOKIE_SECURE = False

CRAVAT_WORKDIR = Path(CRAVAT_SYSCONF[constants.work_dir_key])

CELERY_RESULTS_PATH = CRAVAT_WORKDIR/'celery'/'results'
CELERY_RESULTS_WEIRD = f'file:////?/C:/open-cravat/workspace/celery/results'

if platform.system() == 'Windows':
    WORKER_POOL_TYPE = 'gevent'
else:
    WORKER_POOL_TYPE = 'fork'

CELERY = dict(
    broker_url='filesystem://',
    broker_transport_options={
        'data_folder_in': str(CELERY_RESULTS_PATH/'celery'/'broker'),
        'data_folder_out': str(CELERY_RESULTS_PATH/'celery'/'broker'),
    },
    result_backend=f'file:///{CELERY_RESULTS_PATH}',
    include=['cravat.gui.tasks'],
    task_queues=(
        Queue('default', default_exchange, routing_key='default'),
        Queue('module_install', management_exchange, routing_key='module_install'),
        Queue('live_annotate', live_annotate_exchange, routing_key='live_annotate'),
    ),
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default',
    worker_pool= WORKER_POOL_TYPE,
)
print('===== CELERY CONFIG:', CELERY)

CACHE_TYPE = 'FileSystemCache'
CACHE_DEFAULT_TIMEOUT = 300
CACHE_DIR = str(CRAVAT_WORKDIR/'cache')
CACHE_THRESHOLD = 500
CACHE_SOURCE_CHECK = False