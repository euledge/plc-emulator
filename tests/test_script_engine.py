import asyncio
import pytest
from src.scripting.engine import ScriptEngine
from src.device.device_manager import DeviceManager


@pytest.fixture
def engine():
    dm = DeviceManager()
    return ScriptEngine(device_manager=dm)


@pytest.mark.asyncio
async def test_start_stop(engine):
    await engine.start()
    assert engine.running is True
    await engine.stop()
    assert engine.running is False


@pytest.mark.asyncio
async def test_load_and_run_periodic(engine):
    script = {
        "name": "test_periodic",
        "type": "periodic",
        "interval_ms": 50,
        "actions": [
            {"target": "D0", "expr": "D0 + 1"},
        ],
    }
    engine.load_scripts([script])
    await engine.start()
    await asyncio.sleep(0.15)
    await engine.stop()
    val = engine.device_manager.read_word("D", 0)
    assert val >= 1


@pytest.mark.asyncio
async def test_ramp_script(engine):
    script = {
        "name": "test_ramp",
        "type": "ramp",
        "target": "D100",
        "start_value": 0,
        "end_value": 100,
        "duration_ms": 200,
        "loop": False,
    }
    engine.load_scripts([script])
    await engine.start()
    await asyncio.sleep(0.1)
    await engine.stop()
    val = engine.device_manager.read_word("D", 100)
    assert 0 < val <= 100
