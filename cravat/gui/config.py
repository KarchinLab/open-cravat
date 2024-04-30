from cravat import admin_util, constants
from kombu import Exchange, Queue

## WHere is this used can we use system conf
CRAVAT_SYSCONF = admin_util.get_system_conf()

default_exchange = Exchange('default', type='direct')
management_exchange = Exchange('management', type='direct')

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

CELERY = dict(
    broker_url='filesystem://',
    broker_transport_options={
        'data_folder_in': f'{CRAVAT_SYSCONF[constants.work_dir_key]}/celery/broker',
        'data_folder_out': f'{CRAVAT_SYSCONF[constants.work_dir_key]}/celery/broker/'
    },
    result_backend=f'file://{CRAVAT_SYSCONF[constants.work_dir_key]}/celery/results',
    include=['cravat.gui.tasks'],
    task_queues=(
        Queue('default', default_exchange, routing_key='default'),
        Queue('module_install', management_exchange, routing_key='module_install'),
    ),
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default'
)

CACHE_TYPE = 'FileSystemCache'
CACHE_DEFAULT_TIMEOUT = 300
CACHE_DIR = f'{CRAVAT_SYSCONF[constants.work_dir_key]}/cache'
CACHE_THRESHOLD = 500
CACHE_SOURCE_CHECK = True