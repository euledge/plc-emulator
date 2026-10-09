import asyncio
import struct
import pytest
import httpx
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


@pytest.mark.asyncio
async def test_export_comm_log_empty():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            resp = await client.get("/api/comm_log/export")
            assert resp.status_code == 200
            assert resp.text == ""
            assert "comm_log.txt" in resp.headers.get("Content-Disposition", "")
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_export_comm_log_populated_matches_displayed_content():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        # Send a request over PLC socket
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            writer.write(make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 100, 1))
            await writer.drain()
            await reader.read(1024)
        finally:
            writer.close()
            await writer.wait_closed()

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            resp = await client.get("/api/comm_log/export")
            assert resp.status_code == 200
            content = resp.text
            lines = content.strip().split("\n")
            assert len(lines) == 2  # RX and TX

            # Check RX line
            assert "←" in lines[0]
            assert "[Batch Read (0401)]" in lines[0]
            assert "50 00" in lines[0]

            # Check TX line
            assert "→" in lines[1]
            assert "[Response (3E)]" in lines[1]
            assert "D0 00" in lines[1]

            # Verify exporting did NOT clear the logs
            assert len(app.state.comm_logs) == 2
            resp2 = await client.get("/api/comm_log/export")
            assert resp2.text == content
    finally:
        await app.stop()
