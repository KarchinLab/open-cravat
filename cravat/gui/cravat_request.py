from flask import request


def is_multiuser_server():
    return request.environ.get('CRAVAT_MULTIUSER', False)


def request_user():
    if not is_multiuser_server():
        return 'default'
    else:
        return request.environ.get('CRAVAT_USER', None)
