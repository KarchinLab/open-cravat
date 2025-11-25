import base64
import hashlib
import json
import os
import random
import time

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
                cursor.execute('update users set passwordhash=? where email=?', (temppasswordhash, email))
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

    def get_assembly_stat(self, start_date, end_date):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                q = 'select assembly, count(*) as c from jobs where submit>="{}" and submit<="{}T23:59:59" group by assembly order by c desc'.format(start_date, end_date)
                cursor.execute(q)

                rows = cursor.fetchall()
                assembly_count = []

                for row in rows:
                    (assembly, count) = row
                    assembly_count.append([assembly, count])

                return assembly_count
            finally:
                cursor.close()

    def get_annot_stat(self, start_date, end_date):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                q = 'select annotators from jobs where submit>="{}" and submit<="{}T23:59:59"'.format(start_date, end_date)
                cursor.execute(q)
                rows = cursor.fetchall()

                annot_count = {}
                for row in rows:
                    annots = row[0].split(',')
                    for annot in annots:
                        if not annot in annot_count:
                            annot_count[annot] = 0
                        annot_count[annot] += 1
                return {'annot_count': annot_count}
            finally:
                cursor.close()

    def get_api_stat (self, start_date, end_date):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                q = f'select sum(count) from apilog where writetime>="{start_date}" and writetime<="{end_date}T23:59:59"'
                cursor.execute(q)
                row = cursor.fetchone()
                if row[0] is None:
                    num_api_access = 0
                else:
                    num_api_access = row[0]
                return {'num_api_access': num_api_access}
            finally:
                cursor.close()

    def get_user_stat(self, start_date, end_date):
        with _connect() as conn:
            try:
                cursor = conn.cursor()

                q = 'select count(distinct username) from jobs where submit>="{}" and submit<="{}T23:59:59"'.format(
                    start_date,
                    end_date)
                cursor.execute(q)
                row = cursor.fetchone()
                if row is None:
                    num_unique_users = 0
                else:
                    num_unique_users = row[0]

                q = 'select username, count(*) as c from jobs where submit>="{}" and submit<="{}T23:59:59" group by username order by c desc limit 1'.format(
                    start_date, end_date)
                cursor.execute(q)
                row = cursor.fetchone()
                if row is None:
                    (frequent_user, frequent_user_num_jobs) = (0, 0)
                else:
                    (frequent_user, frequent_user_num_jobs) = row

                q = 'select username, sum(numinput) s from jobs where submit>="{}" and submit<="{}T23:59:59" group by username order by s desc limit 1'.format(
                    start_date, end_date)
                cursor.execute(q)
                row = cursor.fetchone()
                if row is None:
                    (heaviest_user, heaviest_user_num_input) = (0, 0)
                else:
                    (heaviest_user, heaviest_user_num_input) = row

                response = {'num_uniq_user': num_unique_users, 'frequent': [frequent_user, frequent_user_num_jobs],
                            'heaviest': [heaviest_user, heaviest_user_num_input]}
            finally:
                cursor.close()

        return response

    def get_input_stat (self, start_date, end_date):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                q = 'select sum(numinput), max(numinput), avg(numinput) from jobs where submit>="{}" and submit<="{}T23:59:59" and numinput!=-1'.format(start_date, end_date)
                cursor.execute(q)
                row = cursor.fetchall()
                row = row[0]

                s = row[0] if row[0] is not None else 0
                m = row[1] if row[1] is not None else 0
                a = row[2] if row[2] is not None else 0
                response = [s, m, a]
            finally:
                cursor.close()

        return response

    def get_job_stat(self, start_date, end_date):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                q = 'select count(*) from jobs where submit>="{}" and submit<="{}T23:59:59"'.format(start_date, end_date)
                cursor.execute(q)
                row = cursor.fetchone()
                if row is None:
                    num_jobs = 0
                else:
                    num_jobs = row[0]

                q = 'select date(submit) as d, count(*) as c from jobs where submit>="{}" and submit<="{}T23:59:59" group by d order by d asc'.format(
                    start_date, end_date)
                cursor.execute(q)
                rows = cursor.fetchall()
                submits = []
                counts = []
                for row in rows:
                    submits.append(row[0])
                    counts.append(row[1])

                response = {'num_jobs': num_jobs, 'chartdata': [submits, counts]}
            finally:
                cursor.close()

        return response

    def write_single_api_access_count_to_db (self, t, count):
        with _connect() as conn:
            try:
                cursor = conn.cursor()
                ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))
                q = f'insert into apilog values ("{ts}", {count})'
                cursor.execute(q)
            finally:
                cursor.close()
