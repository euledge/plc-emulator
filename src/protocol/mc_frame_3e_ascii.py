import struct
from src.protocol.base import ProtocolHandler, ParsedRequest, CommandResult
from src.protocol.constants import DeviceCode3E, ErrorCode, DEVICE_CODE_TO_NAME_3E
from src.device.device_manager import DeviceSpecificationError

DECIMAL_DEVICES = {"D", "M", "L", "F", "V", "S", "SM", "SD", "TN", "CN", "TS", "TC", "CS", "CC"}

KNOWN_3E_COMMANDS_ASCII = {
    "0401", "1401", "0403", "1402", "0101", "0619",
    "1001", "1002", "0801", "0802", "1630", "1631",
}


def parse_device_ascii(dev_str: str, addr_str: str) -> tuple[str, int]:
    clean_name = dev_str.strip("* ").upper()
    if clean_name in DeviceCode3E.__members__:
        dev_type = clean_name
    else:
        try:
            code = int(dev_str, 16)
            dev_type = DEVICE_CODE_TO_NAME_3E.get(code)
            if not dev_type:
                raise DeviceSpecificationError(f"Unknown device code: {dev_str}")
        except ValueError:
            raise DeviceSpecificationError(f"Unknown device name: {dev_str}")

    base = 10 if dev_type in DECIMAL_DEVICES else 16
    try:
        addr = int(addr_str, base)
    except ValueError:
        addr = int(addr_str, 16)
    return dev_type, addr


class McFrame3EAscii(ProtocolHandler):
    SUBHEADER_REQUEST = b"5000"
    SUBHEADER_RESPONSE = b"D000"

    def detect(self, data: bytes) -> bool:
        return len(data) >= 4 and data[:4].upper() == self.SUBHEADER_REQUEST

    def extract_frame(self, buf: bytearray) -> bytes | None:
        while len(buf) >= 4:
            if buf[:4].upper() == self.SUBHEADER_REQUEST:
                if len(buf) < 16:
                    return None

                total_len = None
                # Check for standard 10-char routing vs legacy 8-char routing
                if len(buf) >= 26:
                    cmd_10 = buf[22:26].decode("ascii", errors="ignore").upper()
                    cmd_8 = buf[20:24].decode("ascii", errors="ignore").upper()
                    if cmd_10 in KNOWN_3E_COMMANDS_ASCII:
                        try:
                            dlen = int(buf[14:18].decode("ascii"), 16)
                            total_len = 18 + dlen
                        except (ValueError, UnicodeDecodeError):
                            pass
                    elif cmd_8 in KNOWN_3E_COMMANDS_ASCII:
                        try:
                            dlen = int(buf[12:16].decode("ascii"), 16)
                            total_len = 16 + dlen
                        except (ValueError, UnicodeDecodeError):
                            pass

                if total_len is None:
                    # Fallback check based on length parsing
                    if len(buf) >= 18:
                        try:
                            dlen_10 = int(buf[14:18].decode("ascii"), 16)
                            if 4 <= dlen_10 <= len(buf) - 18:
                                total_len = 18 + dlen_10
                        except (ValueError, UnicodeDecodeError):
                            pass
                    if total_len is None and len(buf) >= 16:
                        try:
                            dlen_8 = int(buf[12:16].decode("ascii"), 16)
                            if 4 <= dlen_8 <= len(buf) - 16:
                                total_len = 16 + dlen_8
                        except (ValueError, UnicodeDecodeError):
                            pass

                if total_len is None:
                    if len(buf) < 18:
                        return None
                    del buf[0:1]
                    continue

                if len(buf) < total_len:
                    return None
                frame = bytes(buf[:total_len])
                del buf[:total_len]
                return frame
            else:
                del buf[0:1]
        return None

    def parse_request(self, data: bytes) -> ParsedRequest:
        if len(data) < 26:
            raise ValueError("Frame too short for 3E ASCII")

        try:
            text = data.decode("ascii")
        except UnicodeDecodeError as e:
            raise ValueError("Non-ASCII bytes in 3E ASCII frame") from e

        if text[:4].upper() != "5000":
            raise ValueError("Invalid 3E ASCII subheader")

        req = ParsedRequest()

        # Determine whether access path is standard 10-char (with Station No) or legacy 8-char
        cmd_10 = text[22:26].upper() if len(text) >= 26 else ""
        cmd_8 = text[20:24].upper() if len(text) >= 24 else ""

        is_standard_10 = False
        if cmd_10 in KNOWN_3E_COMMANDS_ASCII:
            is_standard_10 = True
        elif cmd_8 in KNOWN_3E_COMMANDS_ASCII:
            is_standard_10 = False
        else:
            try:
                if len(text) >= 18 and 18 + int(text[14:18], 16) == len(text):
                    is_standard_10 = True
            except ValueError:
                pass

        if is_standard_10:
            if len(data) < 30:
                raise ValueError("Frame too short for standard 3E ASCII")
            req.access_path = data[4:14]
            try:
                data_len = int(text[14:18], 16)
            except ValueError as e:
                raise ValueError("Invalid data length format") from e
            if len(data) != 18 + data_len:
                raise ValueError("Data length mismatch in 3E ASCII")
            try:
                req.command = int(text[22:26], 16)
                req.subcommand = int(text[26:30], 16)
            except ValueError as e:
                raise ValueError("Invalid command or subcommand format") from e
            cmd_payload = text[30:]
        else:
            if len(data) < 28:
                raise ValueError("Frame too short for 3E ASCII")
            req.access_path = data[4:12]
            try:
                data_len = int(text[12:16], 16)
            except ValueError as e:
                raise ValueError("Invalid data length format") from e
            if len(data) != 16 + data_len:
                raise ValueError("Data length mismatch in 3E ASCII")
            try:
                req.command = int(text[20:24], 16)
                req.subcommand = int(text[24:28], 16)
            except ValueError as e:
                raise ValueError("Invalid command or subcommand format") from e
            cmd_payload = text[28:]

        if req.command in (0x0401, 0x1401):
            if len(cmd_payload) < 12:
                raise ValueError("Payload too short for batch read/write in ASCII")
            dev_str = cmd_payload[:2]
            addr_str = cmd_payload[2:8]
            count_str = cmd_payload[8:12]

            dev_type, dev_addr = parse_device_ascii(dev_str, addr_str)
            count = int(count_str, 16)
            req.devices.append({
                "type": dev_type,
                "address": dev_addr,
                "count": count,
            })

            if req.command == 0x1401:
                val_text = cmd_payload[12:]
                is_bit = req.subcommand in (0x0001, 0x0003)
                if is_bit:
                    if len(val_text) != count:
                        raise ValueError("Data length mismatch for ASCII bit write")
                    # Convert to packed bits for execute_request
                    packed = bytearray()
                    for i in range(0, count, 2):
                        b0 = 1 if val_text[i] == "1" else 0
                        b1 = 1 if (i + 1 < count and val_text[i + 1] == "1") else 0
                        packed.append((b0 << 4) | (b1 & 0x0F))
                    req.data = bytes(packed)
                else:
                    if len(val_text) != count * 4:
                        raise ValueError("Data length mismatch for ASCII word write")
                    # Convert each 4-char hex word to LE bytes
                    vals = [int(val_text[i:i + 4], 16) for i in range(0, len(val_text), 4)]
                    req.data = struct.pack(f"<{len(vals)}H", *vals)
            else:
                req.data = b""
        elif req.command == 0x0101:
            req.data = b""
        else:
            req.data = cmd_payload.encode("ascii")

        return req

    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        if parsed and getattr(parsed, "access_path", None) and len(parsed.access_path) in (8, 10):
            access_path = parsed.access_path
        else:
            # Default to standard 10-char access path (Net 00, PC FF, Unit IO 03FF, Station 00)
            access_path = b"00FF03FF00"
        end_code = f"{result.error_code:04X}" if not result.success else "0000"

        val_text = ""
        if result.success and result.data:
            if parsed and parsed.subcommand in (0x0001, 0x0003):
                # Bit response: unpack nibbles into "1" and "0" chars up to requested count
                count = parsed.devices[0]["count"] if (parsed.devices and "count" in parsed.devices[0]) else len(result.data) * 2
                chars = []
                for i in range(count):
                    byte_val = result.data[i // 2]
                    bit = (byte_val >> 4) & 1 if (i % 2 == 0) else (byte_val & 1)
                    chars.append("1" if bit else "0")
                val_text = "".join(chars)
            elif parsed and parsed.command == 0x0101:
                # CPU type string
                val_text = result.data.decode("ascii", errors="replace").strip()
            else:
                # Word response: unpack 16-bit LE integers and format as 4-hex-char words
                num_words = len(result.data) // 2
                words = struct.unpack_from(f"<{num_words}H", result.data)
                val_text = "".join(f"{w:04X}" for w in words)

        resp_body = end_code + val_text
        data_len = f"{len(resp_body):04X}"

        return self.SUBHEADER_RESPONSE + access_path + data_len.encode("ascii") + resp_body.encode("ascii")
