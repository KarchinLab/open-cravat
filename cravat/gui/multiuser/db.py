import base64
import hashlib
import json
import os
import random

from cryptography import fernet
from sqlite3 import connect

from cravat import admin_util as au
from cravat.constants import admindb_path


def _connect():
    return connect(admindb_path)


def _check_username_presence(conn, username):
    cursor = conn.cursor()
    cursor.execute('select * from users where email=?', (username,))
    r = cursor.fetchone()
    cursor.close()

    if r is None:
        return False
    else:
        return True


def _add_user(conn, username, passwordhash, question, answer):
    cursor = conn.cursor()
    default_settings = {'lastAssembly': None}
    cursor.execute('insert into users values (?, ?, ?, ?, ?)',
                   [username, passwordhash, question, answer, json.dumps(default_settings)])


class AdminDb():
    def __init__ (self):
        initdb = not os.path.exists(admindb_path)
        if initdb:
            os.makedirs(os.path.dirname(admindb_path), exist_ok=True)

        conn = connect(admindb_path)
        with conn:
            cursor = conn.cursor()
            if initdb:
                cursor.execute('create table users (email text, passwordhash text, question text, answerhash text, settings text)')
                m = hashlib.sha256()
                adminpassword = 'admin'
                m.update(adminpassword.encode('utf-16be'))
                adminpasswordhash = m.hexdigest()
                cursor.execute('insert into users values ("admin", ?, "", "", null)', (adminpasswordhash,))
                conn.commit()
                cursor.execute('create table jobs (jobid text, username text, submit date, runtime integer, numinput integer, annotators text, assembly text)')
                cursor.execute('create table config (key text, value text)')
                fernet_key = fernet.Fernet.generate_key()
                cursor.execute('insert into config (key, value) values ("fernet_key",?)',[fernet_key])
                conn.commit()
                cursor.execute("pragma journal_mode=WAL;")
            else:
                cursor.execute('select value from config where key="fernet_key"')
                fernet_key = cursor.fetchone()[0]

            self.secret_key = base64.urlsafe_b64decode(fernet_key)
            cursor.close()

    def check_password(self, username, passwordhash):
        conn = _connect()
        with conn:
            q = 'select * from users where email=? and passwordhash=?'
            for row in conn.execute(q, (username, passwordhash)):
                if row is not None:
                    return True

        return False

    def find_user(self, username):
        conn = _connect()
        with conn:
            q = 'select * from users where email=?'
            for row in conn.execute(q, (username,)):
                if row is not None:
                    return True

        return False

    def delete_user(self, username):
        conn = _connect()
        with conn:
            q = f'delete from users where email=?'
            conn.execute(q, (username,))

    def get_user_settings(self, username):
        conn = _connect()
        with conn:
            q = 'select settings from users where email=?'
            cursor = conn.cursor()
            cursor.execute(q, (username,))
            r = cursor.fetchone()
            cursor.close()

            if r is None:
                return None
            else:
                settings = r[0]
                if settings is None:
                    return {}
                else:
                    return json.loads(settings)

    def register_user(self, username, password, question, answer):
        m = hashlib.sha256()
        m.update(password.encode('utf-16be'))
        passwordhash = m.hexdigest()

        m = hashlib.sha256()
        m.update(answer.encode('utf-16be'))
        answerhash = m.hexdigest()

        conn = _connect()
        with conn:
            user_exists = _check_username_presence(conn, username)
            if user_exists:
                return False

            _add_user(conn, username, passwordhash, question, answerhash)

        return True

    def get_password_question(self, email):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute('select question from users where email=?', (email, ))
                r = cursor.fetchone()
                cursor.close()
                return r[0] if r is not None else None
            finally:
                cursor.close()

    def check_password_answer(self, email, answerhash):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute('select * from users where email=? and answerhash=?', (email, answerhash))
                r = cursor.fetchone()
                if r is None:
                    return False
                else:
                    return True
            finally:
                cursor.close()

    def set_temp_password(self, email):
        with _connect() as conn:
            temppassword = ''.join([chr(random.randint(97, 122)) for v in range(8)])
            m = hashlib.sha256()
            m.update(temppassword.encode('utf-16be'))
            temppasswordhash = m.hexdigest()

            try:
                cursor = conn.cursor()
                cursor.execute('update users set passwordhash=? where email=?', temppasswordhash, email)
                return temppassword
            finally:
                cursor.close()

    def set_username(self, email, newemail):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(f'select * from users where email=?', (newemail, ))
                r = cursor.fetchone()
                if r is not None:
                    return 'Duplicate username'

                q = f'update users set email=? where email=?'
                cursor.execute(q, (newemail, email))

                q = f'update jobs set username=? where username=?'
                cursor.execute(q, (newemail, email))

            finally:
                cursor.close()

        root_jobs_dir = au.get_jobs_dir()
        old_job_dir = os.path.join(root_jobs_dir, email)
        new_job_dir = os.path.join(root_jobs_dir, newemail)
        os.rename(old_job_dir, new_job_dir)

        return ''

    def set_password(self, email, passwordhash):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute('update users set passwordhash=? where email=?', (passwordhash, email))
            finally:
                cursor.close()

    def add_job_info(self, username, job):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                q = 'insert into jobs values (?, ?, ?, ?, ?, ?, ?)'
                cursor.execute(q, (job.info['id'],
                                   username,
                                   job.info['submission_time'],
                                   -1,
                                   -1,
                                   ','.join(job.info['annotators']),
                                   job.info['assembly']))
            finally:
                cursor.close()

    def update_user_settings(self, username, d):
        with _connect() as conn:
            newsettings = self.get_user_settings(username)
            newsettings.update(d)
            try:
                cursor = conn.cursor()
                cursor.execute('update users set settings=? where email=?',
                               [json.dumps(newsettings), username])
            finally:
                cursor.close()
