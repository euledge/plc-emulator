import asyncio
import socket
import struct
import time
import pytest
from src.server.udp_server import UdpServer
from src.device.device_manager import DeviceManager
from src.server.latency import LatencyEmulator
from src.protocol.constants import DeviceCode3E


@pytest.fixture
def server():
    srv = UdpServer(port=0)
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


class UdpClientProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data, addr):
        self.queue.put_nowait(data)


@pytest.mark.asyncio
async def test_server_start_stop(server):
    await server.start()
    assert server._transport is not None
    await server.stop()
    assert server._transport is None


@pytest.mark.asyncio
async def test_server_receives_datagram(server):
    await server.start()
    port = server.port
    transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: asyncio.DatagramProtocol(),
        remote_addr=("127.0.0.1", port),
    )
    transport.sendto(b"test data")
    transport.close()
    await server.stop()


@pytest.mark.asyncio
async def test_udp_3e_read_write():
    dm = DeviceManager()
    server = UdpServer(port=0, device_manager=dm)
    await server.start()
    port = server.port

    loop = asyncio.get_running_loop()
    transport, client = await loop.create_datagram_endpoint(
        UdpClientProtocol,
        remote_addr=("127.0.0.1", port),
    )
    try:
        # Write D50 = 4321
        write_req = make_3e_write_req(DeviceCode3E.D, 50, [4321])
        transport.sendto(write_req)

        resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        assert len(resp) >= 10
        assert resp[:2] == b"\xD0\x00"
        end_code = struct.unpack_from("<H", resp, 8)[0]
        assert end_code == 0

        # Read back D50
        read_req = make_3e_read_req(DeviceCode3E.D, 50, 1)
        transport.sendto(read_req)

        read_resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        assert len(read_resp) >= 12
        assert read_resp[:2] == b"\xD0\x00"
        val = struct.unpack_from("<H", read_resp, 10)[0]
        assert val == 4321
        assert dm.read_word("D", 50) == 4321
    finally:
        transport.close()
        await server.stop()


@pytest.mark.asyncio
async def test_udp_invalid_request_does_not_break_subsequent_request():
    dm = DeviceManager()
    server = UdpServer(port=0, device_manager=dm)
    await server.start()
    port = server.port

    loop = asyncio.get_running_loop()
    transport, client = await loop.create_datagram_endpoint(
        UdpClientProtocol,
        remote_addr=("127.0.0.1", port),
    )
    try:
        # Send garbage packet
        transport.sendto(b"GARBAGE_PACKET_NOT_MC")
        # May receive error response
        try:
            err_resp = await asyncio.wait_for(client.queue.get(), timeout=0.2)
            assert err_resp[:2] == b"\xD0\x00"
            end_code = struct.unpack_from("<H", err_resp, 8)[0]
            assert end_code != 0  # error code
        except asyncio.TimeoutError:
            pass

        # Send valid write request
        transport.sendto(make_3e_write_req(DeviceCode3E.D, 10, [888]))
        resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        assert resp[:2] == b"\xD0\x00"
        assert struct.unpack_from("<H", resp, 8)[0] == 0
        assert dm.read_word("D", 10) == 888
    finally:
        transport.close()
        await server.stop()


@pytest.mark.asyncio
async def test_udp_3e_latency_fixed_and_timeout():
    dm = DeviceManager()
    latency = LatencyEmulator()
    server = UdpServer(port=0, device_manager=dm, latency_emulator=latency)
    await server.start()
    port = server.port

    loop = asyncio.get_running_loop()
    transport, client = await loop.create_datagram_endpoint(
        UdpClientProtocol,
        remote_addr=("127.0.0.1", port),
    )
    try:
        # Fixed latency 100ms
        latency.mode = "fixed"
        latency.params = {"delay_ms": 100}

        t0 = time.monotonic()
        transport.sendto(make_3e_read_req(DeviceCode3E.D, 0, 1))
        resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.08
        assert resp[:2] == b"\xD0\x00"

        # Timeout 100%
        latency.mode = "timeout"
        latency.params = {"timeout_rate": 1.0}

        transport.sendto(make_3e_read_req(DeviceCode3E.D, 0, 1))
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.queue.get(), timeout=0.2)
    finally:
        transport.close()
        await server.stop()

