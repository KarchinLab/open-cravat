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
    page.get_by_role("img", name="Settings").click()
    refresh_btn = page.get_by_role("button", name="Refresh store")
    expect(refresh_btn).to_be_visible()


def test_websubmit_help_button_shows_links(page: Page):
    page.goto('http://localhost:8080/submit/nocache/index.html')
    page.get_by_role("img", name="Help and Contact").click()
    discussion_link = page.get_by_role("link", name="Discussions Ask questions and provide feedback on our discussion board.")
    expect(discussion_link).to_be_visible()


def test_websubmit_right_click_annotator_shows_info(page: Page):
    page.goto('http://localhost:8080/submit/nocache/index.html')
    page.get_by_role("button", name="All").click()  # make sure annotators are visible
    page.get_by_title("Right-click to see details.").click(button="right")  # right click only annotator (GO)
    info_div = page.get_by_role("cell", name="Gene Ontology annotator |").locator("div")
    expect(info_div).to_be_visible()


def test_websubmit_existing_job_is_displayed(page: Page):
    with page.expect_response('http://0.0.0.0:8080/submit/jobs') as jobs_response:
        page.goto("http://0.0.0.0:8080/submit/nocache/index.html")

    job_label = page.get_by_role("cell", name="fake test job", exact=True)
    expect(job_label).to_be_visible()
    # page.get_by_role("cell", name="2023.10.04 11:25:36", exact=True).click()
    # page.get_by_role("cell", name="test one line", exact=True).click()

def test_websubmit_db_download_is_displayed(page: Page):
    with page.expect_response('http://0.0.0.0:8080/submit/jobs') as jobs_response:
        page.goto("http://0.0.0.0:8080/submit/nocache/index.html")

    jobs_table = page.locator("#jobs-table")
    first_row = jobs_table.locator('tbody').locator('tr').nth(0)
    download_cell = first_row.locator('td').nth(7)
    download_btn = download_cell.get_by_text('DB', exact=True)
    expect(download_btn).to_be_visible()
    expect(download_btn).to_have_class('butn active-download-button')

def test_websubmit_new_job_is_displayed(page: Page):
    with page.expect_response('http://0.0.0.0:8080/submit/jobs') as jobs_response:
        page.goto("http://0.0.0.0:8080/submit/nocache/index.html")

    input_field = page.get_by_placeholder("Enter variants in a supported input format such as VCF or TSV, or type a list of the paths to input files in the server.")
    input_field.fill("chr1\t114716160\t-\tA\tT\ts3\tvar016")
    name_field = page.get_by_placeholder("Enter a note for the analysis (optional)")
    name_field.fill("auto_run")
    page.get_by_role("button", name="ANNOTATE").click()
    job_label = page.get_by_role("cell", name="auto_run", exact=True)
    expect(job_label).to_be_visible()


"""
# TODO: Consider updating the server configuration code to restore original settings before every test

This test alters the system configuration by changing the module directory, so any tests that require even
the base modules to be installed will fail if they run after this one. i.e.

RUN THIS TEST LAST
"""
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
