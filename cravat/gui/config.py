from cravat import admin_util
from cachelib import FileSystemCache

from flask_session import Session
SESSION_TYPE = 'cachelib'
SESSION_CACHELIB = FileSystemCache(cache_dir='flask_session', threshold=500)
SESSION_COOKIE_SECURE = False   # TODO: Make this follow ssl setting

CACHE_TYPE = FileSystemCache(cache_dir='request_cache')
CACHE_DEFAULT_TIMEOUT = 300


## WHere is this used can we use system conf
CRAVAT_SYSCONF = admin_util.get_system_conf()

CELERY = dict(
    broker_url='filesystem://',
    broker_transport_options={
        'data_folder_in': './.data/broker',
        'data_folder_out': './.data/broker/'
    },
    result_backend='file://./.data/results',
    include=['cravat.gui.tasks']
)
