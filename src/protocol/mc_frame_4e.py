from src.protocol.mc_frame_3e import McFrame3E
from src.protocol.base import CommandResult, ParsedRequest


class McFrame4E(McFrame3E):
    SUBHEADER_REQUEST = b"\x54\x00"
    SUBHEADER_RESPONSE = b"\xD4\x00"

    def parse_request(self, data: bytes) -> ParsedRequest:
        req = super().parse_request(data)
        if len(data) >= 12:
            req.data = data[:-2]
        return req

    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        resp = super().build_response(parsed, result)
        resp += b"\x00\x00"
        return resp
