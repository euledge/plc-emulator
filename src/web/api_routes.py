import asyncio
import os
from pathlib import Path
import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from src.scripting.engine import ScriptEngine

router = APIRouter(prefix="/api")

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"


class ConfigUpdate(BaseModel):
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


class SaveLoadRequest(BaseModel):
    name: str = "plc_state.json"


def get_state(request: Request):
    return request.app.state.state


@router.get("/config")
def get_config(request: Request):
    state = get_state(request)
    return state.config.to_dict()


@router.put("/config")
def put_config(request: Request, update: ConfigUpdate):
    state = get_state(request)
    for key, val in update.model_dump(exclude_none=True).items():
        setattr(state.config, key, val)
    return state.config.to_dict()


@router.get("/devices/{device_type}")
def get_devices(device_type: str, start: int = 0, count: int = 10, request: Request = None):
    state = get_state(request)
    values = state.device_manager.batch_read(device_type.upper(), start, count)
    return {"type": device_type.upper(), "start": start, "values": values}


@router.put("/devices/{device_type}/{address}")
def put_device(device_type: str, address: int, update: DeviceValueUpdate, request: Request = None):
    state = get_state(request)
    state.device_manager.write_word(device_type.upper(), address, update.value)
    return {"status": "ok"}


@router.get("/latency/stats")
def latency_stats(request: Request):
    state = get_state(request)
    return state.latency.stats()


@router.put("/latency/config")
def latency_config(update: LatencyConfigUpdate, request: Request = None):
    state = get_state(request)
    state.latency.mode = update.mode
    state.latency.params = update.params
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


@router.post("/scripts/{name}/start")
async def start_script(name: str, request: Request):
    state = get_state(request)
    path = SCRIPTS_DIR / name
    if not path.exists():
        raise HTTPException(404, "Script not found")
    content = path.read_text(encoding="utf-8")
    scripts = yaml.safe_load(content)
    if not isinstance(scripts, list):
        scripts = [scripts]
    engine = ScriptEngine(state.device_manager)
    engine.load_scripts(scripts)
    asyncio.create_task(engine.start())
    return {"status": "started"}


@router.post("/scripts/{name}/stop")
async def stop_script(name: str, request: Request):
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
