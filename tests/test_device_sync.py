import asyncio
import struct
import pytest
import httpx
import websockets
import json
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.protocol.constants import DeviceCode3E


def make_3e_write_req(dev_code: int, addr: int, values: list[int]) -> bytes:
    count = len(values)
    val_bytes = b"".join(struct.pack("<H", v) for v in values)
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    cmd_data = struct.pack("<HH", 0x1401, 0x0000) + dev_bytes + struct.pack("<H", count) + val_bytes
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


@pytest.mark.asyncio
async def test_plc_tcp_write_broadcasts_to_websocket():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        # Connect WebSocket client
        uri = f"ws://127.0.0.1:{web_port}/ws"
        async with websockets.connect(uri) as ws:
            # Connect PLC TCP client and write D100 = 7890
            reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
            try:
                writer.write(make_3e_write_req(DeviceCode3E.D, 100, [7890]))
                await writer.drain()
                resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
                assert resp[:2] == b"\xD0\x00"
            finally:
                writer.close()
                await writer.wait_closed()

            # Verify WebSocket received the update
            while True:
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(msg_raw)
                if msg.get("type") == "device_update":
                    break
            assert msg["device"] == "D"
            assert msg["address"] == 100
            assert msg["value"] == 7890
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_web_api_write_broadcasts_to_websocket():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port

        uri = f"ws://127.0.0.1:{web_port}/ws"
        async with websockets.connect(uri) as ws:
            # Write via REST API
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
                resp = await client.put("/api/devices/D/200", json={"value": 5432})
                assert resp.status_code == 200

            # Verify WebSocket received the update
            msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            msg = json.loads(msg_raw)
            assert msg["type"] == "device_update"
            assert msg["device"] == "D"
            assert msg["address"] == 200
            assert msg["value"] == 5432
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_disconnected_websocket_does_not_break_subsequent_broadcasts():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        uri = f"ws://127.0.0.1:{web_port}/ws"
        # Connect ws1 and ws2
        ws1 = await websockets.connect(uri)
        ws2 = await websockets.connect(uri)

        # Abruptly close ws1
        await ws1.close()

        # Write to PLC
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            writer.write(make_3e_write_req(DeviceCode3E.D, 300, [9999]))
            await writer.drain()
            await asyncio.wait_for(reader.read(1024), timeout=2.0)
        finally:
            writer.close()
            await writer.wait_closed()

        # ws2 must still receive the update without any hang or failure
        while True:
            msg_raw = await asyncio.wait_for(ws2.recv(), timeout=2.0)
            msg = json.loads(msg_raw)
            if msg.get("type") == "device_update":
                break
        assert msg["device"] == "D"
        assert msg["address"] == 300
        assert msg["value"] == 9999

        await ws2.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_websocket_monitor_add_replies_current_value():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    # Pre-populate device D50 = 1234
    app.device_manager.write_word("D", 50, 1234)
    await app.start()
    try:
        web_port = app.actual_web_port
        uri = f"ws://127.0.0.1:{web_port}/ws"
        async with websockets.connect(uri) as ws:
            # Send monitor_add for D50
            await ws.send(json.dumps({"type": "monitor_add", "device": "D", "address": 50}))
            msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            msg = json.loads(msg_raw)
            assert msg["type"] == "device_update"
            assert msg["device"] == "D"
            assert msg["address"] == 50
            assert msg["value"] == 1234
    finally:
        await app.stop()
