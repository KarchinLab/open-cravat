from cravat import admin_util, constants
from kombu import Exchange, Queue

## WHere is this used can we use system conf
CRAVAT_SYSCONF = admin_util.get_system_conf()

default_exchange = Exchange('default', type='direct')
management_exchange = Exchange('management', type='direct')

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