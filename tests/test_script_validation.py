import asyncio
from pathlib import Path
import pytest
import httpx
from main import PLCEmulatorApp
from src.config import ConfigManager

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def cleanup_script(name: str):
    p = SCRIPTS_DIR / name
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_validate_valid_scripts():
    cfg = ConfigManager(port=0)
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # 1. Valid periodic
            p_yaml = """
- type: periodic
  interval_ms: 100
  actions:
    - target: D100
      expr: "D100 + 1"
"""
            r1 = await client.post("/api/scripts/validate", json={"content": p_yaml})
            assert r1.status_code == 200
            assert r1.json()["valid"] is True
            assert len(r1.json()["errors"]) == 0

            # 2. Valid ramp
            r_yaml = """
- type: ramp
  target: D200
  start_value: 0
  end_value: 100
  duration_ms: 500
"""
            r2 = await client.post("/api/scripts/validate", json={"content": r_yaml})
            assert r2.status_code == 200
            assert r2.json()["valid"] is True

            # 3. Valid conditional
            c_yaml = """
- type: conditional
  interval_ms: 200
  conditions:
    - when: "D100 > 10"
      actions:
        - target: M0
          value: 1
"""
            r3 = await client.post("/api/scripts/validate", json={"content": c_yaml})
            assert r3.status_code == 200
            assert r3.json()["valid"] is True
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_validate_yaml_syntax_error():
    cfg = ConfigManager(port=0)
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # Broken indentation / unclosed bracket
            broken_yaml = """
- type: periodic
  interval_ms: [100, 200
  actions:
"""
            resp = await client.post("/api/scripts/validate", json={"content": broken_yaml})
            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is False
            assert len(data["errors"]) > 0
            assert "YAML syntax error" in data["errors"][0] or "line" in data["errors"][0].lower()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_validate_unsafe_expression():
    cfg = ConfigManager(port=0)
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # 1. Forbidden function call (__import__)
            unsafe_func = """
- type: periodic
  interval_ms: 100
  actions:
    - target: D100
      expr: "__import__('os').system('ls')"
"""
            r1 = await client.post("/api/scripts/validate", json={"content": unsafe_func})
            assert r1.status_code == 200
            assert r1.json()["valid"] is False
            assert any("unsafe" in e.lower() or "not allowed" in e.lower() for e in r1.json()["errors"])

            # 2. Attribute access
            unsafe_attr = """
- type: conditional
  conditions:
    - when: "().__class__ == tuple"
      actions:
        - target: M0
          value: 1
"""
            r2 = await client.post("/api/scripts/validate", json={"content": unsafe_attr})
            assert r2.status_code == 200
            assert r2.json()["valid"] is False

            # 3. Syntax error in expression
            expr_syntax = """
- type: periodic
  interval_ms: 100
  actions:
    - target: D100
      expr: "1 + "
"""
            r3 = await client.post("/api/scripts/validate", json={"content": expr_syntax})
            assert r3.status_code == 200
            assert r3.json()["valid"] is False
            assert any("syntax error" in e.lower() for e in r3.json()["errors"])
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_validate_invalid_device_or_structure():
    cfg = ConfigManager(port=0)
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # Invalid target device
            bad_dev = """
- type: periodic
  interval_ms: 100
  actions:
    - target: NOT_A_DEVICE
      value: 1
"""
            resp = await client.post("/api/scripts/validate", json={"content": bad_dev})
            assert resp.status_code == 200
            assert resp.json()["valid"] is False
            assert any("invalid target" in e.lower() for e in resp.json()["errors"])

            # Missing interval_ms
            missing_field = """
- type: periodic
  actions:
    - target: D100
      value: 1
"""
            resp2 = await client.post("/api/scripts/validate", json={"content": missing_field})
            assert resp2.status_code == 200
            assert resp2.json()["valid"] is False
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_start_invalid_script_is_blocked():
    cfg = ConfigManager(port=0)
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    bad_name = "test_bad.yaml"
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            bad_content = """
- type: periodic
  interval_ms: 100
  actions:
    - target: D100
      expr: "__import__('os')"
"""
            await client.put(f"/api/scripts/{bad_name}", json={"content": bad_content})

            # Attempting to start must be rejected with HTTP 400
            start_resp = await client.post(f"/api/scripts/{bad_name}/start")
            assert start_resp.status_code == 400
            assert "validation failed" in start_resp.json()["detail"].lower()

            # Engine was not started
            assert bad_name not in app.state.script_engines
    finally:
        await app.stop()
        cleanup_script(bad_name)
