# Automated Tests

Open Cravat tests are separated into two sections. The `tests/` directory contains unit tests for core cravat functionality, and the `e2e/` directory contains end-to-end tests for the Open Cravat web interface.

These tests use the `pytest` package as the test runner, and the end-to-end tests use `playwright` to tests within browsers. These dependencies need to be installed to run the automated tests.

## Installing Test Dependencies

We have included a `requirements.txt` file in this directory for installing test dependencies. To install, run:
```shell
pip install -r tests/requirements.txt
```

To run end-to-end tests, Playwright also needs to install browsers that it can interact with. After installing the test requirements, run this command to get playwright ready:
```shell
playwright install
```

## Running Tests

Once all dependencies are installed, all tests can be run with:
```shell
pytest
```

During the end-to-end tests, the module and jobs directories will be changed to `e2e/test_modules` and `e2e/test_jobs`, respectively. They will be restored when the tests are finished.
Note that the first time tests are run, the base modules will be installed, which may take minutes to complete.

## Installing and Running Only Unit Tests (No End-To-End)

If you are interested in running the Open Cravat unit tests without the end-to-end tests of the web interface, you do not need to install all the test requirements. All you need is `pytest`, so you could run:
```shell
pip install pytest
```
Then once `pytest` is installed, you can run unit tests only with:
```shell
pytest tests/
```
