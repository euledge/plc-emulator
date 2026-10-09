from src.protocol.base import ProtocolHandler, ParsedRequest, CommandResult
from src.protocol.mc_frame_1e import McFrame1E
from src.protocol.mc_frame_3e import McFrame3E
from src.protocol.mc_frame_4e import McFrame4E
from src.protocol.slmp_handler import SlmpHandler


def create_protocol_handler(protocol: str, data_format: str = "binary") -> ProtocolHandler:
    p = protocol.upper()
    fmt = data_format.lower() if data_format else "binary"
    if p == "3E":
        if fmt == "ascii":
            from src.protocol.mc_frame_3e_ascii import McFrame3EAscii
            return McFrame3EAscii()
        return McFrame3E()
    elif p == "1E":
        return McFrame1E()
    elif p == "4E":
        return McFrame4E()
    elif p == "SLMP":
        return SlmpHandler()
    raise ValueError(f"Unsupported protocol: {protocol}")
