import asyncio
import socket
import struct
import pytest
import httpx
from src.device.device_manager import DeviceManager
from src.server.tcp_server import TcpServer
from src.server.udp_server import UdpServer
from src.protocol.mc_frame_1e import McFrame1E
from src.protocol.mc_frame_4e import McFrame4E
from src.protocol.slmp_handler import SlmpHandler
from src.protocol.device_parser import encode_device_slmp
from main import PLCEmulatorApp
from src.config import ConfigManager


# Helper request builders
def make_1e_read_req(dev_code: int = 0x44, addr: int = 100, count: int = 1) -> bytes:
    # cmd=1 (read), dev_code, addr (2 LE), count (2 LE)
    return struct.pack("<BBHH", 0x01, dev_code, addr, count)


def make_1e_write_req(dev_code: int = 0x44, addr: int = 100, values: list[int] = [1234]) -> bytes:
    # cmd=3 (write), dev_code, addr (2 LE), count (2 LE), values
    val_bytes = b"".join(struct.pack("<H", v) for v in values)
    return struct.pack("<BBHH", 0x03, dev_code, addr, len(values)) + val_bytes


def make_4e_read_req(dev_code: int = 0xA8, addr: int = 100, count: int = 1, serial: int = 1) -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    serial_bytes = struct.pack("<H", serial)
    cmd_data = struct.pack("<HH", 0x0401, 0x0000) + dev_bytes + struct.pack("<H", count) + serial_bytes
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x54\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_4e_write_req(dev_code: int = 0xA8, addr: int = 100, values: list[int] = [1234], serial: int = 1) -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    val_bytes = b"".join(struct.pack("<H", v) for v in values)
    serial_bytes = struct.pack("<H", serial)
    cmd_data = struct.pack("<HH", 0x1401, 0x0000) + dev_bytes + struct.pack("<H", len(values)) + val_bytes + serial_bytes
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x54\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_slmp_read_req(addr: int = 100, code: int = 0x00A8, count: int = 1) -> bytes:
    # 4-byte addr LE, 2-byte dev code LE
    dev_bytes = struct.pack("<IH", addr, code)
    cmd_data = struct.pack("<HH", 0x0401, 0x0002) + dev_bytes + struct.pack("<H", count)
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_slmp_write_req(addr: int = 100, code: int = 0x00A8, values: list[int] = [1234]) -> bytes:
    dev_bytes = struct.pack("<IH", addr, code)
    val_bytes = b"".join(struct.pack("<H", v) for v in values)
    cmd_data = struct.pack("<HH", 0x1401, 0x0002) + dev_bytes + struct.pack("<H", len(values)) + val_bytes
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


class UdpClientProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data, addr):
        self.queue.put_nowait(data)

# ---------------- 1E Tests ----------------
@pytest.mark.asyncio
async def test_1e_tcp_read_write():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm, protocol_handler=McFrame1E())
    await server.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            # Write D100 = 1234, D101 = 5678 (D code = 0x44 in 1E)
            writer.write(make_1e_write_req(0x44, 100, [1234, 5678]))
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2)
            assert resp[0] == 0x83  # 1E write success subheader
            assert dm.read_word("D", 100) == 1234
            assert dm.read_word("D", 101) == 5678

            # Read D100 (count=2)
            writer.write(make_1e_read_req(0x44, 100, 2))
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2)
            assert resp[0] == 0x81  # 1E read success subheader
            v0, v1 = struct.unpack_from("<HH", resp, 1)
            assert (v0, v1) == (1234, 5678)
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_1e_udp_read_write():
    dm = DeviceManager()
    server = UdpServer(port=0, device_manager=dm, protocol_handler=McFrame1E())
    await server.start()
    loop = asyncio.get_running_loop()
    transport, client = await loop.create_datagram_endpoint(
        UdpClientProtocol,
        remote_addr=("127.0.0.1", server.port),
    )
    try:
        # Write D200 = 4321
        transport.sendto(make_1e_write_req(0x44, 200, [4321]))
        resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        assert resp[0] == 0x83
        assert dm.read_word("D", 200) == 4321

        # Read D200
        transport.sendto(make_1e_read_req(0x44, 200, 1))
        resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        assert resp[0] == 0x81
        assert struct.unpack_from("<H", resp, 1)[0] == 4321
    finally:
        transport.close()
        await server.stop()


@pytest.mark.asyncio
async def test_1e_malformed_and_unknown_device_returns_error():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm, protocol_handler=McFrame1E())
    await server.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            # Unknown device code (0xFE)
            writer.write(make_1e_read_req(0xFE, 100, 1))
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2)
            assert resp[0] == 0x81
            err_code = struct.unpack_from("<H", resp, 1)[0]
            assert err_code != 0x0000  # Error response, not success
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


# ---------------- 4E Tests ----------------
@pytest.mark.asyncio
async def test_4e_tcp_read_write():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm, protocol_handler=McFrame4E())
    await server.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            # Write D100 = 7777 (4E serial = 42)
            writer.write(make_4e_write_req(0xA8, 100, [7777], serial=42))
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2)
            assert resp[:2] == b"\xD4\x00"  # 4E response subheader
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000  # Normal end code
            assert struct.unpack_from("<H", resp, len(resp) - 2)[0] == 42  # Serial number echoed
            assert dm.read_word("D", 100) == 7777

            # Read D100 (4E serial = 43)
            writer.write(make_4e_read_req(0xA8, 100, 1, serial=43))
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2)
            assert resp[:2] == b"\xD4\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert struct.unpack_from("<H", resp, 10)[0] == 7777
            assert struct.unpack_from("<H", resp, len(resp) - 2)[0] == 43
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_4e_udp_read_write():
    dm = DeviceManager()
    server = UdpServer(port=0, device_manager=dm, protocol_handler=McFrame4E())
    await server.start()
    loop = asyncio.get_running_loop()
    transport, client = await loop.create_datagram_endpoint(
        UdpClientProtocol,
        remote_addr=("127.0.0.1", server.port),
    )
    try:
        # Write D300 = 8888
        transport.sendto(make_4e_write_req(0xA8, 300, [8888], serial=99))
        resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        assert resp[:2] == b"\xD4\x00"
        assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
        assert dm.read_word("D", 300) == 8888

        # Read D300
        transport.sendto(make_4e_read_req(0xA8, 300, 1, serial=100))
        resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        assert resp[:2] == b"\xD4\x00"
        assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
        assert struct.unpack_from("<H", resp, 10)[0] == 8888
    finally:
        transport.close()
        await server.stop()

# ---------------- SLMP Tests ----------------
@pytest.mark.asyncio
async def test_slmp_tcp_read_write_extended_devices():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm, protocol_handler=SlmpHandler())
    await server.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            # Write D500 = 9999 (4-byte address 500, 2-byte code 0x00A8)
            writer.write(make_slmp_write_req(500, 0x00A8, [9999]))
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert dm.read_word("D", 500) == 9999

            # Read D500
            writer.write(make_slmp_read_req(500, 0x00A8, 1))
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert struct.unpack_from("<H", resp, 10)[0] == 9999
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_slmp_udp_read_write_extended_devices():
    dm = DeviceManager()
    server = UdpServer(port=0, device_manager=dm, protocol_handler=SlmpHandler())
    await server.start()
    loop = asyncio.get_running_loop()
    transport, client = await loop.create_datagram_endpoint(
        UdpClientProtocol,
        remote_addr=("127.0.0.1", server.port),
    )
    try:
        # Write D600 = 6543
        transport.sendto(make_slmp_write_req(600, 0x00A8, [6543]))
        resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        assert resp[:2] == b"\xD0\x00"
        assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
        assert dm.read_word("D", 600) == 6543

        # Read D600
        transport.sendto(make_slmp_read_req(600, 0x00A8, 1))
        resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
        assert resp[:2] == b"\xD0\x00"
        assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
        assert struct.unpack_from("<H", resp, 10)[0] == 6543
    finally:
        transport.close()
        await server.stop()


# ---------------- Regression & Malformed frame tests ----------------
@pytest.mark.asyncio
async def test_unsupported_frames_reject_not_silent_success():
    dm = DeviceManager()
    # 4E server rejects 3E frame
    server = TcpServer(port=0, device_manager=dm, protocol_handler=McFrame4E())
    await server.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            # Send standard 3E frame to 4E server -> should not be processed as success
            # 3E frame starts with 50 00
            req_3e = b"\x50\x00\x00\x00\x00\x00\x0a\x00\x00\x00\x01\x04\x00\x00\xA8\x64\x00\x00\x01\x00"
            writer.write(req_3e)
            await writer.drain()
            # 4E extractor drops 50 00, does not succeed
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1024), timeout=0.3)
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_udp_unrelated_garbage_ignored():
    dm = DeviceManager()
    server = UdpServer(port=0, device_manager=dm, protocol_handler=McFrame1E())
    await server.start()
    loop = asyncio.get_running_loop()
    transport, client = await loop.create_datagram_endpoint(
        UdpClientProtocol,
        remote_addr=("127.0.0.1", server.port),
    )
    try:
        # Send junk that doesn't start with 1 or 3
        transport.sendto(b"\x99\x88\x77\x66")
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.queue.get(), timeout=0.3)
    finally:
        transport.close()
        await server.stop()


# ---------------- Live Web API dynamic protocol switching ----------------
@pytest.mark.asyncio
async def test_dynamic_protocol_switching_via_web_api():
    cfg = ConfigManager(protocol="3E", transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start_plc_server()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app.web_app), base_url="http://test"
        ) as client:
            # Switch protocol to 1E
            resp = await client.put("/api/config", json={"protocol": "1E"})
            assert resp.status_code == 200
            assert resp.json()["protocol"] == "1E"

            # Verify 1E communication works on the live server
            reader, writer = await asyncio.open_connection("127.0.0.1", app.server.port)
            try:
                writer.write(make_1e_write_req(0x44, 50, [1111]))
                await writer.drain()
                resp_bytes = await asyncio.wait_for(reader.read(1024), timeout=2)
                assert resp_bytes[0] == 0x83
                assert app.device_manager.read_word("D", 50) == 1111
            finally:
                writer.close()
                await writer.wait_closed()

            # Switch protocol to 4E
            resp = await client.put("/api/config", json={"protocol": "4E"})
            assert resp.status_code == 200
            assert resp.json()["protocol"] == "4E"

            reader, writer = await asyncio.open_connection("127.0.0.1", app.server.port)
            try:
                writer.write(make_4e_write_req(0xA8, 60, [2222], serial=77))
                await writer.drain()
                resp_bytes = await asyncio.wait_for(reader.read(1024), timeout=2)
                assert resp_bytes[:2] == b"\xD4\x00"
                assert app.device_manager.read_word("D", 60) == 2222
            finally:
                writer.close()
                await writer.wait_closed()

            # Switch protocol to SLMP
            resp = await client.put("/api/config", json={"protocol": "SLMP"})
            assert resp.status_code == 200
            assert resp.json()["protocol"] == "SLMP"

            reader, writer = await asyncio.open_connection("127.0.0.1", app.server.port)
            try:
                writer.write(make_slmp_write_req(70, 0x00A8, [3333]))
                await writer.drain()
                resp_bytes = await asyncio.wait_for(reader.read(1024), timeout=2)
                assert resp_bytes[:2] == b"\xD0\x00"
                assert app.device_manager.read_word("D", 70) == 3333
            finally:
                writer.close()
                await writer.wait_closed()
    finally:
        await app.stop_plc_server()
