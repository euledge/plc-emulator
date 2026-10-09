import asyncio
from math import isfinite
import os
from pathlib import Path
import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from src.scripting.engine import ScriptEngine
from src.scripting.parser import ScriptParser
from src.device.device_definition import get_device_type, DeviceType

router = APIRouter(prefix="/api")

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"


class ConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: str | None = None
    transport: str | None = None
    port: int | None = None
    data_format: str | None = None
    plc_model: str | None = None
    error_response_enabled: bool | None = None
    latency_mode: str | None = None
    latency_params: dict | None = None


class DeviceValueUpdate(BaseModel):
    value: int


class LatencyConfigUpdate(BaseModel):
    mode: str
    params: dict = {}


class ScriptContent(BaseModel):
    content: str


class ScriptValidationRequest(BaseModel):
    content: str

class SaveLoadRequest(BaseModel):
    name: str = "plc_state.json"


class PlcStatusUpdate(BaseModel):
    status: str


def get_state(request: Request):
    return request.app.state.state


def validate_latency(mode: str, params: dict) -> None:
    allowed = {
        "none": (),
        "fixed": ("delay_ms",),
        "random": ("min_ms", "max_ms"),
        "normal": ("mean_ms", "std_ms"),
        "timeout": ("timeout_rate",),
    }
    if mode not in allowed:
        raise HTTPException(400, f"Unsupported latency mode: {mode}")
    for key, value in params.items():
        if (
            key not in allowed[mode]
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or value < 0
        ):
            raise HTTPException(400, f"Invalid latency parameter: {key}")
    if mode == "random" and params.get("min_ms", 0) > params.get("max_ms", 0):
        raise HTTPException(400, "Latency min_ms exceeds max_ms")
    if mode == "timeout" and params.get("timeout_rate", 0) > 1:
        raise HTTPException(400, "Latency timeout_rate must be at most 1")


@router.get("/config")
def get_config(request: Request):
    state = get_state(request)
    return state.config.to_dict()


@router.put("/config")
async def put_config(request: Request, update: ConfigUpdate):
    state = get_state(request)
    async with state.config_lock:
        return await apply_config_update(state, update)


async def apply_config_update(state, update: ConfigUpdate):
    from src.device.plc_models import PLC_MODELS
    from src.server.tcp_server import TcpServer
    from src.server.udp_server import UdpServer
    from src.protocol import create_protocol_handler

    if update.protocol is not None and update.protocol.upper() not in ("1E", "3E", "4E", "SLMP"):
        raise HTTPException(400, f"Unsupported protocol: {update.protocol}")
    if update.data_format is not None and update.data_format.lower() not in ("binary", "ascii"):
        raise HTTPException(400, f"Unsupported data format: {update.data_format}")

    # 1. Validate PLC model if provided
    if update.plc_model is not None:
        model = PLC_MODELS.get(update.plc_model)
        if not model:
            raise HTTPException(400, f"Unknown PLC model: {update.plc_model}")

    # 2. Validate port if provided (0 allows OS ephemeral port allocation, e.g. in tests)
    if update.port is not None and (update.port < 0 or update.port > 65535):
        raise HTTPException(400, f"Invalid port: {update.port}")

    # 3. Validate transport if provided
    if update.transport is not None and update.transport.lower() not in ("tcp", "udp"):
        raise HTTPException(400, f"Invalid transport: {update.transport}")
    changes = update.model_dump(exclude_none=True)
    if update.latency_mode is not None or update.latency_params is not None:
        mode = update.latency_mode or state.latency.mode
        params = (
            update.latency_params
            if update.latency_params is not None
            else ({} if update.latency_mode is not None else state.latency.params)
        )
        validate_latency(mode, params)
        changes["latency_params"] = params


    # Bind the replacement before disturbing active clients. Unchanged settings
    # must not disconnect them either.
    new_protocol = (update.protocol or state.config.protocol).upper()
    new_protocol = (update.protocol or state.config.protocol).upper()
    protocol_changed = new_protocol != state.config.protocol.upper()
    new_format = (update.data_format or state.config.data_format).lower()
    format_changed = new_format != state.config.data_format.lower()
    new_transport = (update.transport or state.config.transport).lower()
    new_port = update.port if update.port is not None else state.config.port
    new_error_resp = (
        update.error_response_enabled
        if update.error_response_enabled is not None
        else state.config.error_response_enabled
    )
    old_server = state.plc_server
    if old_server is not None:
        old_server.error_response_enabled = new_error_resp

    if old_server is not None and (
        new_transport != state.config.transport.lower()
        or (new_port != state.config.port and new_port != old_server.port)
    ):
        server_type = TcpServer if new_transport == "tcp" else UdpServer
        new_server = server_type(
            port=new_port,
            host=old_server.host,
            device_manager=state.device_manager,
            latency_emulator=state.latency,
            protocol_handler=create_protocol_handler(new_protocol, data_format=new_format),
            on_comm_log=old_server.on_comm_log or state.on_comm_log,
            error_response_enabled=new_error_resp,
        )
        try:
            await new_server.start()
        except Exception as e:
            await new_server.stop()
            raise HTTPException(400, f"Cannot switch communication server: {e}") from e
        try:
            await old_server.stop()
        except Exception:
            await new_server.stop()
            raise
        state.plc_server = new_server
    elif old_server is not None and (protocol_changed or format_changed):
        old_server.protocol_handler = create_protocol_handler(new_protocol, data_format=new_format)
        if hasattr(old_server, "_active_writer") and old_server._active_writer:
            try:
                old_server._active_writer.close()
            except Exception:
                pass
    if update.plc_model is not None:
        state.device_manager.plc_model = model

    if "latency_mode" in changes:
        state.latency.mode = changes["latency_mode"]
    if "latency_params" in changes:
        state.latency.params = changes["latency_params"]
    for key, val in changes.items():
        if key in ("transport", "data_format"):
            val = val.lower()
        elif key == "protocol":
            val = val.upper()
        setattr(state.config, key, val)

    return state.config.to_dict()


@router.get("/devices/{device_type}")
def get_devices(device_type: str, start: int = 0, count: int = 10, request: Request = None):
    state = get_state(request)
    dev = device_type.upper()
    dtype = get_device_type(dev)
    if dtype is None:
        raise HTTPException(400, f"Unknown device type: {device_type}")
    try:
        if dtype == DeviceType.BIT:
            values = [1 if state.device_manager.read_bit(dev, start + i) else 0 for i in range(count)]
        else:
            values = state.device_manager.batch_read(dev, start, count)
        return {"type": dev, "start": start, "values": values}
    except (ValueError, IndexError) as e:
        raise HTTPException(400, str(e))


@router.put("/devices/{device_type}/{address}")
async def put_device(device_type: str, address: int, update: DeviceValueUpdate, request: Request = None):
    state = get_state(request)
    dev = device_type.upper()
    dtype = get_device_type(dev)
    if dtype is None:
        raise HTTPException(400, f"Unknown device type: {device_type}")
    try:
        if dtype == DeviceType.BIT:
            state.device_manager.write_bit(dev, address, bool(update.value))
        else:
            if update.value < 0 or update.value > 65535:
                raise HTTPException(400, "Word value must be between 0 and 65535")
            state.device_manager.write_word(dev, address, update.value)
        return {"status": "ok"}
    except (ValueError, IndexError) as e:
        raise HTTPException(400, str(e))


@router.get("/latency/stats")
def latency_stats(request: Request):
    state = get_state(request)
    return state.latency.stats()


@router.put("/latency/config")
async def latency_config(update: LatencyConfigUpdate, request: Request = None):
    state = get_state(request)
    async with state.config_lock:
        await apply_config_update(
            state, ConfigUpdate(latency_mode=update.mode, latency_params=update.params)
        )
    return {"status": "ok"}


@router.get("/scripts")
def list_scripts():
    if not SCRIPTS_DIR.exists():
        return []
    return sorted(f.name for f in SCRIPTS_DIR.iterdir() if f.suffix in (".yaml", ".yml"))


@router.get("/scripts/{name}")
def get_script(name: str):
    path = SCRIPTS_DIR / name
    if not path.exists() or path.suffix not in (".yaml", ".yml"):
        raise HTTPException(404, "Script not found")
    return {"name": name, "content": path.read_text(encoding="utf-8")}


@router.put("/scripts/{name}")
def save_script(name: str, data: ScriptContent):
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRIPTS_DIR / name
    if path.suffix not in (".yaml", ".yml"):
        raise HTTPException(400, "Only .yaml/.yml files allowed")
    path.write_text(data.content, encoding="utf-8")
    return {"status": "ok"}


@router.post("/scripts/validate")
def validate_script_endpoint(req: ScriptValidationRequest):
    valid, errors = ScriptParser.validate_content(req.content)
    return {
        "valid": valid,
        "errors": errors,
        "message": "Script is valid" if valid else (errors[0] if errors else "Validation failed"),
    }

@router.get("/scripts/{name}/status")
def get_script_status(name: str, request: Request):
    state = get_state(request)
    engine = state.script_engines.get(name)
    if engine is None or not engine.running:
        status = "stopped"
    elif engine.paused:
        status = "paused"
    else:
        status = "running"
    return {"name": name, "status": status}


@router.post("/scripts/{name}/start")
async def start_script(name: str, request: Request):
    state = get_state(request)
    path = SCRIPTS_DIR / name
    if not path.exists():
        raise HTTPException(404, "Script not found")

    existing = state.script_engines.get(name)
    if existing is not None:
        if existing.running and existing.paused:
            existing.resume()
            return {"status": "running"}
        if existing.running:
            return {"status": "running"}
        await existing.stop()

    content = path.read_text(encoding="utf-8")
    valid, errors = ScriptParser.validate_content(content)
    if not valid:
        raise HTTPException(400, f"Script validation failed: {errors[0]}")
    scripts = yaml.safe_load(content)
    if not isinstance(scripts, list):
        if isinstance(scripts, dict) and "scripts" in scripts:
            scripts = scripts["scripts"]
        else:
            scripts = [scripts]

    engine = ScriptEngine(state.device_manager)
    engine.load_scripts(scripts)
    await engine.start()
    state.script_engines[name] = engine
    return {"status": "running"}


@router.post("/scripts/{name}/pause")
async def pause_script(name: str, request: Request):
    state = get_state(request)
    engine = state.script_engines.get(name)
    if engine is None or not engine.running:
        raise HTTPException(400, "Script is not running")
    engine.pause()
    return {"status": "paused"}


@router.post("/scripts/{name}/resume")
async def resume_script(name: str, request: Request):
    state = get_state(request)
    engine = state.script_engines.get(name)
    if engine is None or not engine.running:
        raise HTTPException(400, "Script is not running")
    engine.resume()
    return {"status": "running"}


@router.post("/scripts/{name}/stop")
async def stop_script(name: str, request: Request):
    state = get_state(request)
    engine = state.script_engines.pop(name, None)
    if engine is not None:
        await engine.stop()
    return {"status": "stopped"}

@router.post("/save")
def save_state(request: Request, data: SaveLoadRequest = SaveLoadRequest()):
    state = get_state(request)
    path = state.persistence.save(data.name)
    return {"status": "ok", "path": path}


@router.post("/load")
def load_state(request: Request, data: SaveLoadRequest = SaveLoadRequest()):
    state = get_state(request)
    try:
        count = state.persistence.load(data.name)
        return {"status": "ok", "devices_restored": count}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/i18n/{lang}")
def get_i18n(lang: str):
    from src.i18n.i18n import get_translation
    return get_translation(lang)


@router.get("/plc/status")
def get_plc_status(request: Request):
    state = get_state(request)
    return {"status": state.device_manager.plc_status}


@router.post("/plc/status")
def set_plc_status(update: PlcStatusUpdate, request: Request):
    state = get_state(request)
    try:
        state.device_manager.set_plc_status(update.status)
        return {"status": state.device_manager.plc_status}
    except ValueError as e:
        raise HTTPException(400, str(e))
