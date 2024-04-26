from flask import Flask

from whitenoise import WhiteNoise

from cravat import admin_util as au
from cravat import constants

from . import submit, store, config, routing, job_manager
from .cache import cache

# Create the Flask application and our configuration
app = Flask(__name__)
app.config.from_object(config)

# Create the WhiteNoise wrapper.  This will serve static files.
static_server = WhiteNoise(app)

# Cravat settings
sysconf = au.get_system_conf()
log_dir = sysconf[constants.log_dir_key]

# Celery
celery = job_manager.celery_init_app(app)
celery.set_default()

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

def start_server(interface, port, multiuser):
    from waitress import serve

    # Application Initialization
    routing.load(app, static_server, multiuser)
    cache.init_app(app)

    wrapped_app = multiuser_middleware(static_server, multiuser)
    serve(wrapped_app, host=interface, port=port)