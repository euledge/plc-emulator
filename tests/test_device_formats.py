import asyncio
import struct
import pytest
from src.device.device_manager import DeviceManager


def format_val_python(val, fmt, high_word=0):
    num = val & 0xFFFF
    if fmt in ("DEC", "DEC_UNSIGNED"):
        return str(num)
    if fmt == "DEC_SIGNED":
        s16 = num - 0x10000 if num >= 0x8000 else num
        return str(s16)
    if fmt == "HEX":
        return "0x" + f"{num:04X}"
    if fmt == "BIN":
        return "0b" + f"{num:016b}"
    if fmt == "ASCII":
        b0 = num & 0xFF
        b1 = (num >> 8) & 0xFF
        c0 = chr(b0) if 32 <= b0 <= 126 else "."
        c1 = chr(b1) if 32 <= b1 <= 126 else "."
        return f"'{c0}{c1}'"
    if fmt == "FLOAT":
        buf = struct.pack("<HH", num, high_word & 0xFFFF)
        f = struct.unpack("<f", buf)[0]
        return f"{f:.1f}" if f.is_integer() else f"{f:.7g}"
    return str(val)


def test_format_conversions_signed_and_unsigned():
    # Value 65535 (0xFFFF)
    assert format_val_python(65535, "DEC") == "65535"
    assert format_val_python(65535, "DEC_SIGNED") == "-1"
    assert format_val_python(65535, "HEX") == "0xFFFF"
    assert format_val_python(65535, "BIN") == "0b1111111111111111"

    # Value 32768 (0x8000)
    assert format_val_python(32768, "DEC") == "32768"
    assert format_val_python(32768, "DEC_SIGNED") == "-32768"
    assert format_val_python(32768, "HEX") == "0x8000"

    # Value 0
    assert format_val_python(0, "DEC") == "0"
    assert format_val_python(0, "DEC_SIGNED") == "0"


def test_float_32bit_two_consecutive_words():
    # Float 12.5 in IEEE 754: 0x41480000
    # Little-endian: low word = 0x0000, high word = 0x4148
    low = 0x0000
    high = 0x4148
    formatted = format_val_python(low, "FLOAT", high_word=high)
    assert formatted == "12.5"

    # Float -1.0: 0xBF800000
    formatted_neg = format_val_python(0x0000, "FLOAT", high_word=0xBF80)
    assert formatted_neg == "-1.0"


def test_ascii_characters_two_bytes_per_word():
    # Low byte 'A' (0x41), High byte 'B' (0x42) -> 0x4241
    val = (ord("A") & 0xFF) | ((ord("B") & 0xFF) << 8)
    formatted = format_val_python(val, "ASCII")
    assert formatted == "'AB'"

    # Non-printable characters shown as '.'
    non_print = 0x0000
    assert format_val_python(non_print, "ASCII") == "'..'"
