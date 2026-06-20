import asyncio
import logging

logger = logging.getLogger(__name__)


class TcpServer:
    def __init__(self, port: int = 5000, host: str = "0.0.0.0") -> None:
        self.port = port
        self.host = host
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        if self.port == 0:
            port = self._server.sockets[0].getsockname()[1]
            self.port = port
        logger.info("TCP server started on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info("TCP server stopped")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peername = writer.get_extra_info("peername")
        logger.info("Client connected: %s", peername)
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error handling client")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info("Client disconnected: %s", peername)
