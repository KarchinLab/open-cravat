import datetime
import hashlib

from functools import cached_property

from cravat import admin_util as au
from .db import AdminDb

class User:
    def __init__(self, username):
        self.username = username

    def __str__(self):
        return self.username

    @property
    def guest(self):
        return False

    @cached_property
    def admin(self):
        system_conf = au.get_system_conf()
        admin_list = system_conf.get('admin_list', ["admin"])
        return self.username in admin_list

    def login_response(self):
        return self.username

    @staticmethod
    def authenticate(username, password):
        admindb = AdminDb()
        m = hashlib.sha256()
        m.update(password.encode('utf-16be'))
        passwordhash = m.hexdigest()
        if admindb.check_password(username, passwordhash):
            return User(username)

        return None

    @staticmethod
    def find_by_email(email):
        admindb = AdminDb()
        user = None
        if admindb.find_user(email):
            user = User(email)

        return user

class GuestUser(User):
    def __init__(self, username):
        super().__init__(username)

    def guest(self):
        return True

    def login_response(self):
        days_passed, guest_lifetime = self._guest_lifetimes()
        return f'guest_success_{guest_lifetime - days_passed}'

    @property
    def active(self):
        days_passed, guest_lifetime = self._guest_lifetimes()
        return days_passed > guest_lifetime

    def _guest_lifetimes(self):
        system_conf = au.get_system_conf()
        datestr = self.username.split('_')[2]
        creation_date = datetime.datetime(
            int(datestr[:4]),
            int(datestr[4:6]),
            int(datestr[6:8]))
        current_date = datetime.datetime.now()
        days_passed = (current_date - creation_date).days
        guest_lifetime = system_conf.get('guest_lifetime', 7)
        return days_passed, guest_lifetime

    def expire(self):
        admindb = AdminDb()
        admindb.delete_guest_user(self.username)
