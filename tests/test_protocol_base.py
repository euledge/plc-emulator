import struct
import pytest
from src.protocol.base import ProtocolHandler, ParsedRequest, CommandResult


class ConcreteHandler(ProtocolHandler):
    def parse_request(self, data: bytes) -> ParsedRequest:
        return ParsedRequest(command=0x0401, subcommand=0x0000, data=b"")

    def build_response(self, parsed: ParsedRequest, result: CommandResult) -> bytes:
        return b"response"

    def detect(self, data: bytes) -> bool:
        return data[:2] == b"\x50\x00"


def test_parse_request():
    handler = ConcreteHandler()
    req = handler.parse_request(b"\x50\x00" + b"\x00" * 20)
    assert req.command == 0x0401
    assert req.subcommand == 0x0000


def test_build_response():
    handler = ConcreteHandler()
    parsed = ParsedRequest(command=0x0401, subcommand=0x0000)
    result = CommandResult(success=True, data=struct.pack("<H", 0x0000))
    resp = handler.build_response(parsed, result)
    assert resp == b"response"


def test_detect():
    handler = ConcreteHandler()
    assert handler.detect(b"\x50\x00\x01\x00") is True
    assert handler.detect(b"\xd0\x00\x01\x00") is False


def test_abstract_class_cannot_be_instantiated():
    with pytest.raises(TypeError):
        ProtocolHandler()
