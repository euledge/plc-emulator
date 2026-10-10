import pytest
from slmp import AsyncSlmpClient
from main import PLCEmulatorApp
from src.config import ConfigManager


@pytest.mark.asyncio
async def test_slmp_connect_python_read_words_qnu():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")

    # Set D100=100, D101=101, D102=102, D103=103, D104=104
    for i in range(5):
        app.device_manager.write_word("D", 100 + i, 100 + i)

    await app.start()
    try:
        plc_port = app.actual_plc_port
        client = AsyncSlmpClient("127.0.0.1", plc_port, plc_profile="melsec:qnu")
        try:
            await client.connect()
            vals = await client.read_devices("D100", 5)
            assert vals == [100, 101, 102, 103, 104]

            # Verify communication log
            logs = list(app.state.comm_logs)
            assert len(logs) == 2
            assert "Batch Read (0401)" in logs[0]["command"]
            assert logs[0]["direction"] == "rx"
            assert "50 00 00 FF FF 03 00" in logs[0]["data"]
        finally:
            await client.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_slmp_connect_python_read_words_iqf():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")

    for i in range(5):
        app.device_manager.write_word("D", 200 + i, 200 + i)

    await app.start()
    try:
        plc_port = app.actual_plc_port
        client = AsyncSlmpClient("127.0.0.1", plc_port, plc_profile="melsec:iq-f")
        try:
            await client.connect()
            vals = await client.read_devices("D200", 5)
            assert vals == [200, 201, 202, 203, 204]
        finally:
            await client.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_slmp_connect_python_write_and_read_words():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")

    await app.start()
    try:
        plc_port = app.actual_plc_port
        client = AsyncSlmpClient("127.0.0.1", plc_port, plc_profile="melsec:qnu")
        try:
            await client.connect()
            await client.write_devices("D300", [111, 222, 333])
            vals = await client.read_devices("D300", 3)
            assert vals == [111, 222, 333]
            assert app.device_manager.read_word("D", 300) == 111
            assert app.device_manager.read_word("D", 301) == 222
            assert app.device_manager.read_word("D", 302) == 333
        finally:
            await client.close()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_slmp_connect_python_read_write_bits():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")

    await app.start()
    try:
        plc_port = app.actual_plc_port
        client = AsyncSlmpClient("127.0.0.1", plc_port, plc_profile="melsec:qnu")
        try:
            await client.connect()
            await client.write_devices("M0", [True, False, True], bit_unit=True)
            vals = await client.read_devices("M0", 3, bit_unit=True)
            assert vals == [True, False, True]
            assert app.device_manager.read_bit("M", 0) is True
            assert app.device_manager.read_bit("M", 1) is False
            assert app.device_manager.read_bit("M", 2) is True
        finally:
            await client.close()
    finally:
        await app.stop()
