import datetime
import hashlib
import json
import os

from flask import session, request, jsonify, g, current_app, redirect, send_file
from cravat import admin_util as au
from cravat.gui.cravat_request import HTTP_UNAUTHORIZED
from .models import User
from .decorators import with_admin_db
from ..decorators import require_multiuser, require_admin


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

@require_multiuser(multiuser_error=json.dumps({'status':'fail', 'msg':'no multiuser mode'}))
@with_admin_db
def get_password_question(admin_db):
    queries = request.values
    email = queries['email']
    question = admin_db.get_password_question(email)
    if question is None:
        response = {'status':'fail', 'msg':'No such email'}
    else:
        response = {'status':'success', 'msg': question}

    return jsonify(response)


@require_multiuser(multiuser_error=json.dumps({'success': False, 'msg': 'no multiuser mode'}))
@with_admin_db
def check_password_answer(admin_db):
    queries = request.values
    email = queries['email']
    answer = queries['answer']

    m = hashlib.sha256()
    m.update(answer.encode('utf-16be'))
    answerhash = m.hexdigest()

    if admin_db.check_password_answer(email, answerhash):
        temppassword = admin_db.set_temp_password(email)
        response = {'success': True, 'msg': temppassword}
    else:
        response = {'success': False, 'msg': 'Wrong answer'}

    return jsonify(response)

def show_login_page():
    logger = current_app.logger
    if not g.is_multiuser:
        logger.info('Login page requested but no multiuser mode. Redirecting to submit index...')
        return redirect('/submit/nocache/index.html')

    if not g.username:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nocache', 'login.html')
        return send_file(p)
    else:
        logger.info('Login page requested but already logged in. Redirecting to submit index...')
        return redirect('/submit/nocache/index.html')

@with_admin_db
def get_user_settings(admin_db):
    response = admin_db.get_user_settings(g.username)
    return jsonify(response)

def get_noguest():
    system_conf = current_app.config['CRAVAT_SYSCONF']
    return jsonify(system_conf.get('noguest', False))

@with_admin_db
def signup(admin_db):
    system_conf = current_app.config['CRAVAT_SYSCONF']
    enable_remote_user_header = system_conf.get('enable_remote_user_header', False)
    noguest = system_conf.get('noguest', False)

    if not enable_remote_user_header:
        queries = request.values
        username = queries['username']

        if noguest and username.startswith('guest_'):
            response = 'No guest account is allowed.'
        else:
            password = queries['password']
            answer = queries['answer']
            question = queries['question']

            if admin_db.register_user(username, password, question, answer):
                _create_user_dir_if_not_exist(username)
                if User.authenticate(username, password):
                    session['user'] = username
                    response = 'Signup successful'
                else:
                    # check for a bug in registration, are they actually there?
                    response = 'Signup failed'
            else:
                response = 'Already registered'
    else:
        response = 'Signup failed'

    return jsonify(response)

@with_admin_db
@require_multiuser()
def change_password(admin_db):
    queries = request.values
    newemail = queries['newemail']
    oldpassword = queries['oldpassword']
    newpassword = queries['newpassword']

    username = g.username
    if not username:
        response = 'Not logged in'
        return response

    m = hashlib.sha256()
    m.update(oldpassword.encode('utf-16be'))
    oldpasswordhash = m.hexdigest()

    if username.startswith('guest_') == False and '@' not in username:
        r = admin_db.check_password(username, oldpasswordhash)
    else:
        r = True

    if not r:
        response = 'User authentication failed.'
    else:
        if newemail != '':
            r = admin_db.set_username(username, newemail)
            if r != '':
                return r
            else:
                username = newemail

        if newpassword != '':
            m = hashlib.sha256()
            m.update(newpassword.encode('utf-16be'))
            newpasswordhash = m.hexdigest()
            admin_db.set_password(username, newpasswordhash)

        response = 'success'

    return response

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

    if logged and g.username.startswith('guest_'):
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


@require_multiuser()
def logout():
    session.pop('user', None)
    response = 'success'
    return jsonify(response)


@require_multiuser()
@require_admin
@with_admin_db
def get_input_stat(admin_db):
    queries = request.values
    start_date = queries['start_date']
    end_date = queries['end_date']
    rows = admin_db.get_input_stat(start_date, end_date)
    return jsonify(rows)

@require_multiuser()
@require_admin
@with_admin_db
def get_user_stat(admin_db):
    queries = request.values
    start_date = queries['start_date']
    end_date = queries['end_date']
    rows = admin_db.get_user_stat(start_date, end_date)
    return jsonify(rows)

@require_multiuser()
@require_admin
@with_admin_db
def get_job_stat(admin_db):
    queries = request.values
    start_date = queries['start_date']
    end_date = queries['end_date']
    response = admin_db.get_job_stat(start_date, end_date)
    return jsonify(response)

@require_multiuser()
@require_admin
@with_admin_db
def get_api_stat(admin_db):
    queries = request.values
    start_date = queries['start_date']
    end_date = queries['end_date']
    response = admin_db.get_api_stat(start_date, end_date)
    return jsonify(response)

@require_multiuser()
@require_admin
@with_admin_db
def get_annot_stat(admin_db):
    queries = request.values
    start_date = queries['start_date']
    end_date = queries['end_date']
    response = admin_db.get_annot_stat(start_date, end_date)
    return jsonify(response)

@require_multiuser()
@require_admin
@with_admin_db
def get_assembly_stat(admin_db):
    queries = request.values
    start_date = queries['start_date']
    end_date = queries['end_date']
    response = admin_db.get_assembly_stat(start_date, end_date)
    return jsonify(response)

def _create_user_dir_if_not_exist(username):
    root_jobs_dir = au.get_jobs_dir()
    user_job_dir = os.path.join(root_jobs_dir, username)
    if not os.path.exists(user_job_dir):
        os.mkdir(user_job_dir)