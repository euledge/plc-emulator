"""slmp-connect-python (dev-only) を使ったプロトコル x 読出し命令のマトリクス検証。"""
import pytest
from slmp import AsyncSlmpClient
from main import PLCEmulatorApp
from src.config import ConfigManager

# (plc_profile, エミュレータ側プロトコル設定)
# melsec:qnu / melsec:iq-f -> 3Eフレーム, melsec:iq-r -> 4Eフレーム
PROFILES = [
    pytest.param("melsec:qnu", "3E", id="3E"),
    pytest.param("melsec:iq-r", "4E", id="4E"),
    pytest.param("melsec:iq-f", "SLMP", id="SLMP-3Eframe"),
    pytest.param("melsec:iq-r", "SLMP", id="SLMP-4Eframe"),
]


async def _start(protocol):
    cfg = ConfigManager(port=0, transport="tcp", protocol=protocol)
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    for i in range(6):
        app.device_manager.write_word("D", 100 + i, 100 + i)
    app.device_manager.write_bit("M", 0, True)
    app.device_manager.write_bit("M", 1, False)
    app.device_manager.write_bit("M", 2, True)
    await app.start()
    return app


async def _client(app, profile):
    c = AsyncSlmpClient("127.0.0.1", app.actual_plc_port, plc_profile=profile, timeout=2.0)
    await c.connect()
    return c


@pytest.mark.asyncio
@pytest.mark.parametrize("profile,protocol", PROFILES)
async def test_single_word_read(profile, protocol):
    app = await _start(protocol)
    try:
        c = await _client(app, profile)
        try:
            assert await c.read_devices("D103", 1) == [103]
        finally:
            await c.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("profile,protocol", PROFILES)
async def test_bulk_word_read(profile, protocol):
    app = await _start(protocol)
    try:
        c = await _client(app, profile)
        try:
            assert await c.read_devices("D100", 6) == [100, 101, 102, 103, 104, 105]
        finally:
            await c.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("profile,protocol", PROFILES)
async def test_bulk_bit_read(profile, protocol):
    app = await _start(protocol)
    try:
        c = await _client(app, profile)
        try:
            assert await c.read_devices("M0", 3, bit_unit=True) == [True, False, True]
        finally:
            await c.close()
    finally:
        await app.stop()
@pytest.mark.asyncio
@pytest.mark.parametrize("profile,protocol", PROFILES)
async def test_single_bit_read(profile, protocol):
    app = await _start(protocol)
    try:
        c = await _client(app, profile)
        try:
            assert await c.read_devices("M0", 1, bit_unit=True) == [True]
        finally:
            await c.close()
    finally:
        await app.stop()



@pytest.mark.asyncio
@pytest.mark.parametrize("profile,protocol", PROFILES)
async def test_random_read(profile, protocol):
    app = await _start(protocol)
    try:
        c = await _client(app, profile)
        try:
            r = await c.read_random(word_devices=["D100", "D105", "D102"])
            values = [r.word[k] if hasattr(r, "word") and isinstance(r.word, dict) else None for k in ()]
            flat = getattr(r, "word_values", None) or getattr(r, "words", None) or r
            assert 100 in _flatten(flat) and 105 in _flatten(flat) and 102 in _flatten(flat)
        finally:
            await c.close()
    finally:
        await app.stop()


def _flatten(obj):
    if isinstance(obj, dict):
        return list(obj.values())
    if hasattr(obj, "__dict__"):
        out = []
        for v in vars(obj).values():
            out.extend(_flatten(v))
        return out
    if isinstance(obj, (list, tuple)):
        out = []
        for v in obj:
            out.extend(_flatten(v))
        return out
    return [obj]
