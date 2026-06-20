import pytest
from src.protocol.slmp_handler import SlmpHandler
from src.protocol.device_parser import encode_device_slmp


@pytest.fixture
def handler():
    return SlmpHandler()


def test_detect_slmp(handler):
    data = (
        b"\x50\x00"
        b"\x00\x00\x00\x00"
        b"\x0e\x00"
        b"\x00\x00"
        b"\x01\x04"
        b"\x02\x00"
        b"\x64\x00\x00\x00\xA8\x00"
        b"\x01\x00"
    )
    assert handler.detect(data) is True


def test_parse_slmp_batch_read(handler):
    data = (
        b"\x50\x00"
        b"\x00\x00\x00\x00"
        b"\x0e\x00"
        b"\x00\x00"
        b"\x01\x04"
        b"\x02\x00"
        b"\x64\x00\x00\x00\xA8\x00"
        b"\x01\x00"
    )
    req = handler.parse_request(data)
    assert req.command == 0x0401
    assert req.subcommand == 0x0002
    assert req.devices[0]["type"] == "D"
    assert req.devices[0]["address"] == 100


def test_encode_slmp_device():
    data = encode_device_slmp("D", 100)
    assert data == b"\x64\x00\x00\x00\xA8\x00"
