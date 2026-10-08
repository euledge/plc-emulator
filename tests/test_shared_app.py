import asyncio
import struct
import httpx
import pytest
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


def make_3e_read_req(dev_code: int, addr: int, count: int) -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    cmd_data = struct.pack("<HH", 0x0401, 0x0000) + dev_bytes + struct.pack("<H", count)
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


@pytest.mark.asyncio
async def test_shared_state_between_plc_and_rest():
    cfg = ConfigManager()
    cfg.port = 0  # Dynamic port for PLC
    cfg.transport = "tcp"

    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    # Start only PLC server and use TestClient / ASGI transport for Web, or start both
    await app.start_plc_server()
    plc_port = app.server.port

    # Use httpx.AsyncClient with ASGITransport to talk directly to web_app without binding another socket
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.web_app), base_url="http://test"
    ) as client:
        # 1. Write via REST API: D100 = 5555
        put_resp = await client.put("/api/devices/D/100", json={"value": 5555})
        assert put_resp.status_code == 200

        # 2. Read back via TCP MC 3E binary protocol
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            writer.write(make_3e_read_req(DeviceCode3E.D, 100, 1))
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:2] == b"\xD0\x00"
            val = struct.unpack_from("<H", resp, 10)[0]
            assert val == 5555, "TCP read must match value written by REST"

            # 3. Write via TCP MC 3E binary protocol: D200 = 9999
            writer.write(make_3e_write_req(DeviceCode3E.D, 200, [9999]))
            await writer.drain()
            write_resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert write_resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", write_resp, 8)[0] == 0
        finally:
            writer.close()
            await writer.wait_closed()

        # 4. Read back via REST API
        get_resp = await client.get("/api/devices/D?start=200&count=1")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["values"] == [9999], "REST read must match value written by TCP"

        # 5. Client disconnect & reconnect still shares memory
        r2, w2 = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            w2.write(make_3e_read_req(DeviceCode3E.D, 200, 1))
            await w2.drain()
            resp2 = await asyncio.wait_for(r2.read(1024), timeout=2.0)
            val2 = struct.unpack_from("<H", resp2, 10)[0]
            assert val2 == 9999, "Reconnected client must read same shared memory"
        finally:
            w2.close()
            await w2.wait_closed()

    await app.stop_plc_server()
    assert app.server is None


@pytest.mark.asyncio
async def test_full_app_start_stop():
    cfg = ConfigManager()
    cfg.port = 0
    # Use random free port for web
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    assert app.server is not None
    assert app._uvicorn_server is not None
    await app.stop()
    assert app.server is None
    assert app._uvicorn_server is None
