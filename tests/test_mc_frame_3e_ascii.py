import asyncio
import struct
import pytest
import httpx
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.protocol.mc_frame_3e_ascii import McFrame3EAscii
from src.server.tcp_server import TcpServer
from src.server.udp_server import UdpServer
from src.device.device_manager import DeviceManager


def make_ascii_read_req(dev: str = "D*", addr: int = 100, count: int = 1, is_bit: bool = False) -> bytes:
    subcmd = "0001" if is_bit else "0000"
    dev_str = f"{dev:<2}"[:2]
    addr_str = f"{addr:06d}"
    count_str = f"{count:04X}"
    payload = f"00000401{subcmd}{dev_str}{addr_str}{count_str}"
    data_len = f"{len(payload):04X}"
    frame = f"500000000000{data_len}{payload}"
    return frame.encode("ascii")


def make_ascii_write_req(dev: str = "D*", addr: int = 100, values: list[int] = [0x1234], is_bit: bool = False) -> bytes:
    subcmd = "0001" if is_bit else "0000"
    dev_str = f"{dev:<2}"[:2]
    addr_str = f"{addr:06d}"
    count_str = f"{len(values):04X}"
    if is_bit:
        val_str = "".join("1" if v else "0" for v in values)
    else:
        val_str = "".join(f"{v:04X}" for v in values)
    payload = f"00001401{subcmd}{dev_str}{addr_str}{count_str}{val_str}"
    data_len = f"{len(payload):04X}"
    frame = f"500000000000{data_len}{payload}"
    return frame.encode("ascii")


class UdpClientProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data, addr):
        self.queue.put_nowait(data)


@pytest.mark.asyncio
async def test_ascii_3e_read_write_tcp():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm, protocol_handler=McFrame3EAscii())
    await server.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            # 1. Write words D100=0x1234, D101=0x5678
            write_req = make_ascii_write_req("D*", 100, [0x1234, 0x5678])
            writer.write(write_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:4] == b"D000"
            assert resp[16:20] == b"0000"  # Normal end code
            assert dm.read_word("D", 100) == 0x1234
            assert dm.read_word("D", 101) == 0x5678

            # 2. Read back words D100 count=2
            read_req = make_ascii_read_req("D*", 100, 2)
            writer.write(read_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:4] == b"D000"
            assert resp[16:20] == b"0000"
            assert resp[20:] == b"12345678"

            # 3. Write bits M50..M53: [1, 0, 1, 1]
            bit_write_req = make_ascii_write_req("M*", 50, [1, 0, 1, 1], is_bit=True)
            writer.write(bit_write_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:4] == b"D000"
            assert resp[16:20] == b"0000"
            assert dm.read_bit("M", 50) is True
            assert dm.read_bit("M", 51) is False
            assert dm.read_bit("M", 52) is True
            assert dm.read_bit("M", 53) is True

            # 4. Read back bits M50 count=4
            bit_read_req = make_ascii_read_req("M*", 50, 4, is_bit=True)
            writer.write(bit_read_req)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:4] == b"D000"
            assert resp[16:20] == b"0000"
            assert resp[20:] == b"1011"
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_ascii_3e_read_write_udp():
    dm = DeviceManager()
    server = UdpServer(port=0, device_manager=dm, protocol_handler=McFrame3EAscii())
    await server.start()
    try:
        loop = asyncio.get_running_loop()
        transport, client = await loop.create_datagram_endpoint(
            UdpClientProtocol,
            remote_addr=("127.0.0.1", server.port),
        )
        try:
            # Write D200=0xABCD via UDP
            write_req = make_ascii_write_req("D*", 200, [0xABCD])
            transport.sendto(write_req)
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert resp[:4] == b"D000"
            assert resp[16:20] == b"0000"
            assert dm.read_word("D", 200) == 0xABCD

            # Read D200 via UDP
            read_req = make_ascii_read_req("D*", 200, 1)
            transport.sendto(read_req)
            resp = await asyncio.wait_for(client.queue.get(), timeout=2.0)
            assert resp[:4] == b"D000"
            assert resp[16:20] == b"0000"
            assert resp[20:] == b"ABCD"
        finally:
            transport.close()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_ascii_invalid_characters_and_incomplete_frame():
    dm = DeviceManager()
    server = TcpServer(port=0, device_manager=dm, protocol_handler=McFrame3EAscii())
    await server.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
        try:
            # 1. Unknown device code
            bad_dev = f"5000000000000014000004010000ZZ0001000001".encode("ascii")
            writer.write(bad_dev)
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            assert resp[:4] == b"D000"
            # Must return error code, NOT 0000 success
            assert resp[16:20] != b"0000"

            # 2. Length mismatch in frame (claims 0020 length but gives less)
            bad_len = f"5000000000000020000004010000".encode("ascii")
            writer.write(bad_len)
            await writer.drain()
            # Server extractor waits for more bytes or drops bad frame
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1024), timeout=0.3)
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_dynamic_switching_to_ascii_via_api():
    cfg = ConfigManager(port=0, transport="tcp", protocol="3E", data_format="binary")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        web_port = app.actual_web_port
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{web_port}") as client:
            # Switch to ascii
            resp = await client.put("/api/config", json={"data_format": "ascii"})
            assert resp.status_code == 200
            assert resp.json()["data_format"] == "ascii"

            # Connect socket and verify ASCII communication works
            reader, writer = await asyncio.open_connection("127.0.0.1", app.actual_plc_port)
            try:
                write_req = make_ascii_write_req("D*", 300, [0x9999])
                writer.write(write_req)
                await writer.drain()
                resp = await asyncio.wait_for(reader.read(1024), timeout=2.0)
                assert resp[:4] == b"D000"
                assert resp[16:20] == b"0000"
                assert app.device_manager.read_word("D", 300) == 0x9999
            finally:
                writer.close()
                await writer.wait_closed()

            # Switch back to binary
            resp = await client.put("/api/config", json={"data_format": "binary"})
            assert resp.status_code == 200
            assert resp.json()["data_format"] == "binary"
    finally:
        await app.stop()
