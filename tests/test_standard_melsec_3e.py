import asyncio
import struct
import pytest
from main import PLCEmulatorApp
from src.config import ConfigManager


def make_standard_melsec_3e_req(command: int, subcommand: int, dev_code: int, addr: int, count: int) -> bytes:
    """Standard Mitsubishi MELSEC 3E Binary format with 5-byte routing header."""
    # Subheader: 50 00
    # Network No: 00
    # PC No: FF
    # Unit I/O: FF 03
    # Station No: 00
    routing = b"\x50\x00\x00\xFF\xFF\x03\x00"
    timer = b"\x10\x00"  # 16 (4 seconds)
    cmd = struct.pack("<HH", command, subcommand)
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    points = struct.pack("<H", count)
    payload = timer + cmd + dev_bytes + points
    data_len = struct.pack("<H", len(payload))
    return routing + data_len + payload


@pytest.mark.asyncio
async def test_standard_melsec_5byte_routing_batch_read_and_response_format():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")

    # Set D100=100, D101=101, D102=102, D103=103, D104=104
    for i in range(5):
        app.device_manager.write_word("D", 100 + i, 100 + i)

    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            req = make_standard_melsec_3e_req(0x0401, 0x0000, 0xA8, 100, 5)
            writer.write(req)
            await writer.drain()

            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)

            # Response header checks
            # 1. Subheader: D0 00
            assert resp[:2] == b"\xD0\x00"
            # 2. Access path: 5 bytes echoed exactly (00 FF FF 03 00)
            assert resp[2:7] == b"\x00\xFF\xFF\x03\x00"
            # 3. Response data len: 2 bytes
            resp_data_len = struct.unpack_from("<H", resp, 7)[0]
            # End code (2 bytes) + 5 words (10 bytes) = 12 bytes
            assert resp_data_len == 12
            # 4. End code: 00 00
            assert struct.unpack_from("<H", resp, 9)[0] == 0
            # 5. Word values: [100, 101, 102, 103, 104]
            words = struct.unpack_from("<5H", resp, 11)
            assert list(words) == [100, 101, 102, 103, 104]

            # 6. Verify Comm Log has recorded this!
            logs = list(app.state.comm_logs)
            assert len(logs) == 2  # RX and TX
            rx_log = logs[0]
            assert "Batch Read (0401)" in rx_log["command"]
            assert rx_log["direction"] == "rx"
            assert "50 00 00 FF FF 03 00" in rx_log["data"]
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()
