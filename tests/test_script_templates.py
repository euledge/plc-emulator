import pytest
import httpx
from main import PLCEmulatorApp
from src.config import ConfigManager


@pytest.mark.asyncio
async def test_list_and_get_script_templates():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            resp = await client.get("/api/scripts/templates")
            assert resp.status_code == 200
            templates = resp.json()
            assert isinstance(templates, list)
            assert "traffic_light.yaml" in templates
            assert "tank_level_control.yaml" in templates

            resp2 = await client.get("/api/scripts/templates/traffic_light.yaml")
            assert resp2.status_code == 200
            data = resp2.json()
            assert data["name"] == "traffic_light.yaml"
            assert "periodic" in data["content"] or "sequence" in data["content"] or "traffic" in data["content"]

            resp_404 = await client.get("/api/scripts/templates/non_existent.yaml")
            assert resp_404.status_code == 404
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_templates_cannot_be_overwritten_by_user_save():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # Attempt to overwrite examples/ file via path traversal
            resp = await client.put(
                "/api/scripts/examples%2Ftraffic_light.yaml",
                json={"content": "malicious content"}
            )
            assert resp.status_code in (400, 404)

            resp2 = await client.put(
                "/api/scripts/..%2Fexamples%2Ftraffic_light.yaml",
                json={"content": "malicious content"}
            )
            assert resp2.status_code in (400, 404)
    finally:
        await app.stop()
