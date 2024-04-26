import base64
import hashlib
import json
import os

from cryptography import fernet
from sqlite3 import connect

from cravat.constants import admindb_path

class AdminDb ():
    def __init__ (self):
        initdb = not os.path.exists(admindb_path)
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
        conn = self._connect()
        with conn:
            q = 'select * from users where email=? and passwordhash=?'
            for row in conn.execute(q, (username, passwordhash)):
                if row is not None:
                    return True

        return False

    def find_user(self, username):
        conn = self._connect()
        with conn:
            q = 'select * from users where email=?'
            for row in conn.execute(q, (username,)):
                if row is not None:
                    return True

        return False

    def delete_user(self, username):
        conn = self._connect()
        with conn:
            q = f'delete from users where email=?'
            conn.execute(q, (username,))

    def get_user_settings(self, username):
        conn = self._connect()
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

        conn = self._connect()
        with conn:
            user_exists = self._check_username_presence(conn, username)
            if user_exists:
                return False

            self._add_user(conn, username, passwordhash, question, answerhash)

        return True

    def _connect(self):
        return connect(admindb_path)

    def _check_username_presence(self, conn, username):
        cursor = conn.cursor()
        cursor.execute('select * from users where email=?', (username,))
        r = cursor.fetchone()
        cursor.close()

        if r is None:
            return False
        else:
            return True

    def _add_user(self, conn, username, passwordhash, question, answer):
        cursor = conn.cursor()
        default_settings = {'lastAssembly': None}
        cursor.execute('insert into users values (?, ?, ?, ?, ?)',
                       [username, passwordhash, question, answer, json.dumps(default_settings)])
