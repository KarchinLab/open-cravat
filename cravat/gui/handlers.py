from flask import redirect, jsonify, g
from cravat import admin_util as au


def redirect_to_index():
    if g.is_multiuser and g.username is None:
        return redirect('/server/nocache/login.html')
    else:
        return redirect('/submit/nocache/index.html')


def heartbeat():
    return "pong"


def is_system_ready():
    return jsonify(dict(au.system_ready()))