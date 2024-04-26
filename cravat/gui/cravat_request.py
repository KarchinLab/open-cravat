from flask import request, g

import cravat.gui.legacy


def file_router():
    return cravat.gui.legacy.UserFileRouter(g.username, g.is_multiuser)


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
HTTP_UNAUTHORIZED = ('fail', 401, {'Content-Type': 'text/plain'})