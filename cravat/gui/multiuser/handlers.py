import datetime
import os

from flask import session, request, jsonify, g, current_app
from cravat import admin_util as au
from cravat.gui.cravat_request import HTTP_UNAUTHORIZED
from .db import AdminDb
from .models import User


def login():
    authorization = request.authorization
    if authorization:
        user = User.authenticate(authorization.username, authorization.password)
        if user:
            if not user.guest or (user.guest and user.active):
                session['user'] = str(user)
                return jsonify('success')
            else:
                user.expire()

    return HTTP_UNAUTHORIZED


def get_user_settings():
    admindb = AdminDb()
    response = admindb.get_user_settings(g.username)
    return jsonify(response)


def signup():
    system_conf = current_app.config['CRAVAT_SYSCONF']
    enable_remote_user_header = system_conf.get('enable_remote_user_header', False)
    noguest = system_conf.get('noguest', False)
    admindb = AdminDb()

    if not enable_remote_user_header:
        queries = request.values
        username = queries['username']

        if noguest and username.startswith('guest_'):
            response = 'No guest account is allowed.'
        else:
            password = queries['password']
            answer = queries['answer']
            question = queries['question']

            if admindb.register_user(username, password, question, answer):
                _create_user_dir_if_not_exist(username)
                session['user'] = User.authenticate(username, password)
                response = 'Signup successful'
            else:
                response = 'Already registered'
    else:
        response = 'Signup failed'

    return jsonify(response)


def check_logged():
    sysconf = current_app.config['CRAVAT_SYSCONF']

    if g.username:
        logged = True
        email = g.username
        user = User.find_by_email(g.username)
    else:
        logged = False
        email = ''
        user = None

    if g.username.startswith('guest_'):
        datestr = g.username.split('_')[2]
        creation_date = datetime.datetime(
            int(datestr[:4]),
            int(datestr[4:6]),
            int(datestr[6:8]))
        current_date = datetime.datetime.now()
        days_passed = (current_date - creation_date).days
        guest_lifetime = sysconf.get('guest_lifetime', 7)
        days_rem = guest_lifetime - days_passed
    else:
        days_rem = -1

    is_admin = user and user.admin

    response = {'logged': logged, 'email': email, 'days_rem': days_rem, 'admin': is_admin}
    return jsonify(response)


def _create_user_dir_if_not_exist(username):
    root_jobs_dir = au.get_jobs_dir()
    user_job_dir = os.path.join(root_jobs_dir, username)
    if not os.path.exists(user_job_dir):
        os.mkdir(user_job_dir)