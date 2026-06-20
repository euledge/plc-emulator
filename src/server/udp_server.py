import asyncio
import logging

logger = logging.getLogger(__name__)


class UdpServer:
    def __init__(self, port: int = 5000, host: str = "0.0.0.0") -> None:
        self.port = port
        self.host = host
        self._transport: asyncio.DatagramTransport | None = None

    async def start(self) -> None:
        loop = asyncio.get_event_loop()

        class Protocol(asyncio.DatagramProtocol):
            def connection_made(self, transport):
                pass

            def datagram_received(self, data, addr):
                pass

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
        if self._transport:
            self._transport.close()
            self._transport = None
            logger.info("UDP server stopped")
