import asyncio
from collections import deque
from datetime import datetime
from pathlib import Path
import struct
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

def sanitize_comm_log(packet: bytes) -> str:
    if len(packet) >= 14 and packet[:2] in (b"\x50\x00", b"\x54\x00", b"\xD0\x00", b"\xD4\x00"):
        cmd = struct.unpack_from("<H", packet, 10)[0]
        if cmd in (0x1630, 0x1631):
            header_hex = packet[:14].hex(" ").upper()
            masked_payload = " ".join(["**"] * (len(packet) - 14))
            return f"{header_hex} {masked_payload}".strip()
    return packet.hex(" ").upper()


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
        if latency is None:
            self.latency = LatencyEmulator()
            self.latency.mode = self.config.latency_mode
            self.latency.params = dict(self.config.latency_params)
        else:
            self.latency = latency
        self.ws_manager = WebSocketManager()
        self.persistence = PersistenceManager(self.device_manager)
        self.plc_server: TcpServer | UdpServer | None = None
        self.comm_logs: deque[dict] = deque(maxlen=100)
        try:
            self._loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        self.device_manager.on_change(self._on_device_change)

    def _on_device_change(self, device_type: str, address: int, value: int | bool) -> None:
        msg = {
            "type": "device_update",
            "device": device_type,
            "address": address,
            "value": int(value) if isinstance(value, bool) else value,
        }
        loop = self._loop
        if loop is None or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
                self._loop = loop
            except RuntimeError:
                loop = None

        if loop is not None and not loop.is_closed():
            try:
                running = asyncio.get_running_loop()
                if running is loop:
                    loop.create_task(self.ws_manager.broadcast(msg))
                else:
                    asyncio.run_coroutine_threadsafe(self.ws_manager.broadcast(msg), loop)
            except RuntimeError:
                asyncio.run_coroutine_threadsafe(self.ws_manager.broadcast(msg), loop)

    def on_comm_log(self, direction: str, packet: bytes) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        data_hex = sanitize_comm_log(packet)
        msg = {
            "type": "comm_log",
            "timestamp": timestamp,
            "direction": direction,
            "data": data_hex,
        }
        self.comm_logs.append(msg)
        loop = self._loop
        if loop is None or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
                self._loop = loop
            except RuntimeError:
                loop = None

        if loop is not None and not loop.is_closed():
            try:
                running = asyncio.get_running_loop()
                if running is loop:
                    loop.create_task(self.ws_manager.broadcast(msg))
                else:
                    asyncio.run_coroutine_threadsafe(self.ws_manager.broadcast(msg), loop)
            except RuntimeError:
                asyncio.run_coroutine_threadsafe(self.ws_manager.broadcast(msg), loop)
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
        if state.comm_logs:
            try:
                await ws.send_json({
                    "type": "comm_log_bulk",
                    "entries": list(state.comm_logs),
                })
            except Exception:
                pass
        try:
            while True:
                data = await ws.receive_json()
                if isinstance(data, dict) and data.get("type") == "monitor_add":
                    dev = str(data.get("device", "D")).upper()
                    try:
                        addr = int(data.get("address", 0))
                        val = state.device_manager.read_word(dev, addr)
                        await ws.send_json({
                            "type": "device_update",
                            "device": dev,
                            "address": addr,
                            "value": val,
                        })
                    except Exception:
                        pass
        except WebSocketDisconnect:
            state.ws_manager.disconnect(ws)

    return app
