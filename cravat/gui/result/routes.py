from .handlers import *
from cravat.gui.routing import relative_router


def load(application):
    router = relative_router("/result", application)
    router('/service/getresulttablelevels', None, get_result_levels)
    router('/service/variantcols', None, get_variant_cols)
    router('/widgetfile/<module>/<filename>', None, serve_widgetfile)
