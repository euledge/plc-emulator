from src.protocol.device_parser import (
    parse_device_mc,
    parse_device_slmp,
    encode_device_mc,
    encode_device_slmp,
)


def test_parse_device_mc_d():
    code, addr = parse_device_mc(b"\xA8\x64\x00\x00")
    assert code == "D"
    assert addr == 100


def test_parse_device_mc_m():
    code, addr = parse_device_mc(b"\x90\x00\x00\x00")
    assert code == "M"
    assert addr == 0


def test_parse_device_mc_x():
    code, addr = parse_device_mc(b"\x9C\x00\x00\x00")
    assert code == "X"
    assert addr == 0


def test_parse_device_slmp_d():
    code, addr = parse_device_slmp(b"\x64\x00\x00\x00\xA8\x00")
    assert code == "D"
    assert addr == 100


def test_encode_device_mc_d():
    data = encode_device_mc("D", 100)
    assert data == b"\xA8\x64\x00\x00"


def test_encode_device_mc_m():
    data = encode_device_mc("M", 0)
    assert data == b"\x90\x00\x00\x00"


def test_encode_device_slmp_d():
    data = encode_device_slmp("D", 100)
    assert data == b"\x64\x00\x00\x00\xA8\x00"
