import struct
from src.protocol.mc_frame_3e import McFrame3E
from src.protocol.base import ParsedRequest, CommandResult
from src.protocol.device_parser import parse_device_slmp


SLMP_SUBCOMMANDS = {0x0002, 0x0003}


class SlmpHandler(McFrame3E):
    def detect(self, data: bytes) -> bool:
        if len(data) < 14:
            return False
        if data[:2] != self.SUBHEADER_REQUEST:
            return False
        subcommand = struct.unpack_from("<H", data, 12)[0]
        return subcommand in SLMP_SUBCOMMANDS

    def parse_request(self, data: bytes) -> ParsedRequest:
        if len(data) < 12:
            raise ValueError("Frame too short for SLMP")
        req = ParsedRequest()
        data_len = struct.unpack_from("<H", data, 6)[0]
        cmd_data = data[10:10 + data_len - 2]
        req.command = struct.unpack_from("<H", cmd_data, 0)[0]
        req.subcommand = struct.unpack_from("<H", cmd_data, 2)[0]

        if req.command in (0x0401, 0x1401):
            dev_type, dev_addr = parse_device_slmp(cmd_data[4:10])
            count = struct.unpack_from("<H", cmd_data, 10)[0]
            req.devices.append({
                "type": dev_type,
                "address": dev_addr,
                "count": count,
            })
            if req.command == 0x1401:
                req.data = cmd_data[12:12 + count * 2]

        return req

    def build_response(self, parsed: ParsedRequest | None, result: CommandResult) -> bytes:
        return super().build_response(parsed, result)
