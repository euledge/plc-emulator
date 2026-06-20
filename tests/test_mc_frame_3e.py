import pytest
from src.protocol.mc_frame_3e import McFrame3E


@pytest.fixture
def handler():
    return McFrame3E()


def test_detect_3e_binary(handler):
    assert handler.detect(b"\x50\x00\x00" * 3) is True
    assert handler.detect(b"\x00\x00\x00\x00") is False
    assert handler.detect(b"") is False


def test_parse_batch_read_request(handler):
    data = (
        b"\x50\x00"  # subheader
        b"\x00\x00\x00\x00"  # access path
        b"\x0c\x00"  # data length (12 bytes)
        b"\x00\x00"  # timer
        b"\x01\x04"  # command 0401 (batch read)
        b"\x00\x00"  # subcommand 0000 (word)
        b"\xA8\x64\x00\x00"  # D100 (MC format)
        b"\x03\x00"  # 3 points
    )
    req = handler.parse_request(data)
    assert req.command == 0x0401
    assert req.subcommand == 0x0000
    assert len(req.devices) == 1
    assert req.devices[0]["type"] == "D"
    assert req.devices[0]["address"] == 100
    assert req.devices[0]["count"] == 3


def test_parse_batch_write_request(handler):
    data = (
        b"\x50\x00"
        b"\x00\x00\x00\x00"
        b"\x12\x00"
        b"\x00\x00"
        b"\x01\x14"  # command 1401 (batch write)
        b"\x00\x00"
        b"\xA8\x00\x00\x00"  # D0
        b"\x02\x00"  # 2 points
        b"\x01\x02\x03\x04"  # data: 0x0201, 0x0403
    )
    req = handler.parse_request(data)
    assert req.command == 0x1401
    assert req.devices[0]["type"] == "D"
    assert req.devices[0]["address"] == 0
    assert req.devices[0]["count"] == 2
    assert len(req.data) == 4


def test_build_response_success(handler):
    from src.protocol.base import CommandResult
    result = CommandResult(success=True, data=b"\x01\x02")
    resp = handler.build_response(None, result)
    assert resp[:2] == b"\xD0\x00"
    assert resp[8:10] == b"\x00\x00"


def test_build_response_error(handler):
    from src.protocol.base import CommandResult
    result = CommandResult(success=False, error_code=0xC059)
    resp = handler.build_response(None, result)
    assert resp[8:10] == b"\x59\xC0"
