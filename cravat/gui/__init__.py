from flask import Flask
from whitenoise import WhiteNoise

from cravat import admin_util as au
from cravat import constants

from . import submit, store, config, routing, job_manager

# Create the Flask application and our configuration
app = Flask(__name__)
app.config.from_object(config)

# Create the WhiteNoise wrapper.  This will serve static files.
static_server = WhiteNoise(app)

sysconf = au.get_system_conf()
log_dir = sysconf[constants.log_dir_key]

celery = job_manager.celery_init_app(app)
celery.set_default()

routing.load(app, static_server)


def multiuser_middleware(app, multiuser):
    # TODO: Rework cravat_multiuser, this is just the variable,
    # we also need the features/routes
    def wsgi_middleware(environ, start_response):
        environ['CRAVAT_MULTIUSER'] = multiuser
        return app(environ, start_response)

    return wsgi_middleware


def start_server(interface, port, multiuser):
    from waitress import serve
    wrapped_app = multiuser_middleware(static_server, multiuser)
    serve(wrapped_app, host=interface, port=port)