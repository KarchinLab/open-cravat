from flask import redirect, jsonify
from cravat import admin_util as au


def redirect_to_index():
    return redirect('/submit/nocache/index.html')


def heartbeat():
    return "pong"


def is_system_ready():
    return jsonify(dict(au.system_ready()))