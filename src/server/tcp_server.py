import asyncio
import logging
import struct
from typing import Callable
from src.device.device_manager import DeviceManager
from src.protocol.base import ProtocolHandler, CommandResult
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
    ) -> None:
        self.port = port
        self.host = host
        self.device_manager = device_manager or DeviceManager()
        self.latency_emulator = latency_emulator or LatencyEmulator()
        self.protocol_handler = protocol_handler or McFrame3E()
        self.command_processor = command_processor or CommandProcessor(self.device_manager)
        self.on_comm_log = on_comm_log
        self._server: asyncio.AbstractServer | None = None
        self._active_writer: asyncio.StreamWriter | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        if self.port == 0:
            port = self._server.sockets[0].getsockname()[1]
            self.port = port
        logger.info("TCP server started on %s:%d", self.host, self.port)

    async def stop(self) -> None:
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
            req = self.protocol_handler.parse_request(frame)
            data_len = struct.unpack_from("<H", frame, 6)[0]
            cmd_data = frame[10:8 + data_len]
            payload = cmd_data[4:] if len(cmd_data) >= 4 else b""
            result = self.command_processor.execute(req.command, req.subcommand, payload)
        except Exception as e:
            logger.warning("Error parsing/processing frame: %s", e)
            result = CommandResult(success=False, error_code=ErrorCode.COMMAND_TYPE_INVALID)
            req = None

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

        if self._active_writer is not None:
            logger.warning("Another client connected, closing previous connection")
            try:
                self._active_writer.close()
                await self._active_writer.wait_closed()
            except Exception:
                pass

        self._active_writer = writer
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
            if self._active_writer == writer:
                self._active_writer = None
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("Client disconnected: %s", peername)

