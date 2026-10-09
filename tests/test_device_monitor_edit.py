import asyncio
import struct
import pytest
import httpx
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
async def test_edit_word_device_reflects_in_rest_and_plc_socket():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        # 1. Edit via REST PUT
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            resp = await client.put("/api/devices/D/100", json={"value": 4321})
            assert resp.status_code == 200

            # 2. REST GET reflects the new value
            get_resp = await client.get("/api/devices/D?start=100&count=1")
            assert get_resp.status_code == 200
            assert get_resp.json()["values"] == [4321]

        # 3. Live PLC TCP client reads the exact same value
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            req = make_3e_read_req(0x0401, 0x0000, DeviceCode3E.D, 100, 1)
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert struct.unpack_from("<H", resp, 10)[0] == 4321
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_edit_bit_device_reflects_in_rest_and_plc_socket():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        # 1. Edit bit device via REST PUT
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            resp = await client.put("/api/devices/M/50", json={"value": 1})
            assert resp.status_code == 200

            get_resp = await client.get("/api/devices/M?start=50&count=1")
            assert get_resp.status_code == 200
            assert get_resp.json()["values"] == [1]

        # 2. Live PLC client reads bit M50 with subcommand 0x0001 (bit units)
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            req = make_3e_read_req(0x0401, 0x0001, DeviceCode3E.M, 50, 1)
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            # 1 bit in high nibble of byte 10
            assert resp[10] == 0x10
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_out_of_range_and_invalid_value_rejected_without_destroying_existing():
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    # Pre-populate D100 = 1234
    app.device_manager.write_word("D", 100, 1234)
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # Negative word value
            r1 = await client.put("/api/devices/D/100", json={"value": -1})
            assert r1.status_code == 400

            # Value > 65535 for word
            r2 = await client.put("/api/devices/D/100", json={"value": 65536})
            assert r2.status_code == 400

            # Out of range address on Q03UDE (D max is 12287)
            r3 = await client.put("/api/devices/D/99999", json={"value": 55})
            assert r3.status_code == 400

            # Unknown device type
            r4 = await client.put("/api/devices/UNKNOWN/100", json={"value": 55})
            assert r4.status_code == 400

            # Verify existing value was not corrupted or modified
            assert app.device_manager.read_word("D", 100) == 1234
            get_resp = await client.get("/api/devices/D?start=100&count=1")
            assert get_resp.json()["values"] == [1234]
    finally:
        await app.stop()
