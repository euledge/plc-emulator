from src.device.plc_models import PLC_MODELS, PlcModel


def test_q03ude_model():
    model = PLC_MODELS["Q03UDE"]
    assert model.cpu_type_string == "Q03UDE"
    assert model.device_range("D") == (0, 12287)
    assert model.device_range("M") == (0, 8191)


def test_r04cpu_model():
    model = PLC_MODELS["R04CPU"]
    assert model.cpu_type_string == "R04CPU"
    assert model.device_range("D") == (0, 65535)
    assert model.device_range("M") == (0, 65535)


def test_fx5u_model():
    model = PLC_MODELS["FX5U"]
    assert model.cpu_type_string == "FX5UCPU"
    assert model.device_range("D") == (0, 32767)


def test_device_range_unknown_device_returns_none():
    model = PLC_MODELS["Q03UDE"]
    assert model.device_range("ZZ") is None
