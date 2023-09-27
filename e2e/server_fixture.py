import pytest
from xprocess import ProcessStarter


@pytest.fixture(autouse=True, scope='module')
def test_server(xprocess):
    print('starting test server')
    class Starter(ProcessStarter):
        # startup pattern
        pattern = "OpenCRAVAT is served at"

        # command to start process
        args = ['oc', 'gui', '--headless']

    # ensure process is running and return its logfile
    logfile = xprocess.ensure("test_server", Starter)

    conn = True
    yield conn

    # clean up whole process tree afterward
    xprocess.getinfo("test_server").terminate()

