from flask import request, g, abort
from cravat.gui import tasks
from cravat.gui.config import QUEUE_LIVE_ANNOTATE, celery_settings
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
    if not celery_settings()[QUEUE_LIVE_ANNOTATE]['enabled']:
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
