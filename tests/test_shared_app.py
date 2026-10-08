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
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    assert app.server is not None
    assert app._uvicorn_server is not None
    assert app.actual_plc_port > 0
    assert app.actual_web_port > 0
    await app.stop()
    assert app.server is None
    assert app._uvicorn_server is None


async def send_udp_request(host: str, port: int, data: bytes) -> bytes:
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    class ClientProtocol(asyncio.DatagramProtocol):
        def __init__(self) -> None:
            self.transport: asyncio.DatagramTransport | None = None

        def connection_made(self, transport: asyncio.DatagramTransport) -> None:
            self.transport = transport
            self.transport.sendto(data)

        def datagram_received(self, resp_data: bytes, addr: tuple[str, int]) -> None:
            if not future.done():
                future.set_result(resp_data)
            if self.transport:
                self.transport.close()

        def error_received(self, exc: Exception) -> None:
            if not future.done():
                future.set_exception(exc)

    transport, _ = await loop.create_datagram_endpoint(
        ClientProtocol,
        remote_addr=(host, port),
    )
    try:
        return await asyncio.wait_for(future, timeout=2.0)
    finally:
        transport.close()


@pytest.mark.asyncio
async def test_shared_state_between_udp_and_rest():
    cfg = ConfigManager()
    cfg.port = 0
    cfg.transport = "udp"

    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start_plc_server()
    plc_port = app.actual_plc_port

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.web_app), base_url="http://test"
    ) as client:
        # 1. Write via REST API: D300 = 1234
        put_resp = await client.put("/api/devices/D/300", json={"value": 1234})
        assert put_resp.status_code == 200

        # 2. Read back via UDP MC 3E binary protocol
        resp = await send_udp_request(
            "127.0.0.1", plc_port, make_3e_read_req(DeviceCode3E.D, 300, 1)
        )
        assert resp[:2] == b"\xD0\x00"
        val = struct.unpack_from("<H", resp, 10)[0]
        assert val == 1234, "UDP read must match value written by REST"

        # 3. Write via UDP MC 3E binary protocol: D400 = 5678
        write_resp = await send_udp_request(
            "127.0.0.1", plc_port, make_3e_write_req(DeviceCode3E.D, 400, [5678])
        )
        assert write_resp[:2] == b"\xD0\x00"
        assert struct.unpack_from("<H", write_resp, 8)[0] == 0

        # 4. Read back via REST API
        get_resp = await client.get("/api/devices/D?start=400&count=1")
        assert get_resp.status_code == 200
        assert get_resp.json()["values"] == [5678], "REST read must match value written by UDP"

    await app.stop_plc_server()
    assert app.server is None


@pytest.mark.asyncio
async def test_concurrent_real_sockets_plc_and_web():
    """Verify that both PLC and Web servers are accessible via real OS network sockets simultaneously."""
    cfg = ConfigManager()
    cfg.port = 0
    cfg.transport = "tcp"

    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()

    web_port = app.actual_web_port
    plc_port = app.actual_plc_port
    assert web_port > 0
    assert plc_port > 0

    try:
        # Communicate with Web server over real HTTP socket
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            resp = await client.get("/api/config")
            assert resp.status_code == 200
            assert resp.json()["transport"] == "tcp"

            put_resp = await client.put("/api/devices/D/500", json={"value": 7777})
            assert put_resp.status_code == 200

        # Concurrently communicate with PLC server over real TCP socket
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            writer.write(make_3e_read_req(DeviceCode3E.D, 500, 1))
            await writer.drain()
            tcp_resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert tcp_resp[:2] == b"\xD0\x00"
            val = struct.unpack_from("<H", tcp_resp, 10)[0]
            assert val == 7777, "Real TCP read must match value written by real Web HTTP"
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()

    assert app.server is None
    assert app._uvicorn_server is None


@pytest.mark.asyncio
async def test_start_rollback_on_web_failure(monkeypatch):
    """Verify that PLC server is cleaned up and stopped if web server fails during startup."""
    cfg = ConfigManager()
    cfg.port = 0
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")

    async def mock_start_web_failure():
        raise RuntimeError("Simulated web startup failure")

    monkeypatch.setattr(app, "start_web_server", mock_start_web_failure)

    with pytest.raises(RuntimeError, match="Simulated web startup failure"):
        await app.start()

    # PLC server must be safely cleaned up
    assert app.server is None


def test_default_web_binding_is_localhost():
    """Verify default web host binding is 127.0.0.1 for security."""
    app = PLCEmulatorApp()
    assert app.web_host == "127.0.0.1"


@pytest.mark.asyncio
async def test_web_port_conflict_clean_rollback_without_system_exit():
    """Verify that a port conflict raises OSError directly without SystemExit, and rolls back PLC server."""
    import socket

    # Occupy a port
    dummy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dummy.bind(("127.0.0.1", 0))
    occupied_port = dummy.getsockname()[1]

    cfg = ConfigManager()
    cfg.port = 0
    app = PLCEmulatorApp(config=cfg, web_port=occupied_port, web_host="127.0.0.1")

    try:
        with pytest.raises(OSError):
            await app.start()
        # PLC server must have been cleaned up and rolled back
        assert app.server is None
    finally:
        dummy.close()


@pytest.mark.asyncio
async def test_unexpected_web_exit_stops_plc_server():
    """Verify that an unexpected termination of the Web server triggers stopping the PLC listener."""
    cfg = ConfigManager()
    cfg.port = 0
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()

    assert app.server is not None
    plc_port = app.actual_plc_port

    # Verify PLC port is responding
    reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
    writer.close()
    await writer.wait_closed()

    # Trigger unexpected exit of Web server
    assert app._uvicorn_server is not None
    app._uvicorn_server.should_exit = True

    # Wait for lifecycle monitor to detect exit and shut down
    await asyncio.wait_for(app.wait_until_stopped(), timeout=3.0)

    assert app.server is None, "wait_until_stopped must wait for PLC cleanup"
    with pytest.raises(OSError):
        await asyncio.open_connection("127.0.0.1", plc_port)
    await app.stop()


