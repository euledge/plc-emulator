import asyncio
import socket
import struct
import pytest
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.protocol.constants import DeviceCode3E


def make_3e_req(command: int, subcommand: int, dev_code: int, addr: int, count: int, payload: bytes = b"") -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    cmd_data = struct.pack("<HH", command, subcommand) + dev_bytes + struct.pack("<H", count) + payload
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_slmp_req(command: int, subcommand: int, addr: int, code: int, count: int, payload: bytes = b"") -> bytes:
    dev_bytes = struct.pack("<IH", addr, code)
    cmd_data = struct.pack("<HH", command, subcommand) + dev_bytes + struct.pack("<H", count) + payload
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
async def test_bit_batch_read_write_tcp_3e():
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # Write 5 bits to M0: [1, 0, 1, 1, 0]
            # Packed into 3 bytes: 0x10, 0x11, 0x00
            bits_payload = bytes([0x10, 0x11, 0x00])
            write_req = make_3e_req(0x1401, 0x0001, DeviceCode3E.M, 0, 5, bits_payload)
            writer.write(write_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(10), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000

            # Verify in DeviceManager
            assert app.device_manager.read_bit("M", 0) is True
            assert app.device_manager.read_bit("M", 1) is False
            assert app.device_manager.read_bit("M", 2) is True
            assert app.device_manager.read_bit("M", 3) is True
            assert app.device_manager.read_bit("M", 4) is False

            # Read back 5 bits from M0
            read_req = make_3e_req(0x0401, 0x0001, DeviceCode3E.M, 0, 5)
            writer.write(read_req)
            await writer.drain()
            # 8 bytes header + 2 bytes end_code + 3 bytes data = 13 bytes
            resp = await asyncio.wait_for(reader.readexactly(13), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            data_bytes = resp[10:]
            assert data_bytes == bytes([0x10, 0x11, 0x00])
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_word_and_bit_coherence_on_same_address():
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # 1. Write word value 0x0005 to M word address 0 using subcommand 0x0000 (word)
            # 0x0005 has bits 0 and 2 set (M0=1, M1=0, M2=1)
            word_payload = struct.pack("<H", 0x0005)
            write_word_req = make_3e_req(0x1401, 0x0000, DeviceCode3E.M, 0, 1, word_payload)
            writer.write(write_word_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(10), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000

            # 2. Read back 3 bits from M0 using subcommand 0x0001 (bit)
            read_bit_req = make_3e_req(0x0401, 0x0001, DeviceCode3E.M, 0, 3)
            writer.write(read_bit_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(12), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            # 3 bits -> 2 bytes: M0(1),M1(0) -> 0x10; M2(1),M3(0) -> 0x10
            assert resp[10:] == bytes([0x10, 0x10])
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_boundary_address_and_model_range_check():
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # Q03UDE: M range is 0 to 8191.
            # 1. Write M8191 (valid boundary)
            valid_req = make_3e_req(0x1401, 0x0001, DeviceCode3E.M, 8191, 1, bytes([0x10]))
            writer.write(valid_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(10), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert app.device_manager.read_bit("M", 8191) is True

            # 2. Write M8192 (out of range) -> returns 0xC058 (DEVICE_ADDRESS_INVALID)
            oob_req = make_3e_req(0x1401, 0x0001, DeviceCode3E.M, 8192, 1, bytes([0x10]))
            writer.write(oob_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(10), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0xC058

            # 3. Read starting at M8190 count=5 (crosses boundary into 8192..8194) -> returns 0xC058
            oob_read_req = make_3e_req(0x0401, 0x0001, DeviceCode3E.M, 8190, 5)
            writer.write(oob_read_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(10), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0xC058
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_bit_batch_read_write_udp_3e():
    cfg = ConfigManager(port=0, transport="udp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        loop = asyncio.get_running_loop()
        transport, client = await loop.create_datagram_endpoint(
            UdpClientProtocol,
            remote_addr=("127.0.0.1", plc_port),
        )
        try:
            # Write 2 bits to M100: [1, 1] -> 0x11
            transport.sendto(make_3e_req(0x1401, 0x0001, DeviceCode3E.M, 100, 2, bytes([0x11])))
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert app.device_manager.read_bit("M", 100) is True
            assert app.device_manager.read_bit("M", 101) is True

            # Read back 2 bits
            transport.sendto(make_3e_req(0x0401, 0x0001, DeviceCode3E.M, 100, 2))
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert resp[10:] == bytes([0x11])
        finally:
            transport.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_slmp_bit_batch_read_write():
    cfg = ConfigManager(port=0, transport="tcp", protocol="SLMP", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # SLMP bit subcommand is 0x0003
            # Write 4 bits to M200: [1, 0, 0, 1] -> 0x10, 0x01
            payload = bytes([0x10, 0x01])
            req = make_slmp_req(0x1401, 0x0003, 200, 0x0090, 4, payload)
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(10), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert app.device_manager.read_bit("M", 200) is True
            assert app.device_manager.read_bit("M", 201) is False
            assert app.device_manager.read_bit("M", 202) is False
            assert app.device_manager.read_bit("M", 203) is True

            # Read back 4 bits with SLMP
            read_req = make_slmp_req(0x0401, 0x0003, 200, 0x0090, 4)
            writer.write(read_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(12), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert resp[10:] == bytes([0x10, 0x01])
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_subcommand_0000_word_behavior_unbroken():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # Standard word write/read D0 = [1234, 5678] with subcommand 0x0000
            w_payload = struct.pack("<HH", 1234, 5678)
            req = make_3e_req(0x1401, 0x0000, DeviceCode3E.D, 0, 2, w_payload)
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(10), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert app.device_manager.read_word("D", 0) == 1234
            assert app.device_manager.read_word("D", 1) == 5678

            read_req = make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 0, 2)
            writer.write(read_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(14), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            v0, v1 = struct.unpack_from("<HH", resp, 10)
            assert (v0, v1) == (1234, 5678)
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()
