import asyncio
import struct
import pytest
from src.device.device_definition import (
    HEX_DEVICES,
    is_hex_device,
    parse_device_address,
    format_device_address,
)
from src.device.device_manager import DeviceManager
from src.scripting.engine import ScriptEngine
from src.scripting.parser import ScriptParser
from src.protocol.constants import DeviceCode3E


def test_is_hex_device():
    assert is_hex_device("W") is True
    assert is_hex_device("w") is True
    assert is_hex_device("X") is True
    assert is_hex_device("Y") is True
    assert is_hex_device("B") is True
    assert is_hex_device("SW") is True
    assert is_hex_device("SB") is True

    assert is_hex_device("D") is False
    assert is_hex_device("M") is False
    assert is_hex_device("L") is False
    assert is_hex_device("R") is False
    assert is_hex_device("ZR") is False


def test_parse_device_address_hex():
    assert parse_device_address("W100") == ("W", 0x100)
    assert parse_device_address("w0100") == ("W", 0x100)
    assert parse_device_address("X1F") == ("X", 0x1F)
    assert parse_device_address("x0") == ("X", 0)
    assert parse_device_address("Y2A") == ("Y", 0x2A)
    assert parse_device_address("B0FF") == ("B", 0xFF)
    assert parse_device_address("SW10") == ("SW", 0x10)


def test_parse_device_address_dec():
    assert parse_device_address("D100") == ("D", 100)
    assert parse_device_address("d0") == ("D", 0)
    assert parse_device_address("M8191") == ("M", 8191)
    assert parse_device_address("L50") == ("L", 50)
    assert parse_device_address("R1000") == ("R", 1000)

    # Decimal devices with hex letters should raise ValueError
    with pytest.raises(ValueError, match="Decimal device"):
        parse_device_address("D1F")
    with pytest.raises(ValueError, match="Decimal device"):
        parse_device_address("M2A")


def test_format_device_address():
    assert format_device_address("W", 0x100) == "0100"
    assert format_device_address("SW", 0x1A) == "001A"
    assert format_device_address("X", 0x1F) == "1F"
    assert format_device_address("Y", 0x0) == "0"
    assert format_device_address("B", 0x2A) == "2A"

    assert format_device_address("D", 100) == "100"
    assert format_device_address("M", 50) == "50"


def test_script_parser_hex_devices():
    # Valid script with HEX addresses
    yaml_valid = """
scripts:
  - name: test_hex
    type: sequence
    loop: false
    steps:
      - wait_ms: 0
        actions:
          - target: W100
            value: 1234
          - target: X1F
            value: 1
          - target: B2A
            value: 0
"""
    valid, errors = ScriptParser.validate_content(yaml_valid)
    assert valid is True
    assert errors == []

    # Invalid script with hex in DEC device
    yaml_invalid = """
scripts:
  - name: test_invalid_dec
    type: sequence
    loop: false
    steps:
      - wait_ms: 0
        actions:
          - target: D1F
            value: 1234
"""
    valid, errors = ScriptParser.validate_content(yaml_invalid)
    assert valid is False
    assert any("Decimal device D cannot have hexadecimal letters" in e for e in errors)


@pytest.mark.asyncio
async def test_script_engine_hex_device_execution():
    dm = DeviceManager()
    engine = ScriptEngine(device_manager=dm)

    script = {
        "name": "test_hex_exec",
        "type": "sequence",
        "loop": False,
        "steps": [
            {
                "wait_ms": 0,
                "actions": [
                    {"target": "W100", "value": 0xBEEF},
                    {"target": "X1F", "value": 1},
                    {"target": "B2A", "value": 1},
                ],
            }
        ],
    }

    engine.load_scripts([script])
    await engine.start()
    await asyncio.sleep(0.05)
    await engine.stop()

    # W100 is 0x100 = 256
    assert dm.read_word("W", 0x100) == 0xBEEF
    # X1F is 0x1F = 31
    assert dm.read_bit("X", 0x1F) is True
    # B2A is 0x2A = 42
    assert dm.read_bit("B", 0x2A) is True


@pytest.mark.asyncio
async def test_script_and_mc_protocol_hex_address_consistency():
    """Verify that a script writing to W100 writes to the exact same physical address that MC 3E reads for W100."""
    from src.protocol.mc_frame_3e import McFrame3E
    from src.protocol.command_processor import CommandProcessor

    dm = DeviceManager()
    engine = ScriptEngine(device_manager=dm)
    processor = CommandProcessor(dm)
    handler = McFrame3E()

    # 1. Script writes to W100
    script = {
        "name": "write_w100",
        "type": "sequence",
        "loop": False,
        "steps": [
            {
                "wait_ms": 0,
                "actions": [
                    {"target": "W100", "value": 0x1234},
                ],
            }
        ],
    }
    engine.load_scripts([script])
    await engine.start()
    await asyncio.sleep(0.05)
    await engine.stop()

    # 2. Build MC 3E binary request to read 1 word from W100 (addr = 0x100, code = DeviceCode3E.W)
    # Header: 3E subheader 0x5000, net=0, plc=255, io=0x03FF, station=0, timer=0x0010, command=0x0401, sub=0x0000
    # Device: addr=0x000100 (3 bytes little-endian), code=0xB4 (1 byte), count=1 (2 bytes)
    cmd_data = struct.pack("<HH", 0x0401, 0x0000)
    dev_spec = struct.pack("<I", 0x100)[:3] + bytes([DeviceCode3E.W])
    dev_data = dev_spec + struct.pack("<H", 1)
    req_body = cmd_data + dev_data
    timer = b"\x10\x00"
    data_len = len(timer) + len(req_body)
    header = b"\x50\x00\x00\xFF\xFF\x03\x00" + struct.pack("<H", data_len) + timer
    frame = header + req_body

    req = handler.parse_request(frame)
    result = processor.execute_request(req)
    assert result.success is True
    assert result.data == b"\x34\x12"
    assert struct.unpack("<H", result.data)[0] == 0x1234
