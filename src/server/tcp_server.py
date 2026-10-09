import asyncio
import logging
import struct
from typing import Callable
from src.device.device_manager import DeviceManager, DeviceSpecificationError
from src.protocol.base import ProtocolHandler, CommandResult, ParsedRequest
from src.protocol.mc_frame_3e import McFrame3E
from src.protocol.command_processor import CommandProcessor
from src.protocol.constants import ErrorCode
from src.server.latency import LatencyEmulator

logger = logging.getLogger(__name__)


class TcpServer:
    def __init__(
        self,
        port: int = 5000,
        host: str = "0.0.0.0",
        device_manager: DeviceManager | None = None,
        latency_emulator: LatencyEmulator | None = None,
        protocol_handler: ProtocolHandler | None = None,
        command_processor: CommandProcessor | None = None,
        on_comm_log: Callable[[str, bytes], None] | None = None,
        error_response_enabled: bool = True,
    ) -> None:
        self.error_response_enabled = error_response_enabled
        self.port = port
        self.host = host
        self.device_manager = device_manager or DeviceManager()
        self.latency_emulator = latency_emulator or LatencyEmulator()
        self.protocol_handler = protocol_handler or McFrame3E()
        self.command_processor = command_processor or CommandProcessor(self.device_manager)
        self.on_comm_log = on_comm_log
        self._server: asyncio.AbstractServer | None = None
        self._active_writer: asyncio.StreamWriter | None = None
        self._client_lock = asyncio.Lock()

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        if self.port == 0:
            port = self._server.sockets[0].getsockname()[1]
            self.port = port
        logger.info("TCP server started on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        async with self._client_lock:
            if self._active_writer:
                try:
                    self._active_writer.close()
                    await self._active_writer.wait_closed()
                except Exception:
                    pass
                self._active_writer = None
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info("TCP server stopped")

    def _extract_frame(self, buf: bytearray) -> bytes | None:
        if hasattr(self.protocol_handler, "extract_frame"):
            return self.protocol_handler.extract_frame(buf)
        while len(buf) >= 2:
            if buf[:2] == b"\x50\x00":
                if len(buf) < 8:
                    return None
                data_len = struct.unpack_from("<H", buf, 6)[0]
                total_len = 8 + data_len
                if len(buf) < total_len:
                    return None
                frame = bytes(buf[:total_len])
                del buf[:total_len]
                return frame
            else:
                del buf[0:1]
        return None

    async def _process_frame(self, frame: bytes) -> bytes | None:
        if self.on_comm_log:
            try:
                self.on_comm_log("rx", frame)
            except Exception:
                pass

        try:
            if not self.protocol_handler.detect(frame):
                raise ValueError("Frame does not match protocol")
            req = self.protocol_handler.parse_request(frame)
            if (
                req.command == 0x0401
                and req.devices
                and req.devices[0]["count"] > (0xFFFF - 2) // 2
            ):
                result = CommandResult(success=False, error_code=ErrorCode.PARAMETER_ERROR)
            else:
                result = self.command_processor.execute_request(req)
        except DeviceSpecificationError as e:
            logger.warning("Device specification error: %s", e)
            result = CommandResult(success=False, error_code=ErrorCode.DEVICE_SPECIFICATION_ERROR)
            req = ParsedRequest(access_path=frame[2:6] if len(frame) >= 6 else b"\x00\x00\x00\x00")
        except Exception as e:
            logger.warning("Error parsing/processing frame: %s", e)
            result = CommandResult(success=False, error_code=ErrorCode.COMMAND_TYPE_INVALID)
            req = ParsedRequest(access_path=frame[2:6] if len(frame) >= 6 else b"\x00\x00\x00\x00")

        if not result.success and not self.error_response_enabled:
            logger.info("Error response disabled: dropping error response")
            return None

        resp = self.protocol_handler.build_response(req, result)

        delay = await self.latency_emulator.apply_delay()
        if delay < 0:
            logger.info("Simulating timeout: dropping response")
            return None

        if self.on_comm_log:
            try:
                self.on_comm_log("tx", resp)
            except Exception:
                pass

        return resp

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peername = writer.get_extra_info("peername")
        logger.info("Client connected: %s", peername)

        async with self._client_lock:
            if self._active_writer is not None:
                logger.warning("Another client connected, rejecting new connection")
                writer.close()
                await writer.wait_closed()
                return
            self._active_writer = writer
            self.device_manager.reset_connection_lock()
        buf = bytearray()

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                buf.extend(data)

                while True:
                    frame = self._extract_frame(buf)
                    if frame is None:
                        break

                    resp = await self._process_frame(frame)
                    if resp is not None:
                        writer.write(resp)
                        await writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error handling client")
        finally:
            async with self._client_lock:
                if self._active_writer == writer:
                    self._active_writer = None
            self.device_manager.reset_connection_lock()
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("Client disconnected: %s", peername)
