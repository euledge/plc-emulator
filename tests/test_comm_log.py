import asyncio
import json
import socket
import struct
import pytest
import websockets
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


def make_password_unlock_req(password: bytes = b"SECRET12") -> bytes:
    # 0x1630 command, subcommand 0x0000, password payload
    cmd_data = struct.pack("<HH", 0x1630, 0x0000) + password
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


class UdpClientProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data, addr):
        self.queue.put_nowait(data)

async def recv_messages_until(ws, target_comm_logs=2, timeout=2.0):
    comm_logs = []
    device_updates = []
    end_time = asyncio.get_running_loop().time() + timeout
    while len(comm_logs) < target_comm_logs:
        remaining = end_time - asyncio.get_running_loop().time()
        if remaining <= 0:
            break
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        msg = json.loads(raw)
        if msg.get("type") == "comm_log":
            comm_logs.append(msg)
        elif msg.get("type") == "device_update":
            device_updates.append(msg)
    return comm_logs, device_updates


@pytest.mark.asyncio
async def test_tcp_comm_log_rx_and_tx():
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
                writer.write(make_3e_write_req(DeviceCode3E.D, 100, [1111]))
                await writer.drain()
                resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
                assert resp[:2] == b"\xD0\x00"
            finally:
                writer.close()
                await writer.wait_closed()

            logs, updates = await recv_messages_until(ws, target_comm_logs=2)
            assert len(logs) == 2
            rx_msg = logs[0]
            tx_msg = logs[1]
            assert rx_msg["direction"] == "rx"
            assert "timestamp" in rx_msg
            assert "50 00" in rx_msg["data"]
            assert tx_msg["direction"] == "tx"
            assert "timestamp" in tx_msg
            assert "D0 00" in tx_msg["data"]
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_udp_comm_log_rx_and_tx():
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
                transport.sendto(make_3e_write_req(DeviceCode3E.D, 200, [2222]))
                resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
                assert resp[:2] == b"\xD0\x00"
            finally:
                transport.close()

            logs, updates = await recv_messages_until(ws, target_comm_logs=2)
            assert len(logs) == 2
            assert logs[0]["direction"] == "rx"
            assert logs[1]["direction"] == "tx"
    finally:
        await app.stop()

@pytest.mark.asyncio
async def test_timeout_does_not_log_tx():
    cfg = ConfigManager(port=0, transport="tcp", latency_mode="timeout", latency_params={"timeout_rate": 1.0})
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        uri = f"ws://127.0.0.1:{web_port}/ws"
        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
            try:
                writer.write(make_3e_write_req(DeviceCode3E.D, 100, [1111]))
                await writer.drain()
                # Server drops response due to timeout simulation
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(reader.read(1024), timeout=0.3)
            finally:
                writer.close()
                await writer.wait_closed()

            # Received rx log
            rx_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            rx_msg = json.loads(rx_raw)
            assert rx_msg["type"] == "comm_log"
            assert rx_msg["direction"] == "rx"

            # Should NOT receive any tx comm_log
            remaining = []
            try:
                while True:
                    msg_raw = await asyncio.wait_for(ws.recv(), timeout=0.3)
                    remaining.append(json.loads(msg_raw))
            except asyncio.TimeoutError:
                pass
            assert not any(m.get("type") == "comm_log" and m.get("direction") == "tx" for m in remaining)
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_password_command_masks_sensitive_payload():
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
                secret = b"SECRET99"
                writer.write(make_password_unlock_req(secret))
                await writer.drain()
                await asyncio.wait_for(reader.read(1024), timeout=2.0)
            finally:
                writer.close()
                await writer.wait_closed()

            rx_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            rx_msg = json.loads(rx_raw)
            assert rx_msg["type"] == "comm_log"
            assert rx_msg["direction"] == "rx"
            # Must contain masked asterisks
            assert "**" in rx_msg["data"]
            # Must NOT expose cleartext secret in hex
            secret_hex = secret.hex().upper()
            assert secret_hex not in rx_msg["data"].replace(" ", "")
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_websocket_disconnect_does_not_stop_plc_communication():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        uri = f"ws://127.0.0.1:{web_port}/ws"
        ws = await websockets.connect(uri)
        # Abruptly disconnect WebSocket
        await ws.close()

        # Send multiple PLC requests - PLC server must continue without disruption
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            for i in range(5):
                writer.write(make_3e_write_req(DeviceCode3E.D, i, [i * 10]))
                await writer.drain()
                resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
                assert resp[:2] == b"\xD0\x00"
                assert app.device_manager.read_word("D", i) == i * 10
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_comm_log_bulk_on_new_connection():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port
        web_port = app.actual_web_port

        # Send a request before any WebSocket connects
        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            writer.write(make_3e_write_req(DeviceCode3E.D, 50, [5555]))
            await writer.drain()
            await asyncio.wait_for(reader.read(1024), timeout=2.0)
        finally:
            writer.close()
            await writer.wait_closed()

        # Connect new WebSocket - should immediately receive comm_log_bulk
        uri = f"ws://127.0.0.1:{web_port}/ws"
        async with websockets.connect(uri) as ws:
            bulk_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            bulk_msg = json.loads(bulk_raw)
            assert bulk_msg["type"] == "comm_log_bulk"
            assert len(bulk_msg["entries"]) >= 2  # At least rx and tx
            assert any(e["direction"] == "rx" for e in bulk_msg["entries"])
            assert any(e["direction"] == "tx" for e in bulk_msg["entries"])
    finally:
        await app.stop()
