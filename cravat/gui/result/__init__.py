from . import routes


def initialize(application):
    routes.load(application)



