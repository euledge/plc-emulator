import struct
from src.protocol.base import CommandResult, ParsedRequest
from src.protocol.constants import ErrorCode
from src.protocol.device_parser import parse_device_mc, parse_device_slmp
from src.protocol.mc_frame_3e import KNOWN_3E_COMMANDS

class McFrame4E:
    SUBHEADER_REQUEST = b"\x54\x00"
    SUBHEADER_RESPONSE = b"\xD4\x00"
    def detect(self, data: bytes) -> bool:
        return len(data) >= 2 and data[:2] == self.SUBHEADER_REQUEST
    def extract_frame(self, buf: bytearray) -> bytes | None:
        while len(buf) >= 2:
            if buf[:2] != self.SUBHEADER_REQUEST:
                del buf[0]; continue
            if len(buf) < 10: return None
            if len(buf) >= 17 and struct.unpack_from("<H", buf, 15)[0] in KNOWN_3E_COMMANDS:
                n = struct.unpack_from("<H", buf, 11)[0]
                if n >= 2 and 13 + n <= len(buf):
                    frame = bytes(buf[:13 + n]); del buf[:13 + n]; return frame
            n = struct.unpack_from("<H", buf, 6)[0]; total = 8 + n
            if len(buf) < total: return None
            frame = bytes(buf[:total]); del buf[:total]; return frame
        return None
    def parse_request(self, data: bytes) -> ParsedRequest:
        standard = len(data) >= 17 and struct.unpack_from("<H", data, 15)[0] in KNOWN_3E_COMMANDS and 13 + struct.unpack_from("<H", data, 11)[0] == len(data)
        if standard:
            n = struct.unpack_from("<H", data, 11)[0]; cmd = data[15:15 + n - 2]; req = ParsedRequest(access_path=data[6:11], serial=data[2:4], frame_type="standard-4e"); parser, width = parse_device_slmp, 6
        else:
            if len(data) < 10: raise ValueError("Frame too short for 4E")
            n = struct.unpack_from("<H", data, 6)[0]; cmd = data[10:10 + n - 2]; req = ParsedRequest(access_path=data[2:6], frame_type="legacy-4e"); req.serial = data[-2:] if len(data) >= 12 else b"\x00\x00"; parser, width = parse_device_mc, 4
        req.command, req.subcommand = struct.unpack_from("<HH", cmd, 0); req.data = cmd[4:]
        if req.command in (0x0401, 0x1401):
            dev, addr = parser(cmd[4:4 + width]); count = struct.unpack_from("<H", cmd, 4 + width)[0]; req.devices.append({"type": dev, "address": addr, "count": count})
            if req.command == 0x1401:
                size = (count + 1) // 2 if req.subcommand in (1, 3) else count * 2; req.data = cmd[6 + width:6 + width + size]
            else: req.data = b""
        return req
    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        payload = struct.pack("<H", ErrorCode.NORMAL if result.success else result.error_code) + result.data
        if parsed is not None and parsed.frame_type == "standard-4e": return self.SUBHEADER_RESPONSE + parsed.serial + b"\x00\x00" + parsed.access_path + struct.pack("<H", len(payload)) + payload
        path = parsed.access_path if parsed is not None else b"\x00\x00\x00\x00"; return self.SUBHEADER_RESPONSE + path + struct.pack("<H", len(payload)) + payload + (parsed.serial if parsed else b"")
