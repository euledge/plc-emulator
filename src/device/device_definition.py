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


def get_device_type(code: str) -> DeviceType | None:
    return DEVICE_TYPE_MAP.get(code.upper())
