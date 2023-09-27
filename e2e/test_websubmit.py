"""
End-to-end playwright tests for webstore

These are some simple end to end tests for major functionality (i.e. things are being displayed and clicking on them does
something). Uses pytest-xprocess to launch the web server.
TODO: Figure out how to use the configuration to launch the webserver before running tests
"""
from playwright.sync_api import Page, expect
from server_fixture import test_server


def test_webstore(page: Page):
    res = page.request.get("http://0.0.0.0:8080/submit/nocache/index.html")
    expect(res).to_be_ok()
