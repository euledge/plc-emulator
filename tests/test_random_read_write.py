import asyncio
import struct
import pytest
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.protocol.constants import DeviceCode3E


def make_random_read_req(words: list[tuple[int, int]], dwords: list[tuple[int, int]]) -> bytes:
    # 0x0403, subcommand 0x0000
    # word_count, dword_count, followed by 4-byte devices
    head = bytes([len(words), len(dwords)])
    devs = bytearray()
    for code, addr in words:
        devs.extend(bytes([code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF]))
    for code, addr in dwords:
        devs.extend(bytes([code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF]))
    cmd_data = struct.pack("<HH", 0x0403, 0x0000) + head + bytes(devs)
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_random_write_req(words: list[tuple[int, int, int]], dwords: list[tuple[int, int, int]]) -> bytes:
    # 0x1402, subcommand 0x0000
    head = bytes([len(words), len(dwords)])
    entries = bytearray()
    for code, addr, val in words:
        entries.extend(bytes([code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF]))
        entries.extend(struct.pack("<H", val))
    for code, addr, val in dwords:
        entries.extend(bytes([code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF]))
        entries.extend(struct.pack("<I", val))
    cmd_data = struct.pack("<HH", 0x1402, 0x0000) + head + bytes(entries)
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_slmp_random_read_req(words: list[tuple[int, int]], dwords: list[tuple[int, int]]) -> bytes:
    # 0x0403, subcommand 0x0002
    head = bytes([len(words), len(dwords)])
    devs = bytearray()
    for code, addr in words:
        devs.extend(struct.pack("<IH", addr, code))
    for code, addr in dwords:
        devs.extend(struct.pack("<IH", addr, code))
    cmd_data = struct.pack("<HH", 0x0403, 0x0002) + head + bytes(devs)
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_slmp_random_write_req(words: list[tuple[int, int, int]], dwords: list[tuple[int, int, int]]) -> bytes:
    # 0x1402, subcommand 0x0002
    head = bytes([len(words), len(dwords)])
    entries = bytearray()
    for code, addr, val in words:
        entries.extend(struct.pack("<IH", addr, code))
        entries.extend(struct.pack("<H", val))
    for code, addr, val in dwords:
        entries.extend(struct.pack("<IH", addr, code))
        entries.extend(struct.pack("<I", val))
    cmd_data = struct.pack("<HH", 0x1402, 0x0002) + head + bytes(entries)
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
async def test_random_read_mixed_word_dword_order_and_size():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    # Pre-populate words and dwords
    app.device_manager.write_word("D", 10, 0x1111)
    app.device_manager.write_word("D", 20, 0x2222)
    # D30 Dword: lower word D30 = 0x3333, upper word D31 = 0x4444 -> 0x44443333
    app.device_manager.write_word("D", 30, 0x3333)
    app.device_manager.write_word("D", 31, 0x4444)
    # D40 Dword: lower word D40 = 0x5555, upper word D41 = 0x6666 -> 0x66665555
    app.device_manager.write_word("D", 40, 0x5555)
    app.device_manager.write_word("D", 41, 0x6666)

    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            req = make_random_read_req(
                words=[(DeviceCode3E.D, 10), (DeviceCode3E.D, 20)],
                dwords=[(DeviceCode3E.D, 30), (DeviceCode3E.D, 40)],
            )
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000

            data = resp[10:]
            # 2 words (4 bytes) + 2 dwords (8 bytes) = 12 bytes
            assert len(data) == 12
            w0, w1 = struct.unpack_from("<HH", data, 0)
            dw0, dw1 = struct.unpack_from("<II", data, 4)
            assert w0 == 0x1111
            assert w1 == 0x2222
            assert dw0 == 0x44443333
            assert dw1 == 0x66665555
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_random_write_mixed_word_dword():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            req = make_random_write_req(
                words=[(DeviceCode3E.D, 10, 0xAAAA), (DeviceCode3E.D, 20, 0xBBBB)],
                dwords=[(DeviceCode3E.D, 30, 0x12345678), (DeviceCode3E.D, 40, 0x9ABCDEF0)],
            )
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000

            # Verify in DeviceManager
            assert app.device_manager.read_word("D", 10) == 0xAAAA
            assert app.device_manager.read_word("D", 20) == 0xBBBB
            assert app.device_manager.read_word("D", 30) == 0x5678
            assert app.device_manager.read_word("D", 31) == 0x1234
            assert app.device_manager.read_word("D", 40) == 0xDEF0
            assert app.device_manager.read_word("D", 41) == 0x9ABC
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_random_read_write_udp():
    cfg = ConfigManager(port=0, transport="udp")
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
            # Write via UDP
            write_req = make_random_write_req(
                words=[(DeviceCode3E.D, 15, 0x4321)],
                dwords=[(DeviceCode3E.D, 25, 0x87654321)],
            )
            transport.sendto(write_req)
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert app.device_manager.read_word("D", 15) == 0x4321
            assert app.device_manager.read_word("D", 25) == 0x4321
            assert app.device_manager.read_word("D", 26) == 0x8765

            # Read via UDP
            read_req = make_random_read_req(
                words=[(DeviceCode3E.D, 15)],
                dwords=[(DeviceCode3E.D, 25)],
            )
            transport.sendto(read_req)
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            w_val = struct.unpack_from("<H", resp, 10)[0]
            dw_val = struct.unpack_from("<I", resp, 12)[0]
            assert w_val == 0x4321
            assert dw_val == 0x87654321
        finally:
            transport.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_random_read_write_slmp():
    cfg = ConfigManager(port=0, transport="tcp", protocol="SLMP")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # SLMP 6-byte device spec (code=0x00A8 for D)
            write_req = make_slmp_random_write_req(
                words=[(0x00A8, 60, 0x9999)],
                dwords=[(0x00A8, 70, 0x11223344)],
            )
            writer.write(write_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert app.device_manager.read_word("D", 60) == 0x9999
            assert app.device_manager.read_word("D", 70) == 0x3344
            assert app.device_manager.read_word("D", 71) == 0x1122

            # Read back
            read_req = make_slmp_random_read_req(
                words=[(0x00A8, 60)],
                dwords=[(0x00A8, 70)],
            )
            writer.write(read_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert struct.unpack_from("<H", resp, 10)[0] == 0x9999
            assert struct.unpack_from("<I", resp, 12)[0] == 0x11223344
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_out_of_range_and_short_requests_fail_correctly():
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # 1. Truncated request (declares 2 words, but only provides 1 device)
            # data_len mismatch
            cmd_data = struct.pack("<HHBB", 0x0403, 0x0000, 2, 0) + bytes([0xA8, 0, 0, 0])
            header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", 2 + len(cmd_data)) + b"\x00\x00"
            writer.write(header + cmd_data)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0xC061  # DATA_LENGTH_MISMATCH

            # 2. Out-of-range address on Q03UDE (D max is 12287, requesting D12288) -> 0xC051
            oob_req = make_random_read_req(words=[(DeviceCode3E.D, 12288)], dwords=[])
            writer.write(oob_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0xC051  # ADDRESS_RANGE_EXCEEDED

            # 3. Dword crossing boundary: D12287 requires D12287 (low) and D12288 (high)
            # D12288 is out of range, so dword read at D12287 must fail!
            cross_req = make_random_read_req(words=[], dwords=[(DeviceCode3E.D, 12287)])
            writer.write(cross_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0xC058

            # 4. Valid Dword right before boundary (D12286 uses 12286 and 12287) -> succeeds!
            valid_cross = make_random_read_req(words=[], dwords=[(DeviceCode3E.D, 12286)])
            writer.write(valid_cross)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()
