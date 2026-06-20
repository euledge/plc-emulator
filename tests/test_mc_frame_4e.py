import pytest
from src.protocol.mc_frame_4e import McFrame4E


@pytest.fixture
def handler():
    return McFrame4E()


def test_detect_4e(handler):
    assert handler.detect(b"\x54\x00") is True
    assert handler.detect(b"\x50\x00") is False
    assert handler.detect(b"") is False


def test_parse_batch_read(handler):
    data = (
        b"\x54\x00"   # subheader 4E
        b"\x00\x00\x00\x00"
        b"\x0c\x00"
        b"\x00\x00"
        b"\x01\x04"   # command 0401
        b"\x00\x00"
        b"\xA8\x64\x00\x00"  # D100
        b"\x01\x00"   # 1 point
        b"\x01\x00"   # serial number
    )
    req = handler.parse_request(data)
    assert req.command == 0x0401
    assert req.devices[0]["type"] == "D"
    assert req.devices[0]["address"] == 100


def test_build_response_success(handler):
    from src.protocol.base import CommandResult
    result = CommandResult(success=True, data=b"\x00\x00")
    resp = handler.build_response(None, result)
    assert resp[:2] == b"\xD4\x00"
    assert resp[8:10] == b"\x00\x00"
