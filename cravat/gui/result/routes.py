from .handlers import *
from cravat.gui.routing import relative_router
from ...webresult.webresult import get_layout_save_names


def load(application):
    router = relative_router("/result", application)
    service_router = relative_router("/result/service", application)

    service_router('/getresulttablelevels', None, get_result_levels)
    service_router('/variantcols', None, get_variant_cols)
    service_router('/widgetlist', None, get_widgets)
    service_router('/smartfilters', None, get_smartfilters)
    service_router('/samples', None, get_samples)
    service_router('/loadfiltersetting', None, load_filter_setting)
    service_router('/loadlayoutsetting', None, load_layout_setting)
    service_router('/getfiltersavenames', None, get_filter_save_names)
    service_router('/status', None, get_status)
    service_router('/count', None, get_count, methods=['POST'])
    service_router('/result', None, get_result, methods=['POST'])
    service_router('/savelayoutsetting', None, save_layout_setting, methods=['POST'])
    service_router('/savefiltersetting', None, save_filter_setting)
    service_router('/jobpackage', None, jobpackage)
    service_router('/deletelayoutsetting', None, delete_layout_setting)
    service_router('/getlayoutsavename', None, get_layout_save_names)

    router('/runwidget/<widget_module>', None, serve_runwidget)
    router('/runwidget/<widget_module>', None, serve_runwidget_post, methods=['POST'])
    router('/widgetfile/<module>/<filename>', None, serve_widgetfile)
