import asyncio
import json
import struct
import pytest
import websockets
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


class UdpClientProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data, addr):
        self.queue.put_nowait(data)


async def collect_comm_logs(ws, expected_count=2, timeout=2.0):
    logs = []
    end = asyncio.get_running_loop().time() + timeout
    while len(logs) < expected_count:
        rem = end - asyncio.get_running_loop().time()
        if rem <= 0:
            break
        raw = await asyncio.wait_for(ws.recv(), timeout=rem)
        msg = json.loads(raw)
        if msg.get("type") == "comm_log":
            logs.append(msg)
    return logs


@pytest.mark.asyncio
async def test_comm_log_resolves_0401_and_1401_command_names():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port
        uri = f"ws://127.0.0.1:{web_port}/ws"

        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
            try:
                # 1. 0401 Batch Read
                writer.write(make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 100, 1))
                await writer.drain()
                await reader.read(1024)

                logs = await collect_comm_logs(ws, 2)
                assert len(logs) == 2
                assert logs[0]["direction"] == "rx"
                assert "Batch Read (0401)" in logs[0]["command"]
                assert logs[1]["direction"] == "tx"
                assert "Response (3E)" in logs[1]["command"]

                # 2. 1401 Batch Write
                writer.write(make_3e_req(0x1401, 0x0000, DeviceCode3E.D, 100, 1, struct.pack("<H", 123)))
                await writer.drain()
                await reader.read(1024)

                logs2 = await collect_comm_logs(ws, 2)
                assert len(logs2) == 2
                assert logs2[0]["direction"] == "rx"
                assert "Batch Write (1401)" in logs2[0]["command"]
            finally:
                writer.close()
                await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_comm_log_resolves_udp_commands():
    cfg = ConfigManager(port=0, transport="udp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port
        uri = f"ws://127.0.0.1:{web_port}/ws"

        async with websockets.connect(uri) as ws:
            loop = asyncio.get_running_loop()
            transport, client = await loop.create_datagram_endpoint(
                UdpClientProtocol,
                remote_addr=("127.0.0.1", plc_port),
            )
            try:
                transport.sendto(make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 50, 1))
                await asyncio.wait_for(client.queue.get(), timeout=2.0)

                logs = await collect_comm_logs(ws, 2)
                assert len(logs) == 2
                assert "Batch Read (0401)" in logs[0]["command"]
                assert "Response (3E)" in logs[1]["command"]
            finally:
                transport.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_comm_log_resolves_1e_and_ascii_commands():
    # 1. Test 1E
    cfg1 = ConfigManager(port=0, transport="tcp", protocol="1E")
    app1 = PLCEmulatorApp(config=cfg1, web_port=0, web_host="127.0.0.1")
    await app1.start()
    try:
        uri = f"ws://127.0.0.1:{app1.actual_web_port}/ws"
        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_connection("127.0.0.1", app1.actual_plc_port)
            try:
                # 1E read: cmd=1
                req_1e = struct.pack("<BBHH", 0x01, 0x44, 100, 1)
                writer.write(req_1e)
                await writer.drain()
                await reader.read(1024)

                logs = await collect_comm_logs(ws, 2)
                assert len(logs) == 2
                assert "Batch Read (1E)" in logs[0]["command"]
                assert "Response" in logs[1]["command"]
            finally:
                writer.close()
                await writer.wait_closed()
    finally:
        await app1.stop()

    # 2. Test 3E ASCII
    cfg_asc = ConfigManager(port=0, transport="tcp", protocol="3E", data_format="ascii")
    app_asc = PLCEmulatorApp(config=cfg_asc, web_port=0, web_host="127.0.0.1")
    await app_asc.start()
    try:
        uri = f"ws://127.0.0.1:{app_asc.actual_web_port}/ws"
        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_connection("127.0.0.1", app_asc.actual_plc_port)
            try:
                # 3E ASCII read: 5000...0401...
                req_asc = b"5000000000000014000004010000D*0001000001"
                writer.write(req_asc)
                await writer.drain()
                await reader.read(1024)

                logs = await collect_comm_logs(ws, 2)
                assert len(logs) == 2
                assert "Batch Read (0401)" in logs[0]["command"]
                assert "Response (3E ASCII)" in logs[1]["command"]
            finally:
                writer.close()
                await writer.wait_closed()
    finally:
        await app_asc.stop()


@pytest.mark.asyncio
async def test_unparseable_frames_do_not_produce_false_commands():
    from src.web.app import resolve_command_name
    # Short / random bytes
    assert resolve_command_name("rx", b"\x00\x01\x02") == ""
    assert resolve_command_name("rx", b"NOT_A_FRAME") == ""
    assert resolve_command_name("tx", b"") == ""
    assert resolve_command_name("tx", b"\x99\x88") == ""
