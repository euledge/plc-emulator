import asyncio
from pathlib import Path
from typing import TYPE_CHECKING
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from src.config import ConfigManager
from src.device.device_manager import DeviceManager
from src.device.plc_models import PLC_MODELS
from src.persistence.persistence_manager import PersistenceManager
from src.server.latency import LatencyEmulator
from src.web.api_routes import router
from src.web.websocket_handler import WebSocketManager

if TYPE_CHECKING:
    from src.server.tcp_server import TcpServer
    from src.server.udp_server import UdpServer


class AppState:
    def __init__(
        self,
        config: ConfigManager | None = None,
        device_manager: DeviceManager | None = None,
        latency: LatencyEmulator | None = None,
    ) -> None:
        self.config = config or ConfigManager()
        self.config_lock = asyncio.Lock()
        model = PLC_MODELS.get(self.config.plc_model)
        self.device_manager = device_manager or DeviceManager(plc_model=model)
        self.latency = latency or LatencyEmulator()
        self.ws_manager = WebSocketManager()
        self.persistence = PersistenceManager(self.device_manager)
        self.plc_server: TcpServer | UdpServer | None = None


def create_app(state: AppState | None = None) -> FastAPI:
    app = FastAPI(title="PLCEmulator")
    if state is None:
        state = AppState()
    app.state.state = state
    app.include_router(router)

    static_dir = Path(__file__).resolve().parent.parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def root():
        index = static_dir / "index.html"
        return HTMLResponse(index.read_text(encoding="utf-8"))

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await state.ws_manager.connect(ws)
        try:
            while True:
                data = await ws.receive_json()
        except WebSocketDisconnect:
            state.ws_manager.disconnect(ws)

    return app
