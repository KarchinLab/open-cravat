from cravat import admin_util, constants
from kombu import Exchange, Queue

## WHere is this used can we use system conf
CRAVAT_SYSCONF = admin_util.get_system_conf()

# Celery queue names used by the GUI
QUEUE_DEFAULT = 'default'
QUEUE_MODULE_INSTALL = 'module_install'
QUEUE_LIVE_ANNOTATE = 'live_annotate'

def celery_settings():
    user = CRAVAT_SYSCONF.get('celery') or {}
    # Configurable value defaults
    queue_defaults = {
        QUEUE_DEFAULT: {'concurrency': 4},
        QUEUE_LIVE_ANNOTATE: {'enabled': False, 'concurrency': 4},
    }
    # Module install queue not user configurable
    merged = {
        QUEUE_MODULE_INSTALL: {'concurrency': 1},
    }
    for queue, defaults in queue_defaults.items():
        q = dict(defaults)
        q.update(user.get(queue) or {})
        merged[queue] = q
    return merged

# Celery exchanges exist per-queue
default_exchange = Exchange(QUEUE_DEFAULT, type='direct')
module_install_exchange = Exchange(QUEUE_MODULE_INSTALL, type='direct')
live_annotate_exchange = Exchange(QUEUE_LIVE_ANNOTATE, type='direct')

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

CELERY_RESULTS_PATH = f'/{CRAVAT_SYSCONF[constants.work_dir_key]}/celery/results'

CELERY = dict(
    broker_url='filesystem://',
    broker_transport_options={
        'data_folder_in': f'{CRAVAT_SYSCONF[constants.work_dir_key]}/celery/broker',
        'data_folder_out': f'{CRAVAT_SYSCONF[constants.work_dir_key]}/celery/broker/',
		'control_folder': f'{CRAVAT_SYSCONF[constants.work_dir_key]}/celery/control/',
    },
    result_backend=f'file:/{CELERY_RESULTS_PATH}',
    include=['cravat.gui.tasks'],
    task_queues=(
        Queue(QUEUE_DEFAULT, default_exchange, routing_key=QUEUE_DEFAULT),
        Queue(QUEUE_MODULE_INSTALL, module_install_exchange, routing_key=QUEUE_MODULE_INSTALL),
        Queue(QUEUE_LIVE_ANNOTATE, live_annotate_exchange, routing_key=QUEUE_LIVE_ANNOTATE),
    ),
    task_default_queue=QUEUE_DEFAULT,
    task_default_exchange=QUEUE_DEFAULT,
    task_default_routing_key=QUEUE_DEFAULT,
)

CACHE_TYPE = 'FileSystemCache'
CACHE_DEFAULT_TIMEOUT = 300
CACHE_DIR = f'{CRAVAT_SYSCONF[constants.work_dir_key]}/cache'
CACHE_THRESHOLD = 500
CACHE_SOURCE_CHECK = False