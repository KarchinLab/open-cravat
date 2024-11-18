import logging
import os

from flask import Flask
from pathlib import Path

from whitenoise import WhiteNoise

from cravat import admin_util as au
from cravat import constants

from . import submit, store, config, routing, job_manager, multiuser, logging as cl
from .cache import cache

# Create the Flask application and our configuration
app = Flask(__name__)
app.config.from_object(config)

# Create the WhiteNoise wrapper.  This will serve static files.
static_server = WhiteNoise(app)

# Cravat settings
sysconf = au.get_system_conf()

# Celery
celery = job_manager.celery_init_app(app)
celery.set_default()

# Cache
cache.init_app(app)

def multiuser_middleware(app, multiuser):
    def wsgi_middleware(environ, start_response):
        environ['CRAVAT_MULTIUSER'] = multiuser
        return app(environ, start_response)

    return wsgi_middleware

@app.before_request
def setup_app_context():
    from flask import session, g, request
    g.is_multiuser = request.environ.get('CRAVAT_MULTIUSER', False)

    if not g.is_multiuser:
        g.username = 'default'
    else:
        g.username = session.get('user', None)

###
# Requests are layered through the WSGI Applications as such:
#  -> Waitress (Generic webserver)
#  |-> Multiuser WSGI Middleware (Sets CRAVAT_MULTIUSER)
#  |-> WhiteNoise (Static files)
#  |-> Flask


def _ensure_path_exists(*args):
    path = Path(os.path.join(*args))
    path.mkdir(parents=True, exist_ok=True)


def build_app_instance(is_multiuser):
    from paste.translogger import TransLogger

    # Application Initialization
    routing.load(app, static_server, is_multiuser)
    wrapped_app = multiuser_middleware(static_server, is_multiuser)

    app_with_logger = TransLogger(wrapped_app, setup_console_handler=True)

    return app_with_logger

def build_multiuser_app():
    return build_app_instance(True)

def ensure_workspace_exists():
    # bootstrap cache and celery by creating work directories
    workdir = app.config['CRAVAT_SYSCONF'][constants.work_dir_key]
    _ensure_path_exists(workdir, 'celery', 'broker')
    _ensure_path_exists(workdir, 'celery', 'results')
    _ensure_path_exists(workdir, 'cache')


def start_server(interface, port, multiuser):
    from waitress import serve

    app_with_logger = build_app_instance(multiuser)
    serve(app_with_logger, host=interface, port=port, threads=12)

