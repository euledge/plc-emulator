import asyncio
import struct
import pytest
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.protocol.constants import DeviceCode3E, ErrorCode


def make_3e_req(command: int, subcommand: int, payload: bytes = b"") -> bytes:
    cmd_data = struct.pack("<HH", command, subcommand) + payload
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_3e_write_req(dev_code: int, addr: int, count: int, word_values: list[int]) -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    data_bytes = struct.pack(f"<{len(word_values)}H", *word_values)
    payload = dev_bytes + struct.pack("<H", count) + data_bytes
    return make_3e_req(0x1401, 0x0000, payload)


def make_3e_read_req(dev_code: int, addr: int, count: int) -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    payload = dev_bytes + struct.pack("<H", count)
    return make_3e_req(0x0401, 0x0000, payload)


@pytest.mark.asyncio
async def test_remote_password_unlock_and_lock_commands():
    cfg = ConfigManager(port=0, transport="tcp", remote_password="SECRET12")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # 1. Incorrect password unlock (0x1630)
            writer.write(make_3e_req(0x1630, 0x0000, b"WRONGPWD"))
            await writer.drain()
            resp = await reader.read(1024)
            # Response: subheader(2) + access_path(4) + len(2) + end_code(2)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.REMOTE_PASSWORD_MISMATCH  # 0x4A01

            # 2. Write attempt while still locked -> rejected with 0x4A03
            writer.write(make_3e_write_req(DeviceCode3E.D, 10, 1, [1234]))
            await writer.drain()
            resp = await reader.read(1024)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.REMOTE_PASSWORD_LOCKED  # 0x4A03
            assert app.device_manager.read_word("D", 10) == 0

            # 3. Correct password unlock (0x1630)
            writer.write(make_3e_req(0x1630, 0x0000, b"SECRET12"))
            await writer.drain()
            resp = await reader.read(1024)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.NORMAL  # 0x0000

            # 4. Write attempt after unlock -> succeeds!
            writer.write(make_3e_write_req(DeviceCode3E.D, 10, 1, [1234]))
            await writer.drain()
            resp = await reader.read(1024)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.NORMAL
            assert app.device_manager.read_word("D", 10) == 1234

            # 5. Lock command (0x1631)
            writer.write(make_3e_req(0x1631, 0x0000))
            await writer.drain()
            resp = await reader.read(1024)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.NORMAL

            # 6. Write attempt after lock -> rejected again with 0x4A03!
            writer.write(make_3e_write_req(DeviceCode3E.D, 10, 1, [5678]))
            await writer.drain()
            resp = await reader.read(1024)
            end_code = struct.unpack_from("<H", resp, 8)[0]
            assert end_code == ErrorCode.REMOTE_PASSWORD_LOCKED
            # D10 remains 1234, write was rejected
            assert app.device_manager.read_word("D", 10) == 1234
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_remote_password_reconnect_retains_locked_state():
    cfg = ConfigManager(port=0, transport="tcp", remote_password="MYPASSWORD")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port

        # Connection 1: Unlock and perform write
        reader1, writer1 = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            writer1.write(make_3e_req(0x1630, 0x0000, b"MYPASSWORD"))
            await writer1.drain()
            resp = await reader1.read(1024)
            assert struct.unpack_from("<H", resp, 8)[0] == ErrorCode.NORMAL

            writer1.write(make_3e_write_req(DeviceCode3E.D, 50, 1, [9999]))
            await writer1.drain()
            resp = await reader1.read(1024)
            assert struct.unpack_from("<H", resp, 8)[0] == ErrorCode.NORMAL
            assert app.device_manager.read_word("D", 50) == 9999
        finally:
            writer1.close()
            await writer1.wait_closed()

        # Small delay for socket disconnect cleanup
        await asyncio.sleep(0.05)

        # Connection 2: Reconnect -> must start in locked state
        reader2, writer2 = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # Immediate write attempt without unlocking -> must fail with 0x4A03
            writer2.write(make_3e_write_req(DeviceCode3E.D, 50, 1, [1111]))
            await writer2.drain()
            resp = await reader2.read(1024)
            assert struct.unpack_from("<H", resp, 8)[0] == ErrorCode.REMOTE_PASSWORD_LOCKED
            assert app.device_manager.read_word("D", 50) == 9999

            # Unlock on connection 2 -> succeeds
            writer2.write(make_3e_req(0x1630, 0x0000, b"MYPASSWORD"))
            await writer2.drain()
            resp = await reader2.read(1024)
            assert struct.unpack_from("<H", resp, 8)[0] == ErrorCode.NORMAL

            # Write succeeds
            writer2.write(make_3e_write_req(DeviceCode3E.D, 50, 1, [1111]))
            await writer2.drain()
            resp = await reader2.read(1024)
            assert struct.unpack_from("<H", resp, 8)[0] == ErrorCode.NORMAL
            assert app.device_manager.read_word("D", 50) == 1111
        finally:
            writer2.close()
            await writer2.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_remote_password_masked_in_comm_log():
    cfg = ConfigManager(port=0, transport="tcp", remote_password="SUPERSECRET")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            writer.write(make_3e_req(0x1630, 0x0000, b"SUPERSECRET"))
            await writer.drain()
            await reader.read(1024)

            # Check communication logs
            logs = list(app.state.comm_logs)
            assert len(logs) >= 1
            # Check that "SUPERSECRET" or raw hex bytes 53 55 50 45 52 are not in any log entry
            secret_hex = b"SUPERSECRET".hex(" ").upper()
            for entry in logs:
                assert "SUPERSECRET" not in entry["data"]
                assert secret_hex not in entry["data"]
                if entry["direction"] == "rx":
                    assert "**" in entry["data"]
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()
