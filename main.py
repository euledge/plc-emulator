import asyncio
import logging
import uvicorn

from src.config import ConfigManager
from src.device.device_manager import DeviceManager
from src.device.plc_models import PLC_MODELS
from src.server.latency import LatencyEmulator
from src.server.tcp_server import TcpServer
from src.server.udp_server import UdpServer
from src.web.app import AppState, create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class PLCEmulatorApp:
    def __init__(
        self,
        config: ConfigManager | None = None,
        device_manager: DeviceManager | None = None,
        latency: LatencyEmulator | None = None,
        web_port: int = 8000,
        web_host: str = "0.0.0.0",
    ) -> None:
        self.state = AppState(
            config=config,
            device_manager=device_manager,
            latency=latency,
        )
        self.config = self.state.config
        self.device_manager = self.state.device_manager
        self.latency = self.state.latency
        self.web_port = web_port
        self.web_host = web_host
        self.web_app = create_app(state=self.state)
        self._uvicorn_server: uvicorn.Server | None = None
        self._uvicorn_task: asyncio.Task | None = None

    @property
    def server(self) -> TcpServer | UdpServer | None:
        return self.state.plc_server

    async def start_plc_server(self) -> None:
        if self.config.transport == "tcp":
            self.state.plc_server = TcpServer(
                port=self.config.port,
                device_manager=self.device_manager,
                latency_emulator=self.latency,
            )
        else:
            self.state.plc_server = UdpServer(
                port=self.config.port,
                device_manager=self.device_manager,
                latency_emulator=self.latency,
            )
        await self.state.plc_server.start()

    async def stop_plc_server(self) -> None:
        if self.state.plc_server:
            await self.state.plc_server.stop()
            self.state.plc_server = None

    async def start_web_server(self) -> None:
        config = uvicorn.Config(
            self.web_app,
            host=self.web_host,
            port=self.web_port,
            log_level="warning",
        )
        self._uvicorn_server = uvicorn.Server(config=config)
        self._uvicorn_task = asyncio.create_task(self._uvicorn_server.serve())

    async def stop_web_server(self) -> None:
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
            if self._uvicorn_task:
                await self._uvicorn_task
            self._uvicorn_server = None
            self._uvicorn_task = None

    async def start(self) -> None:
        await self.start_plc_server()
        await self.start_web_server()
        logger.info(
            "PLCEmulator started: PLC %s on port %d, Web on port %d",
            self.config.transport.upper(),
            self.state.plc_server.port if self.state.plc_server else self.config.port,
            self.web_port,
        )

    async def stop(self) -> None:
        await self.stop_web_server()
        await self.stop_plc_server()
        logger.info("PLCEmulator stopped.")


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

