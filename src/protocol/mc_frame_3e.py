import struct
from src.protocol.base import ProtocolHandler, ParsedRequest, CommandResult
from src.protocol.device_parser import parse_device_mc
from src.protocol.constants import ErrorCode


KNOWN_3E_COMMANDS = {
    0x0401, 0x1401, 0x0403, 0x1402, 0x0101, 0x0619,
    0x1001, 0x1002, 0x0801, 0x0802, 0x1630, 0x1631,
}


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

                # Check for 5-byte routing (standard MELSEC) vs 4-byte routing (legacy)
                total_len = None
                if len(buf) >= 13:
                    cmd_5 = struct.unpack_from("<H", buf, 11)[0]
                    cmd_4 = struct.unpack_from("<H", buf, 10)[0]
                    if cmd_5 in KNOWN_3E_COMMANDS:
                        data_len = struct.unpack_from("<H", buf, 7)[0]
                        total_len = 9 + data_len
                    elif cmd_4 in KNOWN_3E_COMMANDS:
                        data_len = struct.unpack_from("<H", buf, 6)[0]
                        total_len = 8 + data_len

                if total_len is None:
                    # Heuristic check based on available length
                    if len(buf) >= 9:
                        dlen_5 = struct.unpack_from("<H", buf, 7)[0]
                        dlen_4 = struct.unpack_from("<H", buf, 6)[0]
                        if 2 <= dlen_4 <= len(buf) - 8:
                            total_len = 8 + dlen_4
                        elif 2 <= dlen_5 <= len(buf) - 9:
                            total_len = 9 + dlen_5
                        else:
                            return None
                    else:
                        return None

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
        cmd_5 = struct.unpack_from("<H", data, 11)[0] if len(data) >= 13 else 0
        cmd_4 = struct.unpack_from("<H", data, 10)[0] if len(data) >= 12 else 0

        if cmd_5 in KNOWN_3E_COMMANDS:
            req.access_path = data[2:7]
            data_len = struct.unpack_from("<H", data, 7)[0]
            timer = struct.unpack_from("<H", data, 9)[0]
            cmd_data = data[11:11 + data_len - 2]
        elif cmd_4 in KNOWN_3E_COMMANDS:
            req.access_path = data[2:6]
            data_len = struct.unpack_from("<H", data, 6)[0]
            timer = struct.unpack_from("<H", data, 8)[0]
            cmd_data = data[10:10 + data_len - 2]
        elif len(data) >= 9 and struct.unpack_from("<H", data, 7)[0] + 9 == len(data):
            req.access_path = data[2:7]
            data_len = struct.unpack_from("<H", data, 7)[0]
            timer = struct.unpack_from("<H", data, 9)[0]
            cmd_data = data[11:11 + data_len - 2]
        else:
            req.access_path = data[2:6]
            data_len = struct.unpack_from("<H", data, 6)[0]
            timer = struct.unpack_from("<H", data, 8)[0]
            cmd_data = data[10:10 + data_len - 2]

        req.command = struct.unpack_from("<H", cmd_data, 0)[0]
        req.subcommand = struct.unpack_from("<H", cmd_data, 2)[0]
        req.data = cmd_data[4:] if len(cmd_data) >= 4 else b""
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
                if req.subcommand in (0x0001, 0x0003):
                    byte_count = (count + 1) // 2
                    req.data = device_data[6:6 + byte_count]
                else:
                    req.data = device_data[6:6 + count * 2]
            else:
                req.data = b""
        return req

    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        if result.success:
            end_code = struct.pack("<H", ErrorCode.NORMAL)
        else:
            end_code = struct.pack("<H", result.error_code)

        resp_data = end_code + result.data
        data_len = struct.pack("<H", len(resp_data))

        access_path = (
            parsed.access_path
            if parsed is not None and getattr(parsed, "access_path", None)
            else b"\x00\x00\x00\x00"
        )
        resp = (
            self.SUBHEADER_RESPONSE
            + access_path
            + data_len
            + resp_data
        )
        return resp
