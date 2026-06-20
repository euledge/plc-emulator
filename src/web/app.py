from pathlib import Path
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


class AppState:
    def __init__(self) -> None:
        self.config = ConfigManager()
        model = PLC_MODELS.get(self.config.plc_model)
        self.device_manager = DeviceManager(plc_model=model)
        self.latency = LatencyEmulator()
        self.ws_manager = WebSocketManager()
        self.persistence = PersistenceManager(self.device_manager)


def create_app() -> FastAPI:
    app = FastAPI(title="PLCEmulator")
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
