import asyncio
import logging

from src.config import ConfigManager
from src.device.device_manager import DeviceManager
from src.device.plc_models import PLC_MODELS
from src.server.tcp_server import TcpServer
from src.server.udp_server import UdpServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class PLCEmulatorApp:
    def __init__(self) -> None:
        self.config = ConfigManager()
        model = PLC_MODELS.get(self.config.plc_model)
        self.device_manager = DeviceManager(plc_model=model)
        self._server: TcpServer | UdpServer | None = None

    async def start(self) -> None:
        if self.config.transport == "tcp":
            self._server = TcpServer(port=self.config.port)
        else:
            self._server = UdpServer(port=self.config.port)
        await self._server.start()

    async def stop(self) -> None:
        if self._server:
            await self._server.stop()


async def main() -> None:
    app = PLCEmulatorApp()
    try:
        await app.start()
        logger.info("PLCEmulator running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await app.stop()
        logger.info("PLCEmulator shut down.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
