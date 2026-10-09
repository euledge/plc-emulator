import asyncio
import json
import struct
import pytest
import httpx
import websockets
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
async def test_devices_across_different_types_coexist_and_sync():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        uri = f"ws://127.0.0.1:{web_port}/ws"
        async with websockets.connect(uri) as ws:
            # 1. Subscribe to D100, M50, and X20 via monitor_add
            await ws.send(json.dumps({"type": "monitor_add", "device": "D", "address": 100}))
            await ws.send(json.dumps({"type": "monitor_add", "device": "M", "address": 50}))
            await ws.send(json.dumps({"type": "monitor_add", "device": "X", "address": 20}))

            # Drain initial replies
            for _ in range(3):
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(raw)
                assert msg["type"] == "device_update"

            # 2. Update D100 via PLC TCP write
            reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
            try:
                writer.write(make_3e_write_req(DeviceCode3E.D, 100, [5555]))
                await writer.drain()
                resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
                assert resp[:2] == b"\xD0\x00"
            finally:
                writer.close()
                await writer.wait_closed()

            # 3. Update M50 via REST API
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
                resp = await client.put("/api/devices/M/50", json={"value": 1})
                assert resp.status_code == 200

            # 4. Receive both updates over WebSocket without cross-talk
            updates = []
            for _ in range(20):
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    m = json.loads(raw)
                    if m.get("type") == "device_update":
                        updates.append(m)
                        if len(updates) == 2:
                            break
                except asyncio.TimeoutError:
                    break

            assert any(u["device"] == "D" and u["address"] == 100 and u["value"] == 5555 for u in updates)
            assert any(u["device"] == "M" and u["address"] == 50 and u["value"] == 1 for u in updates)

            # Both devices have correct values in memory
            assert app.device_manager.read_word("D", 100) == 5555
            assert app.device_manager.read_bit("M", 50) is True
    finally:
        await app.stop()
