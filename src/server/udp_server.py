import asyncio
import logging
import struct
from typing import Callable
from src.device.device_manager import DeviceManager
from src.protocol.base import ProtocolHandler, CommandResult, ParsedRequest
from src.protocol.mc_frame_3e import McFrame3E
from src.protocol.command_processor import CommandProcessor
from src.protocol.constants import ErrorCode
from src.server.latency import LatencyEmulator

logger = logging.getLogger(__name__)
MAX_UDP_RESPONSE_WORDS = (65507 - 10) // 2
MAX_PENDING_DATAGRAMS = 128


class UdpServer:
    def __init__(
        self,
        port: int = 5000,
        host: str = "0.0.0.0",
        device_manager: DeviceManager | None = None,
        latency_emulator: LatencyEmulator | None = None,
        protocol_handler: ProtocolHandler | None = None,
        command_processor: CommandProcessor | None = None,
        on_comm_log: Callable[[str, bytes], None] | None = None,
    ) -> None:
        self.port = port
        self.host = host
        self.device_manager = device_manager or DeviceManager()
        self.latency_emulator = latency_emulator or LatencyEmulator()
        self.protocol_handler = protocol_handler or McFrame3E()
        self.command_processor = command_processor or CommandProcessor(self.device_manager)
        self.on_comm_log = on_comm_log
        self._transport: asyncio.DatagramTransport | None = None
        self._tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        server_self = self

        class Protocol(asyncio.DatagramProtocol):
            def __init__(self) -> None:
                self.transport: asyncio.DatagramTransport | None = None

            def connection_made(self, transport):
                self.transport = transport

            def datagram_received(self, data, addr):
                if len(data) < 1 or not server_self.protocol_handler.detect(data):
                    return
                if len(server_self._tasks) >= MAX_PENDING_DATAGRAMS:
                    return
                task = asyncio.create_task(
                    server_self._handle_datagram(data, addr, self.transport)
                )
                server_self._tasks.add(task)
                task.add_done_callback(server_self._tasks.discard)

            def error_received(self, exc):
                logger.error("UDP error: %s", exc)

        self._transport, _ = await loop.create_datagram_endpoint(
            Protocol,
            local_addr=(self.host, self.port),
        )
        if self.port == 0:
            port = self._transport.get_extra_info("sockname")[1]
            self.port = port
        logger.info("UDP server started on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._tasks:
            for task in list(self._tasks):
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        if self._transport:
            self._transport.close()
            self._transport = None
            logger.info("UDP server stopped")

    async def _handle_datagram(
        self, data: bytes, addr: tuple[str, int], transport: asyncio.DatagramTransport
    ) -> None:
        if self.on_comm_log:
            try:
                self.on_comm_log("rx", data)
            except Exception:
                pass

        # Length validation for datagrams with length header
        if hasattr(self.protocol_handler, "SUBHEADER_REQUEST"):
            if getattr(self.protocol_handler, "SUBHEADER_REQUEST", b"") == b"5000":
                if len(data) >= 16:
                    try:
                        data_len = int(data[12:16].decode("ascii"), 16)
                    except (ValueError, UnicodeDecodeError):
                        data_len = -1
                    if len(data) != 16 + data_len:
                        req = ParsedRequest(access_path=data[4:12] if len(data) >= 12 else b"00000000")
                        result = CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)
                        resp = self.protocol_handler.build_response(req, result)
                        if self.on_comm_log:
                            try:
                                self.on_comm_log("tx", resp)
                            except Exception:
                                pass
                        if transport and not transport.is_closing():
                            transport.sendto(resp, addr)
                        return
            elif len(data) >= 8:
                data_len = struct.unpack_from("<H", data, 6)[0]
                if len(data) != 8 + data_len:
                    req = ParsedRequest(access_path=data[2:6] if len(data) >= 6 else b"\x00\x00\x00\x00")
                    result = CommandResult(success=False, error_code=ErrorCode.DATA_LENGTH_MISMATCH)
                    resp = self.protocol_handler.build_response(req, result)
                    if self.on_comm_log:
                        try:
                            self.on_comm_log("tx", resp)
                        except Exception:
                            pass
                    if transport and not transport.is_closing():
                        transport.sendto(resp, addr)
                    return

        try:
            req = self.protocol_handler.parse_request(data)
            if (
                req.command == 0x0401
                and req.devices
                and req.devices[0]["count"] > MAX_UDP_RESPONSE_WORDS
            ):
                result = CommandResult(
                    success=False, error_code=ErrorCode.PARAMETER_ERROR
                )
            else:
                result = self.command_processor.execute_request(req)
        except Exception as e:
            logger.warning("Error parsing/processing datagram from %s: %s", addr, e)
            result = CommandResult(success=False, error_code=ErrorCode.COMMAND_TYPE_INVALID)
            is_ascii = getattr(self.protocol_handler, "SUBHEADER_REQUEST", b"") == b"5000"
            acc = (data[4:12] if len(data) >= 12 else b"00000000") if is_ascii else (data[2:6] if len(data) >= 6 else b"\x00\x00\x00\x00")
            req = ParsedRequest(access_path=acc)

        resp = self.protocol_handler.build_response(req, result)

        delay = await self.latency_emulator.apply_delay()
        if delay < 0:
            logger.info("Simulating timeout: dropping UDP response to %s", addr)
            return

        if self.on_comm_log:
            try:
                self.on_comm_log("tx", resp)
            except Exception:
                pass

        if transport and not transport.is_closing():
            transport.sendto(resp, addr)
