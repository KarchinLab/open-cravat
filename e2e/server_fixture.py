import shutil

import pytest
from xprocess import ProcessStarter
import subprocess
import os


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

    base_dir = get_base_dir()
    # get copy of config file
    config_path = os.path.join(base_dir, 'cravat', 'cravat.yml')
    with open(config_path, 'r', encoding='us-ascii') as f:
        original_config = f.read()

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

    # change the working directory to test_jobs for clean tests, delete any jobs that exist
    os.chdir(test_jobs_dir)
    for f in os.listdir(test_jobs_dir):
        path = os.path.join(test_jobs_dir, f)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        except OSError as e:
            print(f'Could not delete {path}. Reason: {e}')

    # change oc module directory to test modules and make sure that the base modules are installed
    subprocess.run(['oc', 'config', 'md', test_module_dir])
    modules = str(subprocess.getoutput(f'oc module ls'))
    if 'hg38' not in modules:
        subprocess.run(['oc', 'module', 'install-base'])

    # ensure process is running and return its logfile
    logfile = xprocess.ensure("test_server", Starter)

    conn = True
    yield conn

    # clean up whole process tree afterward
    xprocess.getinfo("test_server").terminate()

    # change the working directory back to original
    os.chdir(base_dir)
    # restore original config
    with open(config_path, 'w', encoding='us-ascii') as f:
        f.write(original_config)
    subprocess.run(['oc', 'config', 'md', module_dir])
