import asyncio
import struct
import time
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


def make_3e_cpu_type_req() -> bytes:
    cmd_data = struct.pack("<HH", 0x0101, 0x0000)
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


@pytest.mark.asyncio
async def test_dynamic_plc_model_switching():
    cfg = ConfigManager()
    cfg.port = 0
    cfg.transport = "tcp"
    cfg.plc_model = "Q03UDE"

    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start_plc_server()
    port = app.server.port

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.web_app), base_url="http://test"
    ) as client:
        # 1. Connect and verify Q03UDE CPU type
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            writer.write(make_3e_cpu_type_req())
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            cpu_name = resp[10:].decode("ascii")
            assert "Q03UDE" in cpu_name

            # D20000 is out of range for Q03UDE (max 12287) -> should return error
            writer.write(make_3e_write_req(DeviceCode3E.D, 20000, [1]))
            await writer.drain()
            err_resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            end_code = struct.unpack_from("<H", err_resp, 8)[0]
            assert end_code != 0, "D20000 must fail on Q03UDE"
        finally:
            writer.close()
            await writer.wait_closed()

        # 2. Switch to R04CPU via Web API
        resp = await client.put("/api/config", json={"plc_model": "R04CPU"})
        assert resp.status_code == 200
        assert resp.json()["plc_model"] == "R04CPU"

        # 3. Connect and verify R04CPU CPU type and range (D20000 is allowed on R04CPU up to 65535)
        r2, w2 = await asyncio.open_connection("127.0.0.1", port)
        try:
            w2.write(make_3e_cpu_type_req())
            await w2.drain()
            resp2 = await asyncio.wait_for(r2.read(1024), timeout=2.0)
            cpu_name2 = resp2[10:].decode("ascii")
            assert "R04CPU" in cpu_name2

            # D20000 is allowed on R04CPU
            w2.write(make_3e_write_req(DeviceCode3E.D, 20000, [777]))
            await w2.drain()
            ok_resp = await asyncio.wait_for(r2.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", ok_resp, 8)[0] == 0

            # Read back
            w2.write(make_3e_read_req(DeviceCode3E.D, 20000, 1))
            await w2.drain()
            read_resp = await asyncio.wait_for(r2.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", read_resp, 8)[0] == 0
            assert struct.unpack_from("<H", read_resp, 10)[0] == 777
        finally:
            w2.close()
            await w2.wait_closed()

    await app.stop_plc_server()


@pytest.mark.asyncio
async def test_dynamic_server_transport_and_port_switch():
    cfg = ConfigManager()
    cfg.port = 0
    cfg.transport = "tcp"

    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start_plc_server()
    initial_tcp_port = app.server.port

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.web_app), base_url="http://test"
    ) as client:
        # Switch to UDP on dynamic port (0)
        resp = await client.put("/api/config", json={"transport": "udp", "port": 0})
        assert resp.status_code == 200
        assert resp.json()["transport"] == "udp"

        new_udp_port = app.server.port

        # Connect via UDP to verify new server works
        loop = asyncio.get_running_loop()

        class UdpClient(asyncio.DatagramProtocol):
            def __init__(self):
                self.queue = asyncio.Queue()

            def datagram_received(self, data, addr):
                self.queue.put_nowait(data)

        transport, client_proto = await loop.create_datagram_endpoint(
            UdpClient, remote_addr=("127.0.0.1", new_udp_port)
        )
        try:
            transport.sendto(make_3e_write_req(DeviceCode3E.D, 15, [123]))
            udp_resp = await asyncio.wait_for(client_proto.queue.get(), timeout=2.0)
            assert udp_resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", udp_resp, 8)[0] == 0
        finally:
            transport.close()

    await app.stop_plc_server()


@pytest.mark.asyncio
async def test_invalid_config_returns_error_and_preserves_state():
    cfg = ConfigManager()
    cfg.port = 0
    cfg.transport = "tcp"
    cfg.plc_model = "Q03UDE"

    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start_plc_server()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.web_app), base_url="http://test"
    ) as client:
        # Invalid PLC model
        resp = await client.put("/api/config", json={"plc_model": "INVALID_PLC"})
        assert resp.status_code == 400
        assert app.config.plc_model == "Q03UDE"

        # Invalid port
        resp = await client.put("/api/config", json={"port": 99999})
        assert resp.status_code == 400

        # Invalid transport
        resp = await client.put("/api/config", json={"transport": "bluetooth"})
        assert resp.status_code == 400

    await app.stop_plc_server()


@pytest.mark.asyncio
async def test_dynamic_latency_config():
    cfg = ConfigManager()
    cfg.port = 0
    cfg.transport = "tcp"

    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start_plc_server()
    port = app.server.port

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.web_app), base_url="http://test"
    ) as client:
        # Set fixed latency 100ms via PUT /api/config
        resp = await client.put(
            "/api/config",
            json={"latency_mode": "fixed", "latency_params": {"delay_ms": 100}},
        )
        assert resp.status_code == 200
        assert app.latency.mode == "fixed"

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            t0 = time.monotonic()
            writer.write(make_3e_read_req(DeviceCode3E.D, 0, 1))
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            elapsed = time.monotonic() - t0
            assert elapsed >= 0.08
            assert resp[:2] == b"\xD0\x00"
        finally:
            writer.close()
            await writer.wait_closed()

    await app.stop_plc_server()
