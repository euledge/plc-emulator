from enum import Enum


class DeviceType(Enum):
    WORD = "word"
    BIT = "bit"


DEVICE_TYPE_MAP: dict[str, DeviceType] = {
    "D": DeviceType.WORD,
    "W": DeviceType.WORD,
    "R": DeviceType.WORD,
    "ZR": DeviceType.WORD,
    "SD": DeviceType.WORD,
    "SW": DeviceType.WORD,
    "TN": DeviceType.WORD,
    "CN": DeviceType.WORD,
    "X": DeviceType.BIT,
    "Y": DeviceType.BIT,
    "M": DeviceType.BIT,
    "L": DeviceType.BIT,
    "F": DeviceType.BIT,
    "V": DeviceType.BIT,
    "B": DeviceType.BIT,
    "SM": DeviceType.BIT,
    "SB": DeviceType.BIT,
    "S": DeviceType.BIT,
    "TS": DeviceType.BIT,
    "TC": DeviceType.BIT,
    "CS": DeviceType.BIT,
    "CC": DeviceType.BIT,
}


import re

HEX_DEVICES: set[str] = {"X", "Y", "B", "W", "SB", "SW"}


def is_hex_device(code: str) -> bool:
    return code.upper() in HEX_DEVICES


def get_device_type(code: str) -> DeviceType | None:
    return DEVICE_TYPE_MAP.get(code.upper())


def parse_device_address(target: str) -> tuple[str, int]:
    """Parse a device string like 'D100', 'W100', 'X1F' into (device_code, address_int).

    HEX devices (W, X, Y, B, SB, SW) parse address in base 16.
    DEC devices (D, M, L, R, ZR, etc.) parse address in base 10.
    Raises ValueError on syntax or radix mismatch.
    """
    m = re.match(r"^([A-Za-z]+)([0-9A-Fa-f]+)$", target.strip())
    if not m:
        raise ValueError(f"Invalid device address format: '{target}'")
    dev_type = m.group(1).upper()
    addr_str = m.group(2)
    if is_hex_device(dev_type):
        try:
            addr = int(addr_str, 16)
        except ValueError:
            raise ValueError(f"Invalid hexadecimal address for device {dev_type}: '{addr_str}'")
    else:
        if not addr_str.isdigit():
            raise ValueError(f"Decimal device {dev_type} cannot have hexadecimal letters in address: '{addr_str}'")
        addr = int(addr_str, 10)
    return dev_type, addr


def format_device_address(dev_type: str, address: int) -> str:
    """Format address for display: hex for HEX devices, dec for DEC devices."""
    if is_hex_device(dev_type):
        return f"{address:04X}" if dev_type.upper() in ("W", "SW") else f"{address:X}"
    return str(address)
