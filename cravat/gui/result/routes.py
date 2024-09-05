from .handlers import *
from cravat.gui.routing import relative_router

def load(application):
    router = relative_router("/result", application)
    service_router = relative_router("/result/service", application)

    service_router('/getresulttablelevels', None, get_result_levels)
    service_router('/variantcols', None, get_variant_cols)
    service_router('/widgetlist', None, get_widgets)
    service_router('/smartfilters', None, get_smartfilters)
    service_router('/samples', None, get_samples)
    service_router('/loadfiltersetting', None, load_filter_setting)

    router('/widgetfile/<module>/<filename>', None, serve_widgetfile)
