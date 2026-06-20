import struct
import pytest
from src.protocol.command_processor import CommandProcessor
from src.device.device_manager import DeviceManager


@pytest.fixture
def processor():
    dm = DeviceManager()
    return CommandProcessor(device_manager=dm)


def test_batch_read_word(processor):
    dm = processor.device_manager
    dm.write_word("D", 0, 100)
    dm.write_word("D", 1, 200)
    dm.write_word("D", 2, 300)

    result = processor.execute(0x0401, 0x0000, b"\xA8\x00\x00\x00\x03\x00")
    assert result.success is True
    assert result.data == struct.pack("<HHH", 100, 200, 300)


def test_batch_write_word(processor):
    data = b"\xA8\x00\x00\x00\x02\x00\xE8\x03\xD0\x07"
    result = processor.execute(0x1401, 0x0000, data)
    assert result.success is True
    assert processor.device_manager.read_word("D", 0) == 1000
    assert processor.device_manager.read_word("D", 1) == 2000


def test_unsupported_command(processor):
    result = processor.execute(0xFFFF, 0x0000, b"")
    assert result.success is False
    assert result.error_code == 0xC059


def test_cpu_type_read(processor):
    result = processor.execute(0x0101, 0x0000, b"")
    assert result.success is True
    assert len(result.data) == 20


def test_loopback(processor):
    test_data = b"\x01\x02\x03\x04"
    result = processor.execute(0x0619, 0x0000, test_data)
    assert result.success is True
    assert result.data == test_data


def test_remote_run(processor):
    result = processor.execute(0x1001, 0x0000, b"")
    assert result.success is True


def test_remote_stop(processor):
    result = processor.execute(0x1002, 0x0000, b"")
    assert result.success is True


def test_monitor_register(processor):
    data = b"\xA8\x00\x00\x00\x02\x00"
    result = processor.execute(0x0801, 0x0000, data)
    assert result.success is True


def test_monitor_execute(processor):
    dm = processor.device_manager
    dm.write_word("D", 0, 42)
    dm.write_word("D", 1, 99)
    data = b"\xA8\x00\x00\x00\x02\x00"
    result = processor.execute(0x0801, 0x0000, data)
    assert result.success is True
    result = processor.execute(0x0802, 0x0000, b"")
    assert result.success is True
    assert len(result.data) >= 4
