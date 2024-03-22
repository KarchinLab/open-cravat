from cravat import admin_util
from cachelib import FileSystemCache

from flask_session import Session
SESSION_TYPE = 'cachelib'
SESSION_CACHELIB = FileSystemCache(cache_dir='flask_session', threshold=500)
SESSION_COOKIE_SECURE = False   # TODO: Make this follow ssl setting

CACHE_TYPE = FileSystemCache(cache_dir='request_cache')
CACHE_DEFAULT_TIMEOUT = 300

CRAVAT_SYSCONF = admin_util.get_system_conf()
