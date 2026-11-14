import struct
from src.protocol.base import ProtocolHandler, ParsedRequest, CommandResult
from src.protocol.constants import DEVICE_CODE_TO_NAME_1E, DEVICE_NAME_TO_CODE_3E
from src.device.device_manager import DeviceSpecificationError


CMD_BIT_READ = 0x00
CMD_WORD_READ = 0x01
CMD_BIT_WRITE = 0x02
CMD_WORD_WRITE = 0x03

SUPPORTED_COMMANDS = (CMD_BIT_READ, CMD_WORD_READ, CMD_BIT_WRITE, CMD_WORD_WRITE)


class McFrame1E(ProtocolHandler):
    def detect(self, data: bytes) -> bool:
        if len(data) < 1:
            return False
        return data[0] in SUPPORTED_COMMANDS

    def _is_valid_device_code(self, code_bytes: bytes) -> bool:
        if len(code_bytes) < 2:
            return False
        s = code_bytes.decode("latin1", errors="ignore").rstrip(" \x00").upper()
        if not s:
            return False
        if len(s) == 1:
            return ord(s) in DEVICE_CODE_TO_NAME_1E
        return s in DEVICE_NAME_TO_CODE_3E

    def _resolve_device_name(self, code_bytes: bytes) -> str:
        s = code_bytes.decode("latin1", errors="ignore").rstrip(" \x00").upper()
        if not s:
            raise DeviceSpecificationError(f"Unknown 1E device code: {code_bytes!r}")
        if len(s) == 1:
            dev_code = ord(s)
            name = DEVICE_CODE_TO_NAME_1E.get(dev_code)
            if name:
                return name
        if s in DEVICE_NAME_TO_CODE_3E:
            return s
        raise DeviceSpecificationError(f"Unknown 1E device code: {code_bytes!r}")

    def extract_frame(self, buf: bytearray) -> bytes | None:
        while len(buf) >= 1:
            cmd = buf[0]
            if cmd not in SUPPORTED_COMMANDS:
                del buf[0:1]
                continue

            # 1. Standard 1E Binary Frame (12-byte base header)
            # Layout: [cmd(1), pc_no(1), timer(2), addr(4), dev_code(2), count(2)] (+ write_data)
            # Standard frame has PC No (typically 0xFF or 0x00) and valid ASCII device code at bytes 8..10
            if len(buf) >= 12 and (buf[1] in (0xFF, 0x00) or not (buf[1] in DEVICE_CODE_TO_NAME_1E)):
                if self._is_valid_device_code(bytes(buf[8:10])):
                    count = struct.unpack_from("<H", buf, 10)[0]
                    if cmd in (CMD_BIT_READ, CMD_WORD_READ):
                        total_len = 12
                    elif cmd == CMD_WORD_WRITE:
                        total_len = 12 + count * 2
                    elif cmd == CMD_BIT_WRITE:
                        total_len = 12 + ((count + 1) // 2 if count > 0 else 0)
                    else:
                        total_len = 12

                    if len(buf) < total_len:
                        return None
                    frame = bytes(buf[:total_len])
                    del buf[:total_len]
                    return frame

            # 2. Legacy / Simplified 6-byte base header Frame
            # Layout: [cmd(1), dev_code(1), addr(2), count(2)] (+ write_data)
            if len(buf) < 6:
                return None
            count = struct.unpack_from("<H", buf, 4)[0]
            if cmd in (CMD_BIT_READ, CMD_WORD_READ):
                total_len = 6
            elif cmd == CMD_WORD_WRITE:
                total_len = 6 + count * 2
            elif cmd == CMD_BIT_WRITE:
                total_len = 6 + ((count + 1) // 2 if count > 0 else 0)
            else:
                total_len = 6

            if len(buf) < total_len:
                return None
            frame = bytes(buf[:total_len])
            del buf[:total_len]
            return frame

        return None

    def parse_request(self, data: bytes) -> ParsedRequest:
        if len(data) < 6:
            raise ValueError("Frame too short for 1E")

        cmd = data[0]
        if cmd not in SUPPORTED_COMMANDS:
            raise ValueError(f"Unknown 1E command: 0x{cmd:02X}")

        # Check if standard 12-byte header format
        is_standard = False
        if len(data) >= 12 and (data[1] in (0xFF, 0x00) or not (data[1] in DEVICE_CODE_TO_NAME_1E)):
            if self._is_valid_device_code(data[8:10]):
                is_standard = True

        req = ParsedRequest()
        if is_standard:
            addr = struct.unpack_from("<I", data, 4)[0]
            dev_name = self._resolve_device_name(data[8:10])
            count = struct.unpack_from("<H", data, 10)[0]
            payload = data[12:]
        else:
            dev_code = data[1]
            dev_name = DEVICE_CODE_TO_NAME_1E.get(dev_code)
            if dev_name is None:
                raise DeviceSpecificationError(f"Unknown 1E device code: 0x{dev_code:02X}")
            addr = struct.unpack_from("<H", data, 2)[0]
            count = struct.unpack_from("<H", data, 4)[0]
            payload = data[6:]

        if cmd == CMD_WORD_READ:
            req.command = 0x0401
            req.subcommand = 0x0000
        elif cmd == CMD_BIT_READ:
            req.command = 0x0401
            req.subcommand = 0x0001
        elif cmd == CMD_WORD_WRITE:
            if len(payload) != count * 2:
                raise ValueError("Invalid 1E write frame length")
            req.command = 0x1401
            req.subcommand = 0x0000
            req.data = payload
        elif cmd == CMD_BIT_WRITE:
            expected_len = (count + 1) // 2 if count > 0 else 0
            if len(payload) != expected_len:
                raise ValueError("Invalid 1E write frame length")
            req.command = 0x1401
            req.subcommand = 0x0001
            req.data = payload

        req.devices.append({
            "type": dev_name,
            "address": addr,
            "count": count,
        })
        return req

    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        if parsed is not None:
            if parsed.command == 0x1401:
                subheader = 0x82 if parsed.subcommand == 0x0001 else 0x83
            else:
                subheader = 0x80 if parsed.subcommand == 0x0001 else 0x81
        else:
            subheader = 0x81

        if result.success:
            return bytes([subheader, 0x00]) + result.data
        else:
            end_code = (result.error_code & 0xFF) if (result.error_code & 0xFF) != 0 else 0x5B
            return bytes([subheader, end_code])
