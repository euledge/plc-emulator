import pytest
from src.protocol.mc_frame_1e import McFrame1E


@pytest.fixture
def handler():
    return McFrame1E()


def test_detect_1e(handler):
    assert handler.detect(b"\x01") is True
    assert handler.detect(b"\x03") is True
    assert handler.detect(b"\x50\x00") is False
    assert handler.detect(b"") is False


def test_parse_read_request(handler):
    data = (
        b"\x01"       # subheader: read
        b"\x44"       # device code: D (0x44)
        b"\x64\x00"   # address: 100 (2 bytes LE)
        b"\x01\x00"   # points: 1
    )
    req = handler.parse_request(data)
    assert req.command == 0x0401
    assert req.devices[0]["type"] == "D"
    assert req.devices[0]["address"] == 100
    assert req.devices[0]["count"] == 1


def test_build_response_success(handler):
    from src.protocol.base import CommandResult
    result = CommandResult(success=True, data=b"\x00\x00")
    resp = handler.build_response(None, result)
    assert resp[0] == 0x81
    assert resp[1:3] == b"\x00\x00"


def test_build_response_error(handler):
    from src.protocol.base import CommandResult
    result = CommandResult(success=False, error_code=0xC059)
    resp = handler.build_response(None, result)
    assert resp[0] == 0x81
    assert len(resp) > 1
