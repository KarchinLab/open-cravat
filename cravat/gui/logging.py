import logging
import os

from logging.config import dictConfig

from flask import request, has_request_context
from flask.logging import default_handler

from cravat import admin_util as au, constants

sysconf = au.get_system_conf()
log_dir = sysconf[constants.log_dir_key]
log_path = os.path.join(log_dir, "wcravat.log")
print(log_path)

class RequestFormatter(logging.Formatter):
    def format(self, record):
        if has_request_context():
            record.url = request.url
            record.remote_addr = request.remote_addr
        else:
            record.url = None
            record.remote_addr = None

        return super().format(record)

dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default',
        },
        'cravat': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'when': 'd',
            'filename': log_path,
            'backupCount': 30,
            'formatter': 'default',
         }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi', 'cravat']
    },
    'wsgi': {
        'level': 'DEBUG',
        'handlers': ['wsgi', 'cravat']
    }
})

request_formatter = RequestFormatter(
    '[%(asctime)s] %(remote_addr)s requested %(url)s\n'
    '%(levelname)s in %(module)s: %(message)s'
)
default_handler.setFormatter(request_formatter)
