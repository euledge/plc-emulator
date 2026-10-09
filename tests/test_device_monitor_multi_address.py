import pytest
from playwright.async_api import async_playwright
from main import PLCEmulatorApp
from src.config import ConfigManager


@pytest.mark.asyncio
async def test_device_monitor_all_tab_and_multi_devices_coexistence():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(f"http://127.0.0.1:{web_port}")
            await page.locator(".nav-link[data-page='monitor']").click()
            await page.wait_for_selector("#mon_add", timeout=5000)

            # 1. ALL tab should be active by default
            all_tab = page.locator(".device-tab[data-dev='ALL']")
            assert "active" in (await all_tab.get_attribute("class"))

            # 2. Add D 0 (points = 1)
            await page.locator("#mon_device").select_option("D")
            await page.locator("#mon_address").fill("0")
            await page.locator("#mon_add").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)

            # 3. Add M 1 while on ALL tab
            await page.locator("#mon_device").select_option("M")
            await page.locator("#mon_address").fill("1")
            await page.locator("#mon_add").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 2", timeout=5000)

            # Both D 0 and M 1 are displayed on the ALL tab simultaneously without overwriting!
            table_text = await page.locator("#mon_table").inner_text()
            assert "D" in table_text
            assert "M" in table_text
            assert "0" in table_text
            assert "1" in table_text

            # 4. Filter by D tab
            await page.locator(".device-tab[data-dev='D']").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)
            d_dev = await page.locator("#mon_table tr td").first.text_content()
            assert d_dev == "D"

            # 5. Filter by M tab
            await page.locator(".device-tab[data-dev='M']").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)
            m_dev = await page.locator("#mon_table tr td").first.text_content()
            assert m_dev == "M"

            # 6. Return to ALL tab
            await page.locator(".device-tab[data-dev='ALL']").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 2", timeout=5000)
            all_text = await page.locator("#mon_table").inner_text()
            assert "D" in all_text
            assert "M" in all_text

            await browser.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_device_monitor_add_multiple_addresses_via_points():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(f"http://127.0.0.1:{web_port}")
            await page.locator(".nav-link[data-page='monitor']").click()
            await page.wait_for_selector("#mon_add", timeout=5000)

            # Add D100 with points = 5 -> D100, D101, D102, D103, D104
            await page.locator("#mon_device").select_option("D")
            await page.locator("#mon_address").fill("100")
            await page.locator("#mon_points").fill("5")
            await page.locator("#mon_add").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 5", timeout=5000)

            table_text = await page.locator("#mon_table").inner_text()
            for addr in ("100", "101", "102", "103", "104"):
                assert addr in table_text

            # Deduplication: Re-adding D100 with HEX format does not add a 6th row
            await page.locator("#mon_address").fill("100")
            await page.locator("#mon_points").fill("1")
            await page.locator("#mon_format").select_option("HEX")
            await page.locator("#mon_add").click()
            await page.wait_for_timeout(300)

            # Row count remains 5
            row_count = await page.locator("#mon_table tr").count()
            assert row_count == 5

            await browser.close()
    finally:
        await app.stop()
