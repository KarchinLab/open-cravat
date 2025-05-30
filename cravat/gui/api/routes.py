from cravat.gui.api.handlers import live_annotate
from cravat.gui.routing import relative_router


def load(application):
    router = relative_router("/api", application)
    router('/annotate', None, live_annotate, methods=['GET', 'POST'])
    router('/<version>/annotate', None, live_annotate, methods=['GET', 'POST'])
