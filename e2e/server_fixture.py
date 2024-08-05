import shutil

import pytest
from xprocess import ProcessStarter
import subprocess
import os
from playwright.sync_api import Page, APIRequestContext, Playwright

import cravat.admin_util as au


test_job_json = """
{
  "annotator_version": {
    "original_input": ""
  },
  "annotators": [
    "original_input"
  ],
  "assembly": "hg38",
  "cc_cohorts_path": "",
  "db_path": "/home/user/example/path/12345-67890/input.sqlite",
  "id": "12345-67890",
  "job_dir": "/home/user/example/path/12345-67890",
  "note": "fake test job",
  "num_error_input": 0,
  "num_input_var": 1,
  "num_unique_var": 1,
  "open_cravat_version": "2.4.1",
  "orig_input_fname": [
    "input"
  ],
  "orig_input_path": [
    "/home/user/example/path/12345-67890/input"
  ],
  "reports": [],
  "run_name": "input",
  "status": "Finished",
  "submission_time": "2023-10-04T11:25:36.372592",
  "viewable": false
}
"""


def get_base_dir() -> str:
    cwd = str(os.getcwd())
    print(cwd)
    if cwd.endswith('e2e') or cwd.endswith('test'):
        os.chdir('..')
    return str(os.getcwd())


@pytest.fixture(autouse=True, scope='module')
def test_server(xprocess):
    print('starting test server')

    class Starter(ProcessStarter):
        # startup pattern
        pattern = "OpenCRAVAT is served at"

        # command to start process
        args = ['oc', 'gui', '--headless']

    # get current module directory
    module_dir = str(subprocess.getoutput('oc config md'))
    admin_config = au.get_system_conf()
    orig_jobs_dir = admin_config['jobs_dir']

    base_dir = get_base_dir()

    # check that the e2e dir is in the working directory
    e2e_path = os.path.join(base_dir, 'e2e')
    if not os.path.isdir(e2e_path):
        os.makedirs(e2e_path)
    # check that test_modules is in the working directory
    test_module_dir = os.path.join(e2e_path, 'test_modules')
    if not os.path.isdir(test_module_dir):
        os.makedirs(test_module_dir)

    # check that the test_jobs directory exists in the working directory
    test_jobs_dir = os.path.join(e2e_path, 'test_jobs')
    if not os.path.isdir(test_jobs_dir):
        os.makedirs(test_jobs_dir)

    # clean the test_jobs directory
    for f in os.listdir(test_jobs_dir):
        path = os.path.join(test_jobs_dir, f)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        except OSError as e:
            print(f'Could not delete {path}. Reason: {e}')

    # create a test job
    test_job_path = os.path.join(test_jobs_dir, 'default', '12345-67890')
    os.makedirs(test_job_path)
    test_job_file = os.path.join(test_job_path, 'input.status.json')
    with open(test_job_file, 'w') as f:
        f.write(test_job_json)

    # store email settings and opt-out to avoid pop-up
    email = admin_config['user_email']
    email_opt_out = admin_config['user_email_opt_out']
    admin_config['user_email'] = ''
    admin_config['user_email_opt_out'] = True
    # change the config to new test jobs dir
    admin_config['jobs_dir'] = test_jobs_dir
    au.update_system_conf_file(admin_config)

    # change oc module directory to test modules and make sure that the base modules are installed
    subprocess.run(['oc', 'config', 'md', test_module_dir])
    modules = str(subprocess.getoutput(f'oc module ls'))
    if 'hg38' not in modules:
        subprocess.run(['oc', 'module', 'install-base'])


    # ensure process is running and return its logfile
    logfile = xprocess.ensure("test_server", Starter)

    # request conf file

    conn = True
    yield conn

    # clean up whole process tree afterward
    xprocess.getinfo("test_server").terminate()

    # change the working directory back to original
    subprocess.run(['oc', 'config', 'md', module_dir])

    admin_config['jobs_dir'] = orig_jobs_dir
    admin_config['user_email'] = email
    admin_config['user_email_opt_out'] = email_opt_out
    au.update_system_conf_file(admin_config)

