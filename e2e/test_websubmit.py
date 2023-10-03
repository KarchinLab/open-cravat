"""
End-to-end playwright tests for websubmit

These are some simple end to end tests for major functionality (i.e. things are being displayed and clicking on them does
something). Uses pytest-xprocess to launch the web server.
"""
import re

from playwright.sync_api import Page, expect
from server_fixture import test_server


def test_websubmit(page: Page):
    res = page.request.get("http://0.0.0.0:8080/submit/nocache/index.html")
    expect(res).to_be_ok()


def test_websubmit_config_menu_is_visible(page: Page):
    page.goto("http://localhost:8080/submit/nocache/index.html")
    page.get_by_role("img").nth(3).click()
    refresh_btn = page.get_by_role("button", name="Refresh store")
    expect(refresh_btn).to_be_visible()


def test_websubmit_config_change_module_dir_persists(page: Page):
    page.goto("http://localhost:8080/submit/nocache/index.html")
    page.get_by_role("img").nth(3).click()
    page.locator("#settings_modules_dir_input").click()
    page.locator("#settings_modules_dir_input").fill("test")
    page.locator("#settings_modules_dir_input").press("Tab")
    page.get_by_role("button", name="Save").click()
    page.get_by_role("button", name="Ok").click()
    page.goto("http://localhost:8080/submit/nocache/index.html")
    page.get_by_role("img").nth(3).click()
    value = page.locator("#settings_modules_dir_input")
    expect(value).to_have_value(re.compile('.*test$'))


