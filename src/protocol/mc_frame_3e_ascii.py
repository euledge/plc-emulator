import struct
from src.protocol.base import ProtocolHandler, ParsedRequest, CommandResult
from src.protocol.constants import DeviceCode3E, ErrorCode, DEVICE_CODE_TO_NAME_3E

DECIMAL_DEVICES = {"D", "M", "L", "F", "V", "S", "SM", "SD", "TN", "CN", "TS", "TC", "CS", "CC"}


def parse_device_ascii(dev_str: str, addr_str: str) -> tuple[str, int]:
    clean_name = dev_str.strip("* ").upper()
    if clean_name in DeviceCode3E.__members__:
        dev_type = clean_name
    else:
        try:
            code = int(dev_str, 16)
            dev_type = DEVICE_CODE_TO_NAME_3E.get(code)
            if not dev_type:
                raise ValueError(f"Unknown device code: {dev_str}")
        except ValueError:
            raise ValueError(f"Unknown device name: {dev_str}")

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
                try:
                    data_len = int(buf[12:16].decode("ascii"), 16)
                except (ValueError, UnicodeDecodeError):
                    del buf[0:1]
                    continue
                total_len = 16 + data_len
                if len(buf) < total_len:
                    return None
                frame = bytes(buf[:total_len])
                del buf[:total_len]
                return frame
            else:
                del buf[0:1]
        return None

    def parse_request(self, data: bytes) -> ParsedRequest:
        if len(data) < 28:
            raise ValueError("Frame too short for 3E ASCII")

        try:
            text = data.decode("ascii")
        except UnicodeDecodeError as e:
            raise ValueError("Non-ASCII bytes in 3E ASCII frame") from e

        if text[:4].upper() != "5000":
            raise ValueError("Invalid 3E ASCII subheader")

        req = ParsedRequest()
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
        access_path = parsed.access_path if parsed and len(parsed.access_path) == 8 else b"00000000"
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
