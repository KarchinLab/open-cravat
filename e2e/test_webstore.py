"""
End-to-end playwright tests for websubmit

These are some simple end-to-end tests for major functionality (i.e. things are being displayed and clicking on them does
something). Uses pytest-xprocess to launch the web server.
"""
import re

from playwright.sync_api import Page, expect
import pytest
from xprocess import ProcessStarter
from server_fixture import test_server



def add_complete_response(response, completed_set):
    completed_set.append(response.url)


def test_websubmit(page: Page):
    res = page.request.get("http://0.0.0.0:8080/submit/nocache/index.html")
    expect(res).to_be_ok()


def test_websubmit_has_title(page: Page):
    page.goto("http://0.0.0.0:8080/submit/nocache/index.html")

    # Expect a title "to contain" a substring.
    expect(page).to_have_title("open-cravat submit")


def test_websubmit_click_gene_annotation_category_shows_go(page: Page):
    # Ensure packages are loaded before testing
    annotators_loaded = False
    retries = 3
    while not annotators_loaded and retries > 0:
        with page.expect_response('http://0.0.0.0:8080/submit/annotators') as response:
            page.goto("http://0.0.0.0:8080/submit/nocache/index.html")
        body = response.value.body()
        annotators_loaded = body is not None and body != b'{}'
        print(f'packages_loaded: {annotators_loaded}\nsubmit/packages:\n{response.value.body()}')
        retries -= 1

    # Click the Genes category, then make sure GO is visible
    # page.locator("div").filter(has_text=re.compile(r"^Genes$")).click()
    container = page.locator("div").filter(has_text=re.compile(r"^Genes$"))
    # TODO: The annotators widget has a similar issue to the module filter, needs to be refreshed before it works
    #       Find a way to fix this
    container.get_by_text("Genes", exact=True).click()
    container.get_by_text("Genes", exact=True).click()
    container.get_by_text("Genes", exact=True).click()
    go_checkbox = page.locator("#annotator-select-div").get_by_text("Gene Ontology", exact=True)

    expect(go_checkbox).to_be_visible()


def test_websubmit_click_store_tab_navigates_to_store(page: Page):
    page.goto("http://0.0.0.0:8080/submit/nocache/index.html")
    page.get_by_text("STORE", exact=True).click()
    store_div = page.locator("#store-home-div")
    expect(store_div).to_be_visible()


def test_webstore_search_for_annotator_and_click_shows_info_modal(page: Page) -> None:
    annotators_loaded = False
    retries = 3
    while not annotators_loaded and retries > 0:
        with page.expect_response('http://0.0.0.0:8080/store/remote') as response:
            page.goto("http://0.0.0.0:8080/submit/nocache/index.html")
        body = str(response.value.body())
        annotators_loaded = body is not None and body != '{}' and 'clinvar' in body
        print(f'packages_loaded contains "clinvar": {"clinvar" in body}')
        retries -= 1

    page.get_by_text("STORE", exact=True).click()

    # TODO: something is weird with the initial load of the store filter
    # The first filter does not load, so we filter, clear, and re-filter
    page.get_by_placeholder("Search the Store").focus()
    page.get_by_placeholder("Search the Store").fill("clinvar")
    page.get_by_placeholder("Search the Store").fill("")
    page.get_by_placeholder("Search the Store").fill("clinvar")

    # check clinvar logo is visible
    logo = page.locator("#remotemodulepanels #logodiv_clinvar").get_by_role("img")
    expect(logo).to_be_visible()
    #check clinvar title is visible
    title = page.get_by_role("cell", name="ClinVar annotator | NCBI")
    expect(logo).to_be_visible()

