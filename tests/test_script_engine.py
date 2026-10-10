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
@pytest.mark.asyncio
async def test_typed_dword_action_writes_two_words(engine):
    script = {
        "name": "typed_dword",
        "type": "sequence",
        "loop": False,
        "steps": [
            {
                "wait_ms": 0,
                "actions": [
                    {"target": "D300", "value": 100000, "data_type": "dword"},
                ],
            }
        ],
    }
    engine.load_scripts([script])
    await engine.start()
    await asyncio.sleep(0.02)
    await engine.stop()
    assert engine.device_manager.read_word("D", 300) == 34464
    assert engine.device_manager.read_word("D", 301) == 1
@pytest.mark.asyncio
async def test_typed_long_float_and_ascii_actions(engine):
    script = {
        "name": "typed_values",
        "type": "sequence",
        "loop": False,
        "steps": [
            {
                "wait_ms": 0,
                "actions": [
                    {"target": "D310", "value": -100000, "data_type": "long"},
                    {"target": "D320", "value": 12.5, "data_type": "float32"},
                    {"target": "D330", "value": "ABC", "data_type": "ascii"},
                    {"target": "D340", "value": "PLC", "data_type": "ascii", "length": 6},
                ],
            }
        ],
    }
    engine.load_scripts([script])
    await engine.start()
    await asyncio.sleep(0.02)
    await engine.stop()
    assert engine.device_manager.read_word("D", 310) == 31072
    assert engine.device_manager.read_word("D", 311) == 65534
    assert engine.device_manager.read_word("D", 320) == 0
    assert engine.device_manager.read_word("D", 321) == 16712
    assert engine.device_manager.read_word("D", 330) == 0x4241
    assert engine.device_manager.read_word("D", 331) == 0x0043
    assert engine.device_manager.read_word("D", 340) == 0x4C50
    assert engine.device_manager.read_word("D", 341) == 0x0043
    assert engine.device_manager.read_word("D", 342) == 0
