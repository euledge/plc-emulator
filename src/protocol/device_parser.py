import struct
from src.protocol.constants import DEVICE_CODE_TO_NAME_3E, DEVICE_NAME_TO_CODE_3E


def parse_device_mc(data: bytes) -> tuple[str, int]:
    if len(data) < 4:
        raise ValueError("MC device data too short")
    code = data[0]
    addr = data[1] | (data[2] << 8) | (data[3] << 16)
    device_name = DEVICE_CODE_TO_NAME_3E.get(code)
    if device_name is None:
        raise ValueError(f"Unknown device code: 0x{code:02X}")
    return device_name, addr


def parse_device_slmp(data: bytes) -> tuple[str, int]:
    if len(data) < 6:
        raise ValueError("SLMP device data too short")
    addr = struct.unpack_from("<I", data, 0)[0]
    code = struct.unpack_from("<H", data, 4)[0]
    device_name = DEVICE_CODE_TO_NAME_3E.get(code)
    if device_name is None:
        raise ValueError(f"Unknown device code: 0x{code:04X}")
    return device_name, addr


def encode_device_mc(device_type: str, address: int) -> bytes:
    code = DEVICE_NAME_TO_CODE_3E.get(device_type.upper())
    if code is None:
        raise ValueError(f"Unknown device type: {device_type}")
    return struct.pack("<BI", code, address)[:4]


def encode_device_slmp(device_type: str, address: int) -> bytes:
    code = DEVICE_NAME_TO_CODE_3E.get(device_type.upper())
    if code is None:
        raise ValueError(f"Unknown device type: {device_type}")
    return struct.pack("<IH", address, code)
