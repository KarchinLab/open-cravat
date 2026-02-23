from flask import request, g, abort
from cravat.gui import tasks
import cravat.admin_util as au

## LIVE ANNOTATION
def format_response(response, version):
    if not version:
        return response
    if version == 'v1':
        return response
    else:
        return response

def live_annotate(version=None):
    enable_variant_api = au.get_system_conf().get('enable_variant_api',False)
    if not enable_variant_api:
        return abort(404)
    queries = dict(request.values) if request.values else request.json
    annotators = queries.get('annotators', [])
    is_multiuser = g.is_multiuser
    result = tasks.api_live_annotate.apply_async(kwargs={"queries":queries, "annotators":annotators, "is_multiuser": is_multiuser})
    resp = result.get()
    if not version and queries.get('version'):
        version = queries.get('version')
    resp = format_response(resp, version)
    return resp
