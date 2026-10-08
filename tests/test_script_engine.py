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


@pytest.mark.asyncio
async def test_sequence_script(engine):
    script = {
        "name": "test_seq",
        "type": "sequence",
        "loop": False,
        "steps": [
            {
                "wait_ms": 20,
                "actions": [
                    {"target": "D10", "value": 1},
                    {"target": "M10", "value": 1},
                ],
            },
            {
                "wait_ms": 20,
                "actions": [
                    {"target": "D10", "value": 2},
                    {"target": "M10", "value": 0},
                ],
            },
        ],
    }
    engine.load_scripts([script])
    await engine.start()
    await asyncio.sleep(0.06)
    await engine.stop()
    assert engine.device_manager.read_word("D", 10) == 2
    assert engine.device_manager.read_bit("M", 10) is False


@pytest.mark.asyncio
async def test_all_example_scripts_load_and_run(engine):
    import yaml
    from pathlib import Path

    examples_dir = Path(__file__).resolve().parent.parent / "scripts" / "examples"
    yaml_files = list(examples_dir.glob("*.yaml"))
    assert len(yaml_files) >= 5
    for yf in yaml_files:
        content = yf.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            data = [data]
        eng = ScriptEngine(device_manager=DeviceManager())
        eng.load_scripts(data)
        await eng.start()
        await asyncio.sleep(0.02)
        await eng.stop()
