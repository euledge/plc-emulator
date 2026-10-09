import asyncio
import struct
import time
import pytest
import httpx
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.protocol.constants import DeviceCode3E


def make_3e_req(dev_code: int = 0xA8, addr: int = 100, count: int = 1) -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    cmd_data = struct.pack("<HH", 0x0401, 0x0000) + dev_bytes + struct.pack("<H", count)
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


@pytest.mark.asyncio
async def test_stats_initial_and_reset():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # 1. Initial state (0 requests)
            r0 = await client.get("/api/latency/stats")
            assert r0.status_code == 200
            s0 = r0.json()
            assert s0 == {"count": 0, "min": 0, "max": 0, "avg": 0}

            # 2. Perform a socket request
            reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
            try:
                writer.write(make_3e_req())
                await writer.drain()
                await reader.read(1024)
            finally:
                writer.close()
                await writer.wait_closed()

            # 3. Stats has 1 request
            r1 = await client.get("/api/latency/stats")
            s1 = r1.json()
            assert s1["count"] == 1

            # 4. Reset stats
            r_reset = await client.post("/api/latency/stats/reset")
            assert r_reset.status_code == 200

            # 5. Stats back to 0
            r2 = await client.get("/api/latency/stats")
            s2 = r2.json()
            assert s2 == {"count": 0, "min": 0, "max": 0, "avg": 0}
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_stats_fixed_and_none_latency():
    cfg = ConfigManager(port=0, transport="tcp", latency_mode="fixed", latency_params={"delay_ms": 20})
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            for _ in range(3):
                writer.write(make_3e_req())
                await writer.drain()
                await reader.read(1024)
        finally:
            writer.close()
            await writer.wait_closed()

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            r = await client.get("/api/latency/stats")
            s = r.json()
            assert s["count"] == 3
            assert s["min"] >= 20
            assert s["max"] >= 20
            assert s["avg"] >= 20
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_stats_timeout_only_does_not_break():
    cfg = ConfigManager(port=0, transport="tcp", latency_mode="timeout", latency_params={"timeout_rate": 1.0})
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            for _ in range(3):
                writer.write(make_3e_req())
                await writer.drain()
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(reader.read(1024), timeout=0.1)
        finally:
            writer.close()
            await writer.wait_closed()

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            r = await client.get("/api/latency/stats")
            s = r.json()
            assert s["count"] == 3
            assert s["min"] == 0
            assert s["max"] == 0
            assert s["avg"] == 0
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_web_ui_requests_are_never_delayed():
    # Set high latency (500ms) on PLC communication
    cfg = ConfigManager(port=0, transport="tcp", latency_mode="fixed", latency_params={"delay_ms": 500})
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            t0 = time.monotonic()
            resp = await client.get("/api/config")
            dur = time.monotonic() - t0
            assert resp.status_code == 200
            # Web UI REST request must be fast (< 100ms), NOT delayed by 500ms
            assert dur < 0.1
    finally:
        await app.stop()
