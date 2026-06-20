import json
import tempfile
from pathlib import Path
import pytest
from src.device.device_manager import DeviceManager
from src.persistence.persistence_manager import PersistenceManager


@pytest.fixture
def dm():
    return DeviceManager()


@pytest.fixture
def tmp_save_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def pm(dm, tmp_save_dir):
    return PersistenceManager(dm, str(tmp_save_dir))


def test_save_creates_file(pm, tmp_save_dir):
    pm.save("test_state.json")
    assert (tmp_save_dir / "test_state.json").exists()


def test_save_contains_devices(pm, dm, tmp_save_dir):
    dm.write_word("D", 100, 1234)
    dm.write_word("M", 0, 1)
    pm.save("test_state.json")
    data = json.loads((tmp_save_dir / "test_state.json").read_text(encoding="utf-8"))
    assert "D" in data["devices"]
    assert data["devices"]["D"]["100"] == 1234


def test_load_restores_values(pm, dm, tmp_save_dir):
    dm.write_word("D", 10, 999)
    pm.save("test_state.json")
    dm.write_word("D", 10, 0)
    count = pm.load("test_state.json")
    assert count >= 1
    assert dm.read_word("D", 10) == 999


def test_load_nonexistent_raises(pm):
    with pytest.raises(FileNotFoundError):
        pm.load("nonexistent.json")


def test_save_load_preserves_multiple_devices(pm, dm):
    dm.write_word("D", 0, 100)
    dm.write_word("D", 1, 200)
    dm.write_word("W", 0, 300)
    dm.write_bit("M", 0, True)
    pm.save("multi.json")
    dm2 = DeviceManager()
    pm2 = PersistenceManager(dm2, pm._save_dir)
    pm2.load("multi.json")
    assert dm2.read_word("D", 0) == 100
    assert dm2.read_word("D", 1) == 200
    assert dm2.read_word("W", 0) == 300
    assert dm2.read_bit("M", 0) is True
