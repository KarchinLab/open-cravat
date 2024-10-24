from .handlers import *
from cravat.gui.routing import relative_router


def load(application):
    server_router = relative_router("/server", application)
    server_router(r'/login', None, login)
    server_router(r'/logout', None, logout)
    server_router(r'/usersettings', None, get_user_settings)
    server_router(r'/signup', None, signup)
    server_router(r'/checklogged', None, check_logged)

    server_router(r'/passwordquestion', None, get_password_question)
    server_router(r'/passwordanswer', None, check_password_answer)
    server_router(r'/changepassword', None, change_password)
    server_router(r'/nocache/login.html', None, show_login_page)
    server_router(r'/noguest', None, get_noguest)

    server_router(r'/inputstat', None, get_input_stat)
    server_router(r'/userstat', None, get_user_stat)
    server_router(r'/jobstat', None, get_job_stat)
    server_router(r'/apistat', None, get_api_stat)
    server_router(r'/annotstat', None, get_annot_stat)
    server_router(r'/assemblystat', None, get_assembly_stat)

    # server_router(r'/restart', None, restart)
