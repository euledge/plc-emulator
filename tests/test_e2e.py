import pytest
from fastapi.testclient import TestClient
from src.web.app import create_app


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(scope="session")
def server_url(app):
    import uvicorn
    import threading
    import time
    host = "127.0.0.1"
    port = 8765
    config = uvicorn.Config(app, host=host, port=port, log_level="error")
    server = uvicorn.Server(config=config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)
    return f"http://{host}:{port}"


@pytest.fixture
def api(app):
    return TestClient(app)


def test_page_title(page, server_url):
    page.goto(server_url)
    assert page.title() == "PLCEmulator"


def test_nav_bar_visible(page, server_url):
    page.goto(server_url)
    nav = page.locator("nav")
    assert nav.is_visible()


def test_nav_links_exist(page, server_url):
    page.goto(server_url)
    links = page.locator(".nav-link")
    assert links.count() == 4


def test_settings_page_default_active(page, server_url):
    page.goto(server_url)
    settings = page.locator("#page-settings")
    assert settings.is_visible()


def test_switch_to_monitor(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    monitor = page.locator("#page-monitor")
    assert monitor.is_visible()
    settings = page.locator("#page-settings")
    assert not settings.is_visible()


def test_switch_to_log(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='log']").click()
    log = page.locator("#page-log")
    assert log.is_visible()


def test_switch_to_scripts(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='scripts']").click()
    scripts = page.locator("#page-scripts")
    assert scripts.is_visible()


def test_settings_load_config(page, server_url):
    page.goto(server_url)
    port_input = page.locator("#port")
    assert port_input.is_visible()
    page.wait_for_function("document.getElementById('port').value !== ''", timeout=5000)
    val = port_input.input_value()
    assert val == "5000"


def test_settings_save_changes(page, server_url, api):
    page.goto(server_url)
    page.wait_for_selector("#protocol", timeout=5000)
    page.wait_for_timeout(1000)
    page.locator("#protocol").select_option("4E")
    page.locator("#save_config").click()
    resp = api.get("/api/config")
    assert resp.json()["protocol"] == "4E"
    page.locator("#protocol").select_option("3E")
    page.locator("#save_config").click()


def test_device_monitor_add_device(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    page.wait_for_function("document.getElementById('mon_add') !== null", timeout=5000)
    page.locator("#mon_device").select_option("D")
    page.locator("#mon_address").fill("100")
    page.locator("#mon_add").click()
    table = page.locator("#mon_table")
    assert "D" in table.text_content()
    assert "100" in table.text_content()


def test_language_switch_to_en(page, server_url):
    page.goto(server_url)
    page.locator("button[data-lang='en']").click()
    page.wait_for_timeout(500)
    title = page.locator("nav h1")
    assert title.text_content() == "PLCEmulator"


def test_language_switch_to_ja(page, server_url):
    page.goto(server_url)
    page.locator("button[data-lang='ja']").click()
    page.wait_for_timeout(500)


def test_script_editor_new(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='scripts']").click()
    page.locator("#script_new").click()
    editor = page.locator("#script_editor")
    assert editor.input_value() == ""


def test_script_editor_save_and_load(page, server_url):
    test_yaml = "type: periodic\ninterval_ms: 1000\nactions:\n  - target: D500\n    value: 99\n"
    page.goto(server_url)
    page.locator(".nav-link[data-page='scripts']").click()
    page.locator("#script_name").fill("e2e_test.yaml")
    page.locator("#script_editor").fill(test_yaml)
    page.locator("#script_save").click()
    page.wait_for_timeout(500)
    page.locator("#script_name").fill("e2e_test.yaml")
    page.locator("#script_load").click()
    page.wait_for_timeout(500)
    content = page.locator("#script_editor").input_value()
    assert "periodic" in content


def test_save_and_load_state_from_settings(page, server_url, api):
    page.goto(server_url)
    page.wait_for_selector("#btn_save_state", timeout=5000)
    api.put("/api/devices/D/500", json={"value": 7777})
    page.locator("#btn_save_state").click()
    page.wait_for_timeout(500)
    api.put("/api/devices/D/500", json={"value": 0})
    resp = api.get("/api/devices/D?start=500&count=1")
    assert resp.json()["values"][0] == 0
    page.locator("#btn_load_state").click()
    page.wait_for_timeout(500)
    resp = api.get("/api/devices/D?start=500&count=1")
    assert resp.json()["values"][0] == 7777


def test_monitor_add_device_displayed(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    page.locator("#mon_device").select_option("D")
    page.locator("#mon_address").fill("0")
    page.locator("#mon_format").select_option("DEC")
    page.locator("#mon_add").click()
    table = page.locator("#mon_table")
    content = table.text_content()
    assert "D" in content
    assert "0" in content
    assert "---" in content
