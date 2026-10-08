import asyncio
import struct
import time
import pytest
from src.server.tcp_server import TcpServer
from src.device.device_manager import DeviceManager
from src.server.latency import LatencyEmulator
from src.protocol.constants import DeviceCode3E


@pytest.fixture
def server():
    srv = TcpServer(port=0)
    return srv


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
async def test_server_start_stop(server):
    await server.start()
    assert server._server is not None
    await server.stop()
    assert server._server is None


@pytest.mark.asyncio
async def test_server_accepts_connection(server):
    await server.start()
    port = server.port
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    assert reader is not None
    assert writer is not None
    writer.close()
    await writer.wait_closed()
    await server.stop()


@pytest.mark.asyncio
async def test_tcp_3e_read_write_same_connection():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm)
    await server.start()
    port = server.port

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        # Write D100 = 1234, D101 = 5678
        write_req = make_3e_write_req(DeviceCode3E.D, 100, [1234, 5678])
        writer.write(write_req)
        await writer.drain()

        # Read write response: subheader(2) + access_path(4) + data_len(2) + end_code(2) = 10 bytes
        resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
        assert len(resp) >= 10
        assert resp[:2] == b"\xD0\x00"
        end_code = struct.unpack_from("<H", resp, 8)[0]
        assert end_code == 0

        # Read back D100 (2 points)
        read_req = make_3e_read_req(DeviceCode3E.D, 100, 2)
        writer.write(read_req)
        await writer.drain()

        read_resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
        assert len(read_resp) >= 14
        assert read_resp[:2] == b"\xD0\x00"
        read_end_code = struct.unpack_from("<H", read_resp, 8)[0]
        assert read_end_code == 0
        val0, val1 = struct.unpack_from("<HH", read_resp, 10)
        assert val0 == 1234
        assert val1 == 5678
    finally:
        writer.close()
        await writer.wait_closed()
        await server.stop()


@pytest.mark.asyncio
async def test_tcp_3e_fragmented_and_concatenated():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm)
    await server.start()
    port = server.port

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        # 1. Fragmented write: send in two chunks
        write_req = make_3e_write_req(DeviceCode3E.D, 200, [999])
        mid = len(write_req) // 2
        writer.write(write_req[:mid])
        await writer.drain()
        await asyncio.sleep(0.05)
        writer.write(write_req[mid:])
        await writer.drain()

        resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
        assert resp[:2] == b"\xD0\x00"

        # 2. Concatenated requests: send 2 read requests in single packet
        read_req1 = make_3e_read_req(DeviceCode3E.D, 200, 1)
        read_req2 = make_3e_read_req(DeviceCode3E.D, 200, 1)
        writer.write(read_req1 + read_req2)
        await writer.drain()

        # Both responses should arrive
        resps = bytearray()
        while len(resps) < 24:  # 12 bytes per response
            chunk = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            resps.extend(chunk)

        assert resps[:2] == b"\xD0\x00"
        val1 = struct.unpack_from("<H", resps, 10)[0]
        assert val1 == 999

        assert resps[12:14] == b"\xD0\x00"
        val2 = struct.unpack_from("<H", resps, 22)[0]
        assert val2 == 999
    finally:
        writer.close()
        await writer.wait_closed()
        await server.stop()


@pytest.mark.asyncio
async def test_tcp_3e_reconnect():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm)
    await server.start()
    port = server.port

    # First client writes
    r1, w1 = await asyncio.open_connection("127.0.0.1", port)
    w1.write(make_3e_write_req(DeviceCode3E.D, 300, [777]))
    await w1.drain()
    await r1.read(1024)
    w1.close()
    await w1.wait_closed()

    # Second client reconnects and reads
    r2, w2 = await asyncio.open_connection("127.0.0.1", port)
    try:
        w2.write(make_3e_read_req(DeviceCode3E.D, 300, 1))
        await w2.drain()
        resp = await asyncio.wait_for(r2.read(1024), timeout=2.0)
        val = struct.unpack_from("<H", resp, 10)[0]
        assert val == 777
    finally:
        w2.close()
        await w2.wait_closed()
        await server.stop()


@pytest.mark.asyncio
async def test_tcp_3e_latency_fixed_and_timeout():
    dm = DeviceManager()
    latency = LatencyEmulator()
    server = TcpServer(port=0, device_manager=dm, latency_emulator=latency)
    await server.start()
    port = server.port

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        # Fixed latency: 100ms
        latency.mode = "fixed"
        latency.params = {"delay_ms": 100}

        t0 = time.monotonic()
        writer.write(make_3e_read_req(DeviceCode3E.D, 0, 1))
        await writer.drain()
        resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.08  # ~100ms
        assert resp[:2] == b"\xD0\x00"

        # Timeout simulation: 100% timeout rate -> should not receive response
        latency.mode = "timeout"
        latency.params = {"timeout_rate": 1.0}

        writer.write(make_3e_read_req(DeviceCode3E.D, 0, 1))
        await writer.drain()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(reader.read(1024), timeout=0.2)
    finally:
        writer.close()
        await writer.wait_closed()
        await server.stop()

