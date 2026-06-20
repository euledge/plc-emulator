import pytest
from src.device.device_manager import DeviceManager


def test_read_write_word():
    dm = DeviceManager()
    dm.write_word("D", 100, 12345)
    assert dm.read_word("D", 100) == 12345


def test_read_write_bit():
    dm = DeviceManager()
    dm.write_bit("M", 0, True)
    assert dm.read_bit("M", 0) is True
    dm.write_bit("M", 0, False)
    assert dm.read_bit("M", 0) is False


def test_batch_read_word():
    dm = DeviceManager()
    dm.write_word("D", 0, 10)
    dm.write_word("D", 1, 20)
    dm.write_word("D", 2, 30)
    assert dm.batch_read("D", 0, 3) == [10, 20, 30]


def test_batch_write_word():
    dm = DeviceManager()
    dm.batch_write("D", 0, [100, 200, 300])
    assert dm.read_word("D", 0) == 100
    assert dm.read_word("D", 1) == 200
    assert dm.read_word("D", 2) == 300


def test_range_check_raises_on_out_of_range():
    from src.device.plc_models import PLC_MODELS
    dm = DeviceManager(plc_model=PLC_MODELS["Q03UDE"])
    with pytest.raises(ValueError, match="out of range"):
        dm.write_word("D", 20000, 1)


def test_range_check_allows_valid_access():
    from src.device.plc_models import PLC_MODELS
    dm = DeviceManager(plc_model=PLC_MODELS["Q03UDE"])
    dm.write_word("D", 0, 42)
    assert dm.read_word("D", 0) == 42


def test_no_plc_model_allows_any_address():
    dm = DeviceManager()
    dm.write_word("D", 999999, 1)
    assert dm.read_word("D", 999999) == 1


def test_change_callback_called_on_write():
    dm = DeviceManager()
    changes = []
    dm.on_change(lambda t, a, v: changes.append((t, a, v)))
    dm.write_word("D", 5, 999)
    assert ("D", 5, 999) in changes


def test_change_callback_not_called_on_read():
    dm = DeviceManager()
    changes = []
    dm.on_change(lambda t, a, v: changes.append((t, a, v)))
    dm.read_word("D", 0)
    assert len(changes) == 0


def test_change_callback_bit_write():
    dm = DeviceManager()
    changes = []
    dm.on_change(lambda t, a, v: changes.append((t, a, v)))
    dm.write_bit("M", 0, True)
    assert ("M", 0, True) in changes
