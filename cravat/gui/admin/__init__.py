from flask import current_app

from cravat.gui.cravat_request import request_user


def is_admin_loggedin():
    user = request_user()
    if not user:
        return False
    system_conf = current_app.config['CRAVAT_SYSCONF']
    admin_list = system_conf.get('admin_list', ["admin"])

    return user in admin_list
