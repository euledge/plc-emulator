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
async def test_start_and_stop_by_name():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    script_name = "test_counter.yaml"
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            script_content = "- type: periodic\n  interval_ms: 40\n  actions:\n    - target: D500\n      expr: 'D500 + 1'\n"
            save_resp = await client.put(f"/api/scripts/{script_name}", json={"content": script_content})
            assert save_resp.status_code == 200

            # Initial status is stopped
            status_resp = await client.get(f"/api/scripts/{script_name}/status")
            assert status_resp.status_code == 200
            assert status_resp.json()["status"] == "stopped"

            # Start script
            start_resp = await client.post(f"/api/scripts/{script_name}/start")
            assert start_resp.status_code == 200
            assert start_resp.json()["status"] == "running"

            # Check status is running
            status_resp = await client.get(f"/api/scripts/{script_name}/status")
            assert status_resp.json()["status"] == "running"

            # Wait for device to count up
            await asyncio.sleep(0.15)
            val1 = app.device_manager.read_word("D", 500)
            assert val1 >= 2

            # Stop script
            stop_resp = await client.post(f"/api/scripts/{script_name}/stop")
            assert stop_resp.status_code == 200
            assert stop_resp.json()["status"] == "stopped"

            # Check status is stopped
            status_resp = await client.get(f"/api/scripts/{script_name}/status")
            assert status_resp.json()["status"] == "stopped"

            val_at_stop = app.device_manager.read_word("D", 500)
            await asyncio.sleep(0.1)
            val_after_stop = app.device_manager.read_word("D", 500)
            # Updates must have stopped!
            assert val_after_stop == val_at_stop
    finally:
        await app.stop()
        cleanup_script(script_name)


@pytest.mark.asyncio
async def test_pause_and_resume_script():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    script_name = "test_pause.yaml"
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            script_content = "- type: periodic\n  interval_ms: 30\n  actions:\n    - target: D600\n      expr: 'D600 + 1'\n"
            await client.put(f"/api/scripts/{script_name}", json={"content": script_content})

            # Start script
            await client.post(f"/api/scripts/{script_name}/start")
            await asyncio.sleep(0.1)
            val_running = app.device_manager.read_word("D", 600)
            assert val_running >= 2

            # Pause script
            pause_resp = await client.post(f"/api/scripts/{script_name}/pause")
            assert pause_resp.status_code == 200
            assert pause_resp.json()["status"] == "paused"

            # Status is paused
            status_resp = await client.get(f"/api/scripts/{script_name}/status")
            assert status_resp.json()["status"] == "paused"

            val_paused = app.device_manager.read_word("D", 600)
            await asyncio.sleep(0.1)
            val_after_pause_wait = app.device_manager.read_word("D", 600)
            # Value must NOT advance while paused!
            assert val_after_pause_wait == val_paused

            # Resume script via /resume
            resume_resp = await client.post(f"/api/scripts/{script_name}/resume")
            assert resume_resp.status_code == 200
            assert resume_resp.json()["status"] == "running"

            await asyncio.sleep(0.1)
            val_resumed = app.device_manager.read_word("D", 600)
            assert val_resumed > val_paused

            # Stop script
            await client.post(f"/api/scripts/{script_name}/stop")
    finally:
        await app.stop()
        cleanup_script(script_name)


@pytest.mark.asyncio
async def test_repeated_start_stop_cycles_cleanly():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    script_name = "test_cycle.yaml"
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            script_content = "- type: periodic\n  interval_ms: 25\n  actions:\n    - target: D700\n      expr: 'D700 + 1'\n"
            await client.put(f"/api/scripts/{script_name}", json={"content": script_content})

            for _ in range(5):
                await client.post(f"/api/scripts/{script_name}/start")
                await asyncio.sleep(0.05)
                await client.post(f"/api/scripts/{script_name}/stop")

            # At the end, script is stopped and no engine task remains active
            assert script_name not in app.state.script_engines
            status_resp = await client.get(f"/api/scripts/{script_name}/status")
            assert status_resp.json()["status"] == "stopped"
    finally:
        await app.stop()
        cleanup_script(script_name)


@pytest.mark.asyncio
async def test_app_shutdown_cleans_up_all_running_scripts():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    s1 = "s1.yaml"
    s2 = "s2.yaml"
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            c = "- type: periodic\n  interval_ms: 20\n  actions:\n    - target: D800\n      expr: 'D800 + 1'\n"
            await client.put(f"/api/scripts/{s1}", json={"content": c})
            await client.put(f"/api/scripts/{s2}", json={"content": c})

            await client.post(f"/api/scripts/{s1}/start")
            await client.post(f"/api/scripts/{s2}/start")
            assert len(app.state.script_engines) == 2

        # App stop should stop all engines
        await app.stop()
        assert len(app.state.script_engines) == 0
    finally:
        cleanup_script(s1)
        cleanup_script(s2)
