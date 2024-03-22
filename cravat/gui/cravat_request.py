from flask import request


def is_multiuser_server():
    return request.environ.get('CRAVAT_MULTIUSER', False)