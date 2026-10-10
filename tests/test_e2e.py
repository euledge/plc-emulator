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


def test_comm_log_save_button(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='log']").click()
    page.wait_for_selector("#log_save", timeout=5000)
    assert page.locator("#log_save").is_visible()
    page.locator("#log_save").click()
    assert page.locator("#log_container").is_visible()

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
    page.wait_for_function("document.getElementById('server_status').textContent === 'Saved'", timeout=5000)
    resp = api.get("/api/config")
    assert resp.json()["protocol"] == "4E"
    page.locator("#protocol").select_option("3E")
    page.locator("#save_config").click()
    page.wait_for_function("document.getElementById('server_status').textContent === 'Saved'", timeout=5000)


def test_settings_latency_stats_panel(page, server_url):
    page.goto(server_url)
    page.wait_for_selector("#latency_stats_panel", timeout=5000)
    assert page.locator("#stat_count").is_visible()
    assert page.locator("#stat_min").is_visible()
    assert page.locator("#stat_max").is_visible()
    assert page.locator("#stat_avg").is_visible()
    page.locator("#btn_refresh_stats").click()
    page.wait_for_timeout(300)
    page.locator("#btn_reset_stats").click()
    page.wait_for_timeout(300)
    assert page.locator("#stat_count").text_content() == "0"

def test_device_monitor_add_and_edit_device(page, server_url, api):
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    page.wait_for_function("document.getElementById('mon_add') !== null", timeout=5000)
    page.locator("#mon_device").select_option("D")
    page.locator("#mon_address").fill("100")
    page.locator("#mon_add").click()
    table = page.locator("#mon_table")
    assert "D" in table.text_content()
    assert "100" in table.text_content()

    # Double-click to edit cell #val_0
    page.locator("#val_0").dblclick()
    input_el = page.locator("#edit_input_0")
    input_el.fill("9876")
    input_el.press("Enter")

    page.wait_for_function("document.getElementById('val_0').textContent === '9876'", timeout=5000)
    assert page.locator("#val_0").text_content() == "9876"

    resp = api.get("/api/devices/D?start=100&count=1")
    assert resp.json()["values"] == [9876]


def test_device_monitor_tab_switching(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    page.wait_for_selector(".device-tab", timeout=5000)

    # 1. Add D100
    page.locator("#mon_device").select_option("D")
    page.locator("#mon_address").fill("100")
    page.locator("#mon_add").click()
    assert "D" in page.locator("#mon_table").text_content()

    # 2. Switch tab to M
    page.locator(".device-tab[data-dev='M']").click()
    assert "No M devices monitored" in page.locator("#mon_table").text_content()

    # 3. Add M50 on M tab
    page.locator("#mon_address").fill("50")
    page.locator("#mon_add").click()
    table_m = page.locator("#mon_table").text_content()
    assert "M" in table_m
    assert "50" in table_m
    assert "100" not in table_m

    # 4. Switch back to D tab
    page.locator(".device-tab[data-dev='D']").click()
    table_d = page.locator("#mon_table").text_content()
    assert "D" in table_d
    assert "100" in table_d
    assert "50" not in table_d

def test_device_monitor_format_switching(page, server_url, api):
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    page.wait_for_selector("#mon_add", timeout=5000)

    # Pre-populate D300 = 65535
    api.put("/api/devices/D/300", json={"value": 65535})

    # Add D300 to monitor table
    page.locator("#mon_device").select_option("D")
    page.locator("#mon_address").fill("300")
    page.locator("#mon_add").click()
    page.wait_for_function("document.getElementById('val_0') && document.getElementById('val_0').textContent !== '---'", timeout=5000)
    assert page.locator("#val_0").text_content() == "65535"

    # Switch row format to DEC (Signed) -> -1
    page.locator(".row-format").first.select_option("DEC_SIGNED")
    page.wait_for_function("document.getElementById('val_0').textContent === '-1'", timeout=5000)
    assert page.locator("#val_0").text_content() == "-1"

    # Switch row format to HEX -> 0xFFFF
    page.locator(".row-format").first.select_option("HEX")
    page.wait_for_function("document.getElementById('val_0').textContent === '0xFFFF'", timeout=5000)
    assert page.locator("#val_0").text_content() == "0xFFFF"

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


def test_script_editor_validate_valid_and_invalid(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='scripts']").click()

    # 1. Valid YAML
    valid_yaml = "- type: periodic\n  interval_ms: 100\n  actions:\n    - target: D100\n      value: 1\n"
    page.locator("#script_editor").fill(valid_yaml)
    page.locator("#script_validate").click()
    page.wait_for_function("document.getElementById('script_validation_result').textContent.includes('Script is valid')", timeout=5000)
    result_text = page.locator("#script_validation_result").text_content()
    assert "Script is valid" in result_text

    # 2. Invalid YAML
    invalid_yaml = "- type: periodic\n  interval_ms: 100\n  actions:\n    - target: D100\n      expr: '__import__(\\'os\\')'\n"
    page.locator("#script_editor").fill(invalid_yaml)
    page.locator("#script_validate").click()
    page.wait_for_function("document.getElementById('script_validation_result').textContent.includes('Validation failed')", timeout=5000)
    result_text = page.locator("#script_validation_result").text_content()
    assert "Validation failed" in result_text

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


def test_script_editor_syntax_highlight_and_line_numbers(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='scripts']").click()
    page.wait_for_selector("#script_editor", timeout=5000)

    sample_yaml = "# Periodic counter script\n- type: periodic\n  interval_ms: 500\n  target: 'D100'\n  value: 42\n"
    page.locator("#script_editor").fill(sample_yaml)
    page.locator("#script_editor").dispatch_event("input")

    lines_gutter = page.locator("#editor_lines").text_content()
    assert lines_gutter == "1\n2\n3\n4\n5\n6"

    highlight_html = page.locator("#editor_highlight").inner_html()
    assert "Periodic counter script" in highlight_html
    assert "color:#6c757d" in highlight_html
    assert "color:#4fc3f7" in highlight_html
    assert "color:#f06292" in highlight_html


def test_script_editor_load_preset_template(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='scripts']").click()
    page.wait_for_selector("#script_template", timeout=5000)
    page.wait_for_function("document.getElementById('script_template').options.length > 1", timeout=5000)

    # Select traffic_light.yaml from templates dropdown
    page.locator("#script_template").select_option("traffic_light.yaml")
    page.locator("#script_load_template").click()

    # Verify content loaded into editor
    page.wait_for_function("document.getElementById('script_editor').value.length > 0", timeout=5000)
    content = page.locator("#script_editor").input_value()
    assert len(content) > 0
    assert "traffic_light" in page.locator("#script_name").input_value()

    # Validate loaded template
    page.locator("#script_validate").click()
    page.wait_for_function("document.getElementById('script_validation_result').textContent.includes('Script is valid')", timeout=5000)
    assert "Script is valid" in page.locator("#script_validation_result").text_content()

    # Preset template list is distinctively displayed
    assert page.locator("#template_list").is_visible()
    assert "traffic_light.yaml" in page.locator("#template_list").text_content()


def test_device_monitor_all_tab_and_multi_devices_coexistence(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    page.wait_for_selector("#mon_add", timeout=5000)

    # 1. ALL tab should be active by default
    all_tab = page.locator(".device-tab[data-dev='ALL']")
    assert "active" in all_tab.get_attribute("class")

    # 2. Add D 0 (points = 1)
    page.locator("#mon_device").select_option("D")
    page.locator("#mon_address").fill("0")
    page.locator("#mon_add").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)

    # 3. Add M 1 while on ALL tab
    page.locator("#mon_device").select_option("M")
    page.locator("#mon_address").fill("1")
    page.locator("#mon_add").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 2", timeout=5000)

    # Both D 0 and M 1 are displayed on the ALL tab simultaneously without overwriting!
    table_text = page.locator("#mon_table").inner_text()
    assert "D" in table_text
    assert "M" in table_text
    assert "0" in table_text
    assert "1" in table_text

    # 4. Filter by D tab
    page.locator(".device-tab[data-dev='D']").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)
    d_dev = page.locator("#mon_table tr td").first.text_content()
    assert d_dev == "D"

    # 5. Filter by M tab
    page.locator(".device-tab[data-dev='M']").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)
    m_dev = page.locator("#mon_table tr td").first.text_content()
    assert m_dev == "M"

    # 6. Return to ALL tab
    page.locator(".device-tab[data-dev='ALL']").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 2", timeout=5000)
    all_text = page.locator("#mon_table").inner_text()
    assert "D" in all_text
    assert "M" in all_text


def test_device_monitor_add_multiple_addresses_via_points(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    page.wait_for_selector("#mon_add", timeout=5000)

    # Add D100 with points = 5 -> D100, D101, D102, D103, D104
    page.locator("#mon_device").select_option("D")
    page.locator("#mon_address").fill("100")
    page.locator("#mon_points").fill("5")
    page.locator("#mon_add").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 5", timeout=5000)

    table_text = page.locator("#mon_table").inner_text()
    for addr in ("100", "101", "102", "103", "104"):
        assert addr in table_text

    # Deduplication: Re-adding D100 with HEX format does not add a 6th row
    page.locator("#mon_address").fill("100")
    page.locator("#mon_points").fill("1")
    page.locator("#mon_format").select_option("HEX")
    page.locator("#mon_add").click()
    page.wait_for_timeout(300)

    # Row count remains 5
    row_count = page.locator("#mon_table tr").count()
    assert row_count == 5


def test_clear_all_removes_rows_and_clears_memory(page, server_url, api):
    api.put("/api/devices/D/0", json={"value": 1234})
    api.put("/api/devices/D/1", json={"value": 5678})

    page.on("dialog", lambda dialog: dialog.accept())
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    page.wait_for_selector("#mon_add", timeout=5000)

    # Add D0 and D1
    page.locator("#mon_device").select_option("D")
    page.locator("#mon_address").fill("0")
    page.locator("#mon_points").fill("2")
    page.locator("#mon_add").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 2", timeout=5000)
    assert page.locator("#mon_table tr").count() == 2

    # Click Clear All
    page.locator("#mon_clear").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr td').length === 1", timeout=5000)

    table_text = page.locator("#mon_table").inner_text()
    assert "No devices monitored" in table_text

    # Verify memory is reset to 0 in backend
    resp = api.get("/api/devices/D?start=0&count=2")
    assert resp.json()["values"] == [0, 0]

    # Add new device after clear
    page.locator("#mon_address").fill("10")
    page.locator("#mon_points").fill("1")
    page.locator("#mon_add").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)
    new_text = page.locator("#mon_table").inner_text()
    assert "10" in new_text


def test_clear_all_cancel_retains_rows(page, server_url):
    page.on("dialog", lambda dialog: dialog.dismiss())
    page.goto(server_url)
    page.locator(".nav-link[data-page='monitor']").click()
    page.wait_for_selector("#mon_add", timeout=5000)

    # Add D0
    page.locator("#mon_device").select_option("D")
    page.locator("#mon_address").fill("0")
    page.locator("#mon_add").click()
    page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)

    # Click Clear All and dismiss
    page.locator("#mon_clear").click()
    page.wait_for_timeout(300)

    # Row still retained
    assert page.locator("#mon_table tr").count() == 1


def test_script_editor_direct_start_without_prior_save(page, server_url):
    page.goto(server_url)
    page.locator(".nav-link[data-page='scripts']").click()
    page.wait_for_selector("#script_editor", timeout=5000)

    # User clicks New script
    page.locator("#script_new").click()

    # User types YAML directly into editor (with name left blank)
    user_yaml = "type: periodic\ninterval_ms: 1000\nactions:\n  - target: D100\n    value: 99\n"
    page.locator("#script_editor").fill(user_yaml)

    # User clicks Start directly without manually clicking Save first
    page.locator("#script_start").click()

    # Status must transition to running!
    page.wait_for_function(
        "document.getElementById('script_status') && document.getElementById('script_status').textContent === 'running'",
        timeout=5000
    )
    status_text = page.locator("#script_status").text_content()
    assert status_text == "running"

    # Clean up: stop the running script
    page.locator("#script_stop").click()
    page.wait_for_function(
        "document.getElementById('script_status') && document.getElementById('script_status').textContent === 'stopped'",
        timeout=5000
    )
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "scripts" / "untitled.yaml"
    if p.exists():
        p.unlink()
