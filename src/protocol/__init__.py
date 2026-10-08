from src.protocol.base import ProtocolHandler, ParsedRequest, CommandResult
from src.protocol.mc_frame_1e import McFrame1E
from src.protocol.mc_frame_3e import McFrame3E
from src.protocol.mc_frame_4e import McFrame4E
from src.protocol.slmp_handler import SlmpHandler


def create_protocol_handler(protocol: str) -> ProtocolHandler:
    p = protocol.upper()
    if p == "1E":
        return McFrame1E()
    elif p == "3E":
        return McFrame3E()
    elif p == "4E":
        return McFrame4E()
    elif p == "SLMP":
        return SlmpHandler()
    raise ValueError(f"Unsupported protocol: {protocol}")
