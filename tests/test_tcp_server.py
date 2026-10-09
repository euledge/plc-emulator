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


@pytest.mark.asyncio
async def test_tcp_3e_short_write_does_not_change_device_values():
    server = TcpServer(port=0)
    await server.start()
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    try:
        request = bytearray(make_3e_write_req(DeviceCode3E.D, 100, [1234]))
        struct.pack_into("<H", request, 18, 2)  # Claim two values, carry only one.
        writer.write(request)
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(10), timeout=2)
        assert struct.unpack_from("<H", response, 8)[0] == 0xC061

        writer.write(make_3e_read_req(DeviceCode3E.D, 100, 2))
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(14), timeout=2)
        assert struct.unpack_from("<HH", response, 10) == (0, 0)
    finally:
        writer.close()
        await writer.wait_closed()
        await server.stop()


@pytest.mark.asyncio
async def test_tcp_3e_oversized_read_returns_error_and_keeps_connection():
    server = TcpServer(port=0)
    await server.start()
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    try:
        writer.write(make_3e_read_req(DeviceCode3E.D, 0, 32767))
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(10), timeout=2)
        assert struct.unpack_from("<H", response, 8)[0] == 0xC05B

        writer.write(make_3e_read_req(DeviceCode3E.D, 0, 1))
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(12), timeout=2)
        assert struct.unpack_from("<H", response, 8)[0] == 0
    finally:
        writer.close()
        await writer.wait_closed()
        await server.stop()


@pytest.mark.asyncio
async def test_tcp_second_connection_does_not_displace_active_client():
    server = TcpServer(port=0)
    await server.start()
    first_reader, first_writer = await asyncio.open_connection("127.0.0.1", server.port)
    second_reader, second_writer = await asyncio.open_connection("127.0.0.1", server.port)
    try:
        assert await asyncio.wait_for(second_reader.read(1), timeout=2) == b""
        first_writer.write(make_3e_read_req(DeviceCode3E.D, 0, 1))
        await first_writer.drain()
        response = await asyncio.wait_for(first_reader.readexactly(12), timeout=2)
        assert struct.unpack_from("<H", response, 8)[0] == 0
    finally:
        first_writer.close()
        second_writer.close()
        await first_writer.wait_closed()
        await second_writer.wait_closed()
        await server.stop()


@pytest.mark.asyncio
async def test_tcp_competing_connection_rejection_and_subsequent_reconnect():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm)
    await server.start()
    try:
        # 1. Client 1 connects and writes D0 = 100
        r1, w1 = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            w1.write(make_3e_write_req(DeviceCode3E.D, 0, [100]))
            await w1.drain()
            resp = await asyncio.wait_for(r1.readexactly(10), timeout=2)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert dm.read_word("D", 0) == 100

            # 2. Client 2 attempts to connect while Client 1 is active -> rejected
            r2, w2 = await asyncio.open_connection("127.0.0.1", server.port)
            try:
                # Reading from rejected client returns EOF
                assert await asyncio.wait_for(r2.read(10), timeout=2) == b""
            finally:
                w2.close()
                await w2.wait_closed()

            # 3. Client 1 continues communicating without disruption
            w1.write(make_3e_write_req(DeviceCode3E.D, 1, [200]))
            await w1.drain()
            resp = await asyncio.wait_for(r1.readexactly(10), timeout=2)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert dm.read_word("D", 1) == 200
        finally:
            # 4. Client 1 disconnects cleanly
            w1.close()
            await w1.wait_closed()

        # 5. Client 2 reconnects after Client 1 disconnected -> accepted!
        r2_reconnect, w2_reconnect = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            w2_reconnect.write(make_3e_write_req(DeviceCode3E.D, 2, [300]))
            await w2_reconnect.drain()
            resp = await asyncio.wait_for(r2_reconnect.readexactly(10), timeout=2)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert dm.read_word("D", 2) == 300

            # Read all 3 values (D0, D1, D2)
            w2_reconnect.write(make_3e_read_req(DeviceCode3E.D, 0, 3))
            await w2_reconnect.drain()
            resp = await asyncio.wait_for(r2_reconnect.readexactly(16), timeout=2)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            v0, v1, v2 = struct.unpack_from("<HHH", resp, 10)
            assert (v0, v1, v2) == (100, 200, 300)
        finally:
            w2_reconnect.close()
            await w2_reconnect.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_tcp_concurrent_connection_race_only_one_active():
    server = TcpServer(port=0)
    await server.start()
    try:
        # Launch 5 concurrent connection attempts
        pairs = await asyncio.gather(
            *[asyncio.open_connection("127.0.0.1", server.port) for _ in range(5)]
        )
        try:
            active = []
            rejected = []
            for r, w in pairs:
                # Check if connection was closed immediately
                try:
                    data = await asyncio.wait_for(r.read(1), timeout=0.2)
                    if data == b"":
                        rejected.append((r, w))
                    else:
                        active.append((r, w))
                except asyncio.TimeoutError:
                    active.append((r, w))

            # Exactly 1 connection must be active, 4 must be rejected
            assert len(active) == 1
            assert len(rejected) == 4

            # Active connection can communicate
            act_r, act_w = active[0]
            act_w.write(make_3e_read_req(DeviceCode3E.D, 0, 1))
            await act_w.drain()
            resp = await asyncio.wait_for(act_r.readexactly(12), timeout=2)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
        finally:
            for r, w in pairs:
                w.close()
            for r, w in pairs:
                await w.wait_closed()
    finally:
        await server.stop()

@pytest.mark.asyncio
async def test_tcp_3e_response_preserves_request_access_path():
    server = TcpServer(port=0)
    await server.start()
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    route = b"\x12\x34\x56\x78"
    try:
        write = bytearray(make_3e_write_req(DeviceCode3E.D, 100, [1234]))
        write[2:6] = route
        writer.write(write)
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(10), timeout=2)
        assert response[2:6] == route
        assert struct.unpack_from("<H", response, 8)[0] == 0

        read = bytearray(make_3e_read_req(DeviceCode3E.D, 100, 1))
        read[2:6] = route
        writer.write(read)
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(12), timeout=2)
        assert response[2:6] == route
        assert struct.unpack_from("<H", response, 10)[0] == 1234

        struct.pack_into("<H", read, 10, 0xFFFF)
        writer.write(read)
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(10), timeout=2)
        assert response[2:6] == route
        assert struct.unpack_from("<H", response, 8)[0] == 0xC059

        writer.write(b"\x50\x00" + route + b"\x02\x00\x00\x00")
        await writer.drain()
        response = await asyncio.wait_for(reader.readexactly(10), timeout=2)
        assert response[2:6] == route
        assert struct.unpack_from("<H", response, 8)[0] == 0xC050
    finally:
        writer.close()
        await writer.wait_closed()
        await server.stop()
