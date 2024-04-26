from cravat import admin_util
from kombu import Exchange, Queue

CACHE_TYPE = 'FileSystemCache'
CACHE_DEFAULT_TIMEOUT = 300
CACHE_DIR = '.cache'
CACHE_THRESHOLD = 500
CACHE_SOURCE_CHECK = True

## WHere is this used can we use system conf
CRAVAT_SYSCONF = admin_util.get_system_conf()

default_exchange = Exchange('default', type='direct')
management_exchange = Exchange('management', type='direct')

CELERY = dict(
    broker_url='filesystem://',
    broker_transport_options={
        'data_folder_in': './.data/broker',
        'data_folder_out': './.data/broker/'
    },
    result_backend='file://./.data/results',
    include=['cravat.gui.tasks'],
    task_queues=(
        Queue('default', default_exchange, routing_key='default'),
        Queue('module_install', management_exchange, routing_key='module_install'),
    ),
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default'
)
