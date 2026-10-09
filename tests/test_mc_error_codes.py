import asyncio
import struct
import pytest
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.protocol.constants import DeviceCode3E, ErrorCode


def make_3e_req(command: int, subcommand: int, dev_code: int, addr: int, count: int, payload: bytes = b"") -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    cmd_data = struct.pack("<HH", command, subcommand) + dev_bytes + struct.pack("<H", count) + payload
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


@pytest.mark.asyncio
async def test_error_code_c051_start_address_range_exceeded():
    # Q03UDE: D range is 0..12287
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", app.actual_plc_port)
        try:
            # Start address 12288 exceeds Q03UDE D limit (12287) -> 0xC051
            req = make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 12288, 1)
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.ADDRESS_RANGE_EXCEEDED  # 0xC051
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_error_code_c056_device_specification_error():
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", app.actual_plc_port)
        try:
            # 1. Unknown device code (0xFE)
            req1 = make_3e_req(0x0401, 0x0000, 0xFE, 100, 1)
            writer.write(req1)
            await writer.drain()
            resp1 = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            end_code1 = struct.unpack_from("<H", resp1, 8)[0]
            assert end_code1 == ErrorCode.DEVICE_SPECIFICATION_ERROR  # 0xC056

            # 2. Point count is 0
            req2 = make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 100, 0)
            writer.write(req2)
            await writer.drain()
            resp2 = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            end_code2 = struct.unpack_from("<H", resp2, 8)[0]
            assert end_code2 == ErrorCode.DEVICE_SPECIFICATION_ERROR  # 0xC056
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_error_code_c058_device_address_invalid():
    # Q03UDE: D range is 0..12287
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", app.actual_plc_port)
        try:
            # Start address 12285 is within range, but count 5 crosses boundary (12285..12289 > 12287) -> 0xC058
            req = make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 12285, 5)
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.DEVICE_ADDRESS_INVALID  # 0xC058
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_error_code_c059_unsupported_command():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", app.actual_plc_port)
        try:
            # Command 0xFFFF is unsupported -> 0xC059
            req = make_3e_req(0xFFFF, 0x0000, DeviceCode3E.D, 0, 1)
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.UNSUPPORTED_COMMAND  # 0xC059
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_error_code_c05b_parameter_error():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", app.actual_plc_port)
        try:
            # Oversized points count in TCP (count 32768 exceeds limit) -> 0xC05B
            req = make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 0, 32768)
            writer.write(req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.PARAMETER_ERROR  # 0xC05B
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_error_code_c061_data_length_mismatch():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", app.actual_plc_port)
        try:
            # Batch write declares count=2 words, but only provides 1 word (2 bytes instead of 4) -> 0xC061
            dev_bytes = bytes([DeviceCode3E.D, 0, 0, 0])
            cmd_data = struct.pack("<HH", 0x1401, 0x0000) + dev_bytes + struct.pack("<H", 2) + struct.pack("<H", 1234)
            data_len = 2 + len(cmd_data)
            header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + b"\x00\x00"
            writer.write(header + cmd_data)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.DATA_LENGTH_MISMATCH  # 0xC061
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_server_continues_after_errors_and_processes_subsequent_valid_requests():
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", app.actual_plc_port)
        try:
            # 1. Send C056 error (count=0)
            writer.write(make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 0, 0))
            await writer.drain()
            r1 = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", r1, 8)[0] == 0xC056

            # 2. Send C051 error (start out of range)
            writer.write(make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 99999, 1))
            await writer.drain()
            r2 = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", r2, 8)[0] == 0xC051

            # 3. Send C059 error (unsupported command)
            writer.write(make_3e_req(0x9999, 0x0000, DeviceCode3E.D, 0, 1))
            await writer.drain()
            r3 = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", r3, 8)[0] == 0xC059

            # 4. Valid write request on the SAME connection succeeds!
            writer.write(make_3e_req(0x1401, 0x0000, DeviceCode3E.D, 100, 1, struct.pack("<H", 8888)))
            await writer.drain()
            r4 = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", r4, 8)[0] == 0x0000
            assert app.device_manager.read_word("D", 100) == 8888

            # 5. Valid read request succeeds!
            writer.write(make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 100, 1))
            await writer.drain()
            r5 = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", r5, 8)[0] == 0x0000
            assert struct.unpack_from("<H", r5, 10)[0] == 8888
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()
