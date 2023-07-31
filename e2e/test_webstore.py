"""
End-to-end playwright tests for websubmit

These are some simple end to end tests for major functionality (i.e. things are being displayed and clicking on them does
something). Currently, we need to run `oc gui` first to launch a local instance to test.
TODO: Figure out how to use the configuration to launch the webserver before running tests
TODO: Set up fixtures to get consistent data for testing (installed modules, jobs, etc)
"""
import re
from playwright.sync_api import Page, expect


def test_websubmit(page: Page):
    res = page.request.get("http://0.0.0.0:8080/submit/nocache/index.html")
    expect(res).to_be_ok()


def test_websubmit_has_title(page: Page):
    page.goto("http://0.0.0.0:8080/submit/nocache/index.html")

    # Expect a title "to contain" a substring.
    expect(page).to_have_title("open-cravat submit")


def test_websubmit_click_variant_annotation_category_shows_aloft(page: Page):
    page.goto("http://0.0.0.0:8080/submit/nocache/index.html")
    page.wait_for_timeout(2000) # auto-wait didn't seem to wait for the click handler to be attached
    page.locator(".submit-annot-tag").get_by_text("Variants", exact=True).click()
    aloft_checkbox = page.locator("#annotator-select-div").get_by_text("ALoFT", exact=True)
    expect(aloft_checkbox).to_be_visible()


def test_websubmit_click_store_tab_navigates_to_store(page: Page):
    page.goto("http://0.0.0.0:8080/submit/nocache/index.html")
    page.wait_for_timeout(2000) # auto-wait didn't seem to wait for the click handler to be attached
    page.get_by_text("STORE", exact=True).click()
    store_div = page.locator("#store-home-div")
    expect(store_div).to_be_visible()
