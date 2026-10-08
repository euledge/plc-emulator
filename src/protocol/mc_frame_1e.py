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

    def extract_frame(self, buf: bytearray) -> bytes | None:
        while len(buf) >= 1:
            cmd = buf[0]
            if cmd == CMD_READ:
                if len(buf) < 6:
                    return None
                frame = bytes(buf[:6])
                del buf[:6]
                return frame
            elif cmd == CMD_WRITE:
                if len(buf) < 6:
                    return None
                count = struct.unpack_from("<H", buf, 4)[0]
                total_len = 6 + count * 2
                if len(buf) < total_len:
                    return None
                frame = bytes(buf[:total_len])
                del buf[:total_len]
                return frame
            else:
                del buf[0:1]
        return None
    def parse_request(self, data: bytes) -> ParsedRequest:
        if len(data) < 6:
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
            if len(data) != 6:
                raise ValueError("Invalid 1E read frame length")
            req.command = 0x0401
        elif cmd == CMD_WRITE:
            if len(data) != 6 + count * 2:
                raise ValueError("Invalid 1E write frame length")
            req.command = 0x1401
            req.data = data[6:]
        else:
            raise ValueError(f"Unknown 1E command: 0x{cmd:02X}")
        req.subcommand = 0x0000
        req.devices.append({
            "type": device_name,
            "address": addr,
            "count": count,
        })
        return req

    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        if parsed is not None and parsed.command == 0x1401:
            subheader = 0x83
        else:
            subheader = 0x81

        if result.success:
            return bytes([subheader]) + result.data
        else:
            end_code = struct.pack("<H", result.error_code)
            return bytes([subheader]) + end_code
