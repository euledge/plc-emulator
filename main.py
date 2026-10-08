import asyncio
import logging
from typing import TYPE_CHECKING
import uvicorn

from src.config import ConfigManager
from src.device.device_manager import DeviceManager
from src.device.plc_models import PLC_MODELS
from src.server.latency import LatencyEmulator
from src.server.tcp_server import TcpServer
from src.server.udp_server import UdpServer
from src.web.app import AppState, create_app

if TYPE_CHECKING:
    pass

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

    @property
    def actual_plc_port(self) -> int:
        """Return the actual bound port of the PLC server."""
        if self.state.plc_server:
            return self.state.plc_server.port
        return self.config.port

    @property
    def actual_web_port(self) -> int:
        """Return the actual bound port of the Web server (useful when configured with port 0)."""
        if self._uvicorn_server and self._uvicorn_server.servers:
            for s in self._uvicorn_server.servers:
                for sock in getattr(s, "sockets", []):
                    return sock.getsockname()[1]
        return self.web_port

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
            try:
                await self.state.plc_server.stop()
            finally:
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

        # Wait until server has finished starting up and bound sockets
        for _ in range(100):
            if self._uvicorn_task.done():
                exc = self._uvicorn_task.exception()
                if exc:
                    raise RuntimeError(f"Web server failed to start: {exc}") from exc
                raise RuntimeError("Web server terminated unexpectedly during startup.")
            if self._uvicorn_server.started:
                break
            await asyncio.sleep(0.05)
        else:
            if not self._uvicorn_server.started:
                raise TimeoutError("Web server startup timed out.")

    async def stop_web_server(self) -> None:
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True
            if self._uvicorn_task:
                try:
                    await asyncio.wait_for(self._uvicorn_task, timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    if not self._uvicorn_task.done():
                        self._uvicorn_task.cancel()
                        try:
                            await self._uvicorn_task
                        except (asyncio.CancelledError, Exception):
                            pass
            self._uvicorn_server = None
            self._uvicorn_task = None

    async def start(self) -> None:
        try:
            await self.start_plc_server()
            await self.start_web_server()
        except BaseException:
            await self.stop()
            raise

        logger.info(
            "PLCEmulator started: PLC %s on port %d, Web on port %d",
            self.config.transport.upper(),
            self.actual_plc_port,
            self.actual_web_port,
        )

    async def stop(self) -> None:
        errors: list[BaseException] = []
        try:
            await self.stop_web_server()
        except BaseException as e:
            logger.error("Error stopping web server: %s", e)
            errors.append(e)

        try:
            await self.stop_plc_server()
        except BaseException as e:
            logger.error("Error stopping PLC server: %s", e)
            errors.append(e)

        logger.info("PLCEmulator stopped.")
        if errors:
            raise errors[0]


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


