import asyncio
import json
import struct
import pytest
import httpx
import websockets
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.protocol.constants import DeviceCode3E


def make_3e_read_req(command: int, subcommand: int, dev_code: int, addr: int, count: int) -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    cmd_data = struct.pack("<HH", command, subcommand) + dev_bytes + struct.pack("<H", count)
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


@pytest.mark.asyncio
async def test_clear_all_devices_resets_memory_to_zero():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    # Pre-populate devices
    app.device_manager.write_word("D", 10, 111)
    app.device_manager.write_word("D", 20, 222)
    app.device_manager.write_bit("M", 0, True)
    app.device_manager.write_word("W", 5, 333)

    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # 1. Call POST /api/devices/clear
            resp = await client.post("/api/devices/clear")
            assert resp.status_code == 200
            assert resp.json()["cleared"] is True

            # 2. Check via REST API: values are 0
            d_resp = await client.get("/api/devices/D?start=10&count=2")
            assert d_resp.json()["values"] == [0, 0]
            w_resp = await client.get("/api/devices/W?start=5&count=1")
            assert w_resp.json()["values"] == [0]

            # 3. Check JSON save: state is empty
            save_resp = await client.post("/api/save", json={"name": "test_clear_state.json"})
            assert save_resp.status_code == 200

        # 4. Read over live PLC socket: returns 0
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            req = make_3e_read_req(0x0401, 0x0000, DeviceCode3E.D, 10, 1)
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert struct.unpack_from("<H", resp, 10)[0] == 0
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_clear_with_preserve_latch():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    app.device_manager.write_word("D", 10, 555)
    app.device_manager.write_bit("L", 5, True)

    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            resp = await client.post("/api/devices/clear", json={"preserve_latch": True})
            assert resp.status_code == 200

            assert app.device_manager.read_word("D", 10) == 0
            assert app.device_manager.read_bit("L", 5) is True
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_clear_specific_device_type():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    app.device_manager.write_word("D", 10, 123)
    app.device_manager.write_word("W", 10, 456)

    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # Clear only D
            resp = await client.post("/api/devices/clear", json={"device_type": "D"})
            assert resp.status_code == 200

            assert app.device_manager.read_word("D", 10) == 0
            assert app.device_manager.read_word("W", 10) == 456  # Untouched
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_invalid_device_type_does_not_destroy_memory():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    app.device_manager.write_word("D", 10, 789)

    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # Invalid device type returns HTTP 400
            resp = await client.post("/api/devices/clear", json={"device_type": "UNKNOWN_DEVICE"})
            assert resp.status_code == 400

            # D10 is untouched
            assert app.device_manager.read_word("D", 10) == 789
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_clear_broadcasts_update_to_websockets():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    app.device_manager.write_word("D", 100, 42)

    await app.start()
    try:
        web_port = app.actual_web_port
        uri = f"ws://127.0.0.1:{web_port}/ws"
        async with websockets.connect(uri) as ws:
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
                await client.post("/api/devices/clear")

            # Collect websocket messages until D100=0 arrives
            found_clear = False
            for _ in range(10):
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(msg_raw)
                if msg.get("type") == "device_update" and msg.get("device") == "D" and msg.get("address") == 100:
                    assert msg["value"] == 0
                    found_clear = True
                    break
            assert found_clear
    finally:
        await app.stop()
