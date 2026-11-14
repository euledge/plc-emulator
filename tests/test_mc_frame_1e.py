import struct
import pytest
from src.protocol.mc_frame_1e import (
    McFrame1E,
    CMD_BIT_READ,
    CMD_WORD_READ,
    CMD_BIT_WRITE,
    CMD_WORD_WRITE,
)
from src.protocol.base import CommandResult, ParsedRequest


@pytest.fixture
def handler():
    return McFrame1E()


def test_detect_1e(handler):
    assert handler.detect(b"\x00") is True
    assert handler.detect(b"\x01") is True
    assert handler.detect(b"\x02") is True
    assert handler.detect(b"\x03") is True
    assert handler.detect(b"\x50\x00") is False
    assert handler.detect(b"") is False


def test_parse_read_request_legacy(handler):
    data = (
        b"\x01"       # subheader: read
        b"\x44"       # device code: D (0x44)
        b"\x64\x00"   # address: 100 (2 bytes LE)
        b"\x01\x00"   # points: 1
    )
    req = handler.parse_request(data)
    assert req.command == 0x0401
    assert req.subcommand == 0x0000
    assert req.devices[0]["type"] == "D"
    assert req.devices[0]["address"] == 100
    assert req.devices[0]["count"] == 1


def test_parse_read_request_standard_12bytes(handler):
    # Standard official 1E frame:
    # subheader(1) + pc_no(1) + timer(2) + addr(4) + dev_code(2) + count(2)
    data = (
        b"\x01"               # subheader: word read
        b"\xFF"               # PC No: own station
        b"\x0A\x00"           # timer: 2500ms
        b"\x64\x00\x00\x00"   # head address: 100 (4 bytes LE)
        b"D "                 # device code: D (ASCII 2 bytes)
        b"\x02\x00"           # points: 2
    )
    req = handler.parse_request(data)
    assert req.command == 0x0401
    assert req.subcommand == 0x0000
    assert req.devices[0]["type"] == "D"
    assert req.devices[0]["address"] == 100
    assert req.devices[0]["count"] == 2


def test_parse_bit_read_and_write(handler):
    # Bit read standard
    data_bit_read = (
        b"\x00"               # subheader: bit read
        b"\xFF"
        b"\x10\x00"
        b"\x14\x00\x00\x00"   # addr: 20
        b"M "                 # dev: M
        b"\x05\x00"           # count: 5
    )
    req = handler.parse_request(data_bit_read)
    assert req.command == 0x0401
    assert req.subcommand == 0x0001
    assert req.devices[0]["type"] == "M"
    assert req.devices[0]["address"] == 20
    assert req.devices[0]["count"] == 5

    # Bit write standard (5 bits packed into 3 bytes)
    # count=5 -> (5+1)//2 = 3 bytes
    bit_data = b"\x10\x10\x00"
    data_bit_write = (
        b"\x02"               # subheader: bit write
        b"\xFF"
        b"\x10\x00"
        b"\x14\x00\x00\x00"
        b"M "
        b"\x05\x00"
    ) + bit_data
    req2 = handler.parse_request(data_bit_write)
    assert req2.command == 0x1401
    assert req2.subcommand == 0x0001
    assert req2.data == bit_data


def test_extract_frame_standard_and_legacy(handler):
    # Standard frame in buffer
    std_req = (
        b"\x01\xFF\x0A\x00"
        b"\x64\x00\x00\x00"
        b"D "
        b"\x01\x00"
    )
    buf = bytearray(std_req + b"EXTRA")
    frame = handler.extract_frame(buf)
    assert frame == std_req
    assert buf == bytearray(b"EXTRA")

    # Legacy frame in buffer
    leg_req = b"\x01\x44\x64\x00\x01\x00"
    buf2 = bytearray(leg_req + b"TRAILING")
    frame2 = handler.extract_frame(buf2)
    assert frame2 == leg_req
    assert buf2 == bytearray(b"TRAILING")


def test_build_response_success(handler):
    # Read response
    req = ParsedRequest(command=0x0401, subcommand=0x0000)
    result = CommandResult(success=True, data=b"\x34\x12")
    resp = handler.build_response(req, result)
    assert resp[0] == 0x81        # subheader
    assert resp[1] == 0x00        # end_code (success)
    assert resp[2:] == b"\x34\x12" # data

    # Write response (2 bytes total: subheader + end code 0x00)
    write_req = ParsedRequest(command=0x1401, subcommand=0x0000)
    write_result = CommandResult(success=True)
    resp_write = handler.build_response(write_req, write_result)
    assert resp_write == b"\x83\x00"

    # Bit read response
    bit_req = ParsedRequest(command=0x0401, subcommand=0x0001)
    resp_bit = handler.build_response(bit_req, CommandResult(success=True, data=b"\x10"))
    assert resp_bit == b"\x80\x00\x10"


def test_build_response_error(handler):
    req = ParsedRequest(command=0x0401, subcommand=0x0000)
    result = CommandResult(success=False, error_code=0xC059)
    resp = handler.build_response(req, result)
    assert resp[0] == 0x81
    assert resp[1] == (0xC059 & 0xFF)  # 1-byte error code
    assert len(resp) == 2
