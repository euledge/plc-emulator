import struct
from src.protocol.base import ProtocolHandler, ParsedRequest, CommandResult
from src.protocol.device_parser import parse_device_mc
from src.protocol.constants import ErrorCode


class McFrame3E(ProtocolHandler):
    SUBHEADER_REQUEST = b"\x50\x00"
    SUBHEADER_RESPONSE = b"\xD0\x00"

    def detect(self, data: bytes) -> bool:
        return len(data) >= 2 and data[:2] == self.SUBHEADER_REQUEST

    def extract_frame(self, buf: bytearray) -> bytes | None:
        while len(buf) >= 2:
            if buf[:2] == self.SUBHEADER_REQUEST:
                if len(buf) < 8:
                    return None
                data_len = struct.unpack_from("<H", buf, 6)[0]
                total_len = 8 + data_len
                if len(buf) < total_len:
                    return None
                frame = bytes(buf[:total_len])
                del buf[:total_len]
                return frame
            else:
                del buf[0:1]
        return None
    def parse_request(self, data: bytes) -> ParsedRequest:
        if len(data) < 10:
            raise ValueError("Frame too short for 3E")
        req = ParsedRequest()
        req.access_path = data[2:6]
        req.data = data

        data_len = struct.unpack_from("<H", data, 6)[0]
        timer = struct.unpack_from("<H", data, 8)[0]

        cmd_data = data[10:10 + data_len - 2]  # subtract timer bytes
        req.command = struct.unpack_from("<H", cmd_data, 0)[0]
        req.subcommand = struct.unpack_from("<H", cmd_data, 2)[0]

        if req.command in (0x0401, 0x1401):
            device_data = cmd_data[4:]
            dev_type, dev_addr = parse_device_mc(device_data[:4])
            count = struct.unpack_from("<H", device_data, 4)[0]
            req.devices.append({
                "type": dev_type,
                "address": dev_addr,
                "count": count,
            })
            if req.command == 0x1401:
                req.data = device_data[6:6 + count * 2]

        return req

    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        if result.success:
            end_code = struct.pack("<H", ErrorCode.NORMAL)
        else:
            end_code = struct.pack("<H", result.error_code)

        resp_data = end_code + result.data
        data_len = struct.pack("<H", len(resp_data))

        resp = (
            self.SUBHEADER_RESPONSE
            + (parsed.access_path if parsed is not None else b"\x00\x00\x00\x00")
            + data_len
            + resp_data
        )
        return resp
