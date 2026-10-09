import asyncio
import socket
import struct
import pytest
import httpx
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.protocol.constants import DeviceCode3E


def make_3e_write_req(dev_code: int = 0xA8, addr: int = 100, values: list[int] = [1234]) -> bytes:
    count = len(values)
    val_bytes = b"".join(struct.pack("<H", v) for v in values)
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    cmd_data = struct.pack("<HH", 0x1401, 0x0000) + dev_bytes + struct.pack("<H", count) + val_bytes
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_remote_run_req(mode: int = 1, clear_mode: int = 0) -> bytes:
    # 0x1001, subcommand 0x0000, mode (2 bytes), clear_mode (1 byte), reserved (1 byte)
    cmd_data = struct.pack("<HHHBx", 0x1001, 0x0000, mode, clear_mode)
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def make_remote_stop_req(mode: int = 1) -> bytes:
    # 0x1002, subcommand 0x0000, mode (2 bytes)
    cmd_data = struct.pack("<HHH", 0x1002, 0x0000, mode)
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
async def test_remote_run_stop_tcp():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        assert app.device_manager.plc_status == "RUN"

        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # Send Remote STOP
            writer.write(make_remote_stop_req())
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0  # Normal end code
            assert app.device_manager.plc_status == "STOP"
            assert not app.device_manager.is_running

            # Send Remote RUN
            writer.write(make_remote_run_req())
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert app.device_manager.plc_status == "RUN"
            assert app.device_manager.is_running
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_remote_run_stop_udp():
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
            # STOP
            transport.sendto(make_remote_stop_req())
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert app.device_manager.plc_status == "STOP"

            # RUN
            transport.sendto(make_remote_run_req())
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert resp[:2] == b"\xD0\x00"
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert app.device_manager.plc_status == "RUN"
        finally:
            transport.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_script_engine_pauses_during_stop_and_resumes_on_run():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    script_name = "test_run_stop.yaml"
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            content = "- type: periodic\n  interval_ms: 30\n  actions:\n    - target: D50\n      expr: 'D50 + 1'\n"
            await client.put(f"/api/scripts/{script_name}", json={"content": content})
            await client.post(f"/api/scripts/{script_name}/start")

        # Give script time to run
        await asyncio.sleep(0.1)
        val_running = app.device_manager.read_word("D", 50)
        assert val_running >= 2

        # Client sends Remote STOP via socket
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            writer.write(make_remote_stop_req())
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert app.device_manager.plc_status == "STOP"

            val_at_stop = app.device_manager.read_word("D", 50)
            await asyncio.sleep(0.1)
            val_after_stop = app.device_manager.read_word("D", 50)
            # Script updates must NOT advance while PLC is in STOP!
            assert val_after_stop == val_at_stop

            # Client sends Remote RUN via socket
            writer.write(make_remote_run_req())
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert app.device_manager.plc_status == "RUN"

            await asyncio.sleep(0.1)
            val_resumed = app.device_manager.read_word("D", 50)
            # Script updates resume!
            assert val_resumed > val_at_stop
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / "scripts" / script_name
        if p.exists():
            p.unlink()


@pytest.mark.asyncio
async def test_remote_run_clear_mode_resets_memory_preserving_latch():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        # Set D10 = 555, L10 (latch) = 777
        app.device_manager.write_word("D", 10, 555)
        app.device_manager.write_word("L", 10, 777)
        assert app.device_manager.read_word("D", 10) == 555
        assert app.device_manager.read_word("L", 10) == 777

        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # STOP first
            writer.write(make_remote_stop_req())
            await writer.drain()
            await reader.read(1024)

            # RUN with clear_mode=1 (clear except latch)
            writer.write(make_remote_run_req(mode=1, clear_mode=1))
            await writer.drain()
            resp = await reader.read(1024)
            assert struct.unpack_from("<H", resp, 8)[0] == 0

            # D10 is cleared (0), L10 is preserved (777)
            assert app.device_manager.read_word("D", 10) == 0
            assert app.device_manager.read_word("L", 10) == 777
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_consecutive_run_stop_consistency_across_multiple_clients():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        r1, w1 = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            w1.write(make_remote_stop_req())
            await w1.drain()
            resp = await r1.read(1024)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert app.device_manager.plc_status == "STOP"
        finally:
            w1.close()
            await w1.wait_closed()

        # Client 2 connects and sends STOP again - already STOP, returns success
        r2, w2 = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            w2.write(make_remote_stop_req())
            await w2.drain()
            resp = await r2.read(1024)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert app.device_manager.plc_status == "STOP"

            # Client 2 sends RUN
            w2.write(make_remote_run_req())
            await w2.drain()
            resp = await r2.read(1024)
            assert struct.unpack_from("<H", resp, 8)[0] == 0
            assert app.device_manager.plc_status == "RUN"
        finally:
            w2.close()
            await w2.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_invalid_parameters_return_parameter_error():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # 1002 with 1 byte payload (invalid)
            cmd_data = struct.pack("<HHB", 0x1002, 0x0000, 0x01)
            data_len = 2 + len(cmd_data)
            header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + b"\x00\x00"
            writer.write(header + cmd_data)
            await writer.drain()
            resp = await reader.read(1024)
            # Must return parameter error (0xC05B)
            assert struct.unpack_from("<H", resp, 8)[0] == 0xC05B
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_rest_api_plc_status():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            resp = await client.get("/api/plc/status")
            assert resp.status_code == 200
            assert resp.json()["status"] == "RUN"

            resp = await client.post("/api/plc/status", json={"status": "STOP"})
            assert resp.status_code == 200
            assert resp.json()["status"] == "STOP"
            assert app.device_manager.plc_status == "STOP"

            resp = await client.post("/api/plc/status", json={"status": "INVALID"})
            assert resp.status_code == 400
    finally:
        await app.stop()
