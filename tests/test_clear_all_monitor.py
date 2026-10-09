import pytest
import httpx
from playwright.async_api import async_playwright
from main import PLCEmulatorApp
from src.config import ConfigManager


@pytest.mark.asyncio
async def test_clear_all_removes_rows_and_clears_memory():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    # Pre-populate device memory
    app.device_manager.write_word("D", 0, 1234)
    app.device_manager.write_word("D", 1, 5678)
    await app.start()
    try:
        web_port = app.actual_web_port
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            # Accept confirm dialogs
            page.on("dialog", lambda dialog: dialog.accept())

            await page.goto(f"http://127.0.0.1:{web_port}")
            await page.locator(".nav-link[data-page='monitor']").click()
            await page.wait_for_selector("#mon_add", timeout=5000)

            # 1. Add D0 and D1
            await page.locator("#mon_device").select_option("D")
            await page.locator("#mon_address").fill("0")
            await page.locator("#mon_points").fill("2")
            await page.locator("#mon_add").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 2", timeout=5000)
            assert await page.locator("#mon_table tr").count() == 2

            # 2. Click Clear All
            await page.locator("#mon_clear").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr td').length === 1", timeout=5000)

            # Table is cleared: shows empty message, no device rows
            table_text = await page.locator("#mon_table").inner_text()
            assert "No devices monitored" in table_text
            assert "1234" not in table_text
            assert "5678" not in table_text

            # 3. Verify memory is reset to 0 in backend
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
                resp = await client.get("/api/devices/D?start=0&count=2")
                assert resp.json()["values"] == [0, 0]

            # 4. Add new device after clear
            await page.locator("#mon_address").fill("10")
            await page.locator("#mon_points").fill("1")
            await page.locator("#mon_add").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)
            new_text = await page.locator("#mon_table").inner_text()
            assert "10" in new_text

            await browser.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_clear_all_cancel_retains_rows():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            # Dismiss confirm dialog
            page.on("dialog", lambda dialog: dialog.dismiss())

            await page.goto(f"http://127.0.0.1:{web_port}")
            await page.locator(".nav-link[data-page='monitor']").click()
            await page.wait_for_selector("#mon_add", timeout=5000)

            # Add D0
            await page.locator("#mon_device").select_option("D")
            await page.locator("#mon_address").fill("0")
            await page.locator("#mon_add").click()
            await page.wait_for_function("document.querySelectorAll('#mon_table tr').length === 1", timeout=5000)

            # Click Clear All and dismiss
            await page.locator("#mon_clear").click()
            await page.wait_for_timeout(300)

            # Row still retained
            assert await page.locator("#mon_table tr").count() == 1

            await browser.close()
    finally:
        await app.stop()
