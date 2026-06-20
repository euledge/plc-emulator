import struct
from src.protocol.base import ProtocolHandler, ParsedRequest, CommandResult
from src.protocol.constants import DEVICE_CODE_TO_NAME_1E, ErrorCode


CMD_READ = 0x01
CMD_WRITE = 0x03


class McFrame1E(ProtocolHandler):
    def detect(self, data: bytes) -> bool:
        if len(data) < 1:
            return False
        cmd = data[0]
        return cmd in (CMD_READ, CMD_WRITE)

    def parse_request(self, data: bytes) -> ParsedRequest:
        if len(data) < 5:
            raise ValueError("Frame too short for 1E")
        req = ParsedRequest()
        cmd = data[0]
        dev_code = data[1]
        addr = struct.unpack_from("<H", data, 2)[0]
        count = struct.unpack_from("<H", data, 4)[0]

        device_name = DEVICE_CODE_TO_NAME_1E.get(dev_code)
        if device_name is None:
            raise ValueError(f"Unknown 1E device code: 0x{dev_code:02X}")

        if cmd == CMD_READ:
            req.command = 0x0401
        elif cmd == CMD_WRITE:
            req.command = 0x1401
            req.data = data[6:]

        req.subcommand = 0x0000
        req.devices.append({
            "type": device_name,
            "address": addr,
            "count": count,
        })
        return req

    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        if parsed is None:
            subheader = 0x81
        else:
            subheader = parsed.data[0] | 0x80 if parsed.data else 0x81

        if result.success:
            return bytes([subheader]) + result.data
        else:
            end_code = struct.pack("<H", result.error_code)
            return bytes([subheader]) + end_code
