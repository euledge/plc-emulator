import pytest
from src.config import ConfigManager


def test_default_config_values():
    cfg = ConfigManager()
    assert cfg.protocol == "3E"
    assert cfg.transport == "tcp"
    assert cfg.port == 5000
    assert cfg.data_format == "binary"
    assert cfg.plc_model == "Q03UDE"
    assert cfg.error_response_enabled is True


def test_set_and_get():
    cfg = ConfigManager()
    cfg.protocol = "4E"
    assert cfg.protocol == "4E"


def test_latency_config():
    cfg = ConfigManager()
    assert cfg.latency_mode == "none"
    assert cfg.latency_params == {}

    cfg.latency_mode = "fixed"
    cfg.latency_params = {"delay_ms": 100}
    assert cfg.latency_mode == "fixed"
    assert cfg.latency_params["delay_ms"] == 100


def test_save_and_load_config_file(tmp_path):
    cfg = ConfigManager(port=6000, protocol="4E", plc_model="R04CPU")
    file_path = tmp_path / "config.json"
    cfg.save_to_file(file_path)
    assert file_path.exists()

    loaded = ConfigManager.load_from_file(file_path)
    assert loaded.port == 6000
    assert loaded.protocol == "4E"
    assert loaded.plc_model == "R04CPU"
    assert loaded.transport == "tcp"


def test_load_non_existent_config_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        ConfigManager.load_from_file(tmp_path / "non_existent.json")


def test_from_dict_partial_keys():
    cfg = ConfigManager.from_dict({"port": 7777})
    assert cfg.port == 7777
    assert cfg.protocol == "3E"
    assert cfg.plc_model == "Q03UDE"
