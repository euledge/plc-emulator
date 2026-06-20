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
