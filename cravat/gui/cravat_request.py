from flask import request, current_app

import cravat.gui.legacy


def is_multiuser_server():
    return request.environ.get('CRAVAT_MULTIUSER', False)


def request_user():
    if not is_multiuser_server():
        return 'default'
    else:
        return request.environ.get('CRAVAT_USER', None)


def file_router():
    return cravat.gui.legacy.UserFileRouter(request_user(), is_multiuser_server())


def jobid_and_db_path():
    job_id = request.values.get('job_id', None)
    db_path = request.values.get('dbpath', None)

    if not db_path:
        if job_id:
            router = file_router()
            job = router.load_job(job_id)
            db_path = job.db_path
        else:
            return None, None

    return job_id, db_path


HTTP_NO_CONTENT = ('', 204)
HTTP_BAD_REQUEST = ('', 400)
