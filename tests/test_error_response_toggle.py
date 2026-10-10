import asyncio
import socket
import struct
import pytest
import httpx
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


class UdpClientProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data, addr):
        self.queue.put_nowait(data)


@pytest.mark.asyncio
async def test_error_response_toggle_via_api():
    cfg = ConfigManager(port=0)
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # Default is True
            cfg_resp = await client.get("/api/config")
            assert cfg_resp.json()["error_response_enabled"] is True

            # Toggle OFF
            put_resp = await client.put("/api/config", json={"error_response_enabled": False})
            assert put_resp.status_code == 200
            assert put_resp.json()["error_response_enabled"] is False

            cfg_resp = await client.get("/api/config")
            assert cfg_resp.json()["error_response_enabled"] is False

            # Toggle ON
            put_resp = await client.put("/api/config", json={"error_response_enabled": True})
            assert put_resp.status_code == 200
            assert put_resp.json()["error_response_enabled"] is True
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_tcp_error_response_on_and_off():
    cfg = ConfigManager(port=0, transport="tcp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
        try:
            # 1. Error response ON: invalid request returns error code (0xC051)
            bad_req = make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 99999, 1)
            writer.write(bad_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == ErrorCode.ADDRESS_RANGE_EXCEEDED

            # 2. Toggle error response OFF via API
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
                res = await client.put("/api/config", json={"error_response_enabled": False})
                assert res.status_code == 200

            # 3. Same invalid request: server drops response (silent no-response)
            writer.write(bad_req)
            await writer.drain()
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1024), timeout=0.3)

            # 4. Valid request: normal response is STILL returned when OFF!
            good_req = make_3e_req(0x1401, 0x0000, DeviceCode3E.D, 100, 1, struct.pack("<H", 7777))
            writer.write(good_req)
            await writer.drain()
            good_resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", good_resp, 8)[0] == 0x0000
            assert app.device_manager.read_word("D", 100) == 7777

            # 5. Toggle error response back ON
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
                res = await client.put("/api/config", json={"error_response_enabled": True})
                assert res.status_code == 200

            # 6. Invalid request now returns error response again
            writer.write(bad_req)
            await writer.drain()
            resp_on = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert struct.unpack_from("<H", resp_on, 8)[0] == ErrorCode.ADDRESS_RANGE_EXCEEDED
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_udp_error_response_on_and_off():
    cfg = ConfigManager(port=0, transport="udp", plc_model="Q03UDE")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        plc_port = app.actual_plc_port

        loop = asyncio.get_running_loop()
        transport, client = await loop.create_datagram_endpoint(
            UdpClientProtocol,
            remote_addr=("127.0.0.1", plc_port),
        )
        try:
            bad_req = make_3e_req(0x0401, 0x0000, DeviceCode3E.D, 99999, 1)

            # 1. Error response ON: receives error response
            transport.sendto(bad_req)
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == ErrorCode.ADDRESS_RANGE_EXCEEDED

            # 2. Toggle error response OFF via API
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as http_client:
                await http_client.put("/api/config", json={"error_response_enabled": False})

            # 3. Invalid request drops response
            transport.sendto(bad_req)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(client.queue.get(), timeout=0.3)

            # 4. Valid request still receives response
            good_req = make_3e_req(0x1401, 0x0000, DeviceCode3E.D, 200, 1, struct.pack("<H", 8888))
            transport.sendto(good_req)
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
            assert app.device_manager.read_word("D", 200) == 8888
        finally:
            transport.close()
    finally:
        await app.stop()
