import asyncio
import struct
import pytest
from main import PLCEmulatorApp
from src.config import ConfigManager
from src.scripting.evaluator import SafeEvaluator
from src.device.device_manager import DeviceManager
from src.protocol.constants import DeviceCode3E


def make_3e_req(command: int, subcommand: int, dev_code: int, addr: int, count: int, payload: bytes = b"") -> bytes:
    dev_bytes = bytes([dev_code, addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF])
    cmd_data = struct.pack("<HH", command, subcommand) + dev_bytes + struct.pack("<H", count) + payload
    timer = b"\x00\x00"
    data_len = len(timer) + len(cmd_data)
    header = b"\x50\x00\x00\x00\x00\x00" + struct.pack("<H", data_len) + timer
    return header + cmd_data


def test_heavy_expression_raises_timeout_error():
    dm = DeviceManager()
    evaluator = SafeEvaluator(device_manager=dm, timeout=0.01)

    # Normal expressions evaluate accurately
    assert evaluator.evaluate("1 + 2 * 3") == 7
    assert evaluator.evaluate("clamp(10, 0, 5)") == 5

    # 1. Huge exponent raises TimeoutError
    with pytest.raises(TimeoutError):
        evaluator.evaluate("2 ** 999999")

    # 2. Overly deep / complex AST raises TimeoutError
    deep_expr = " + ".join(["1"] * 600)
    with pytest.raises(TimeoutError):
        evaluator.evaluate(deep_expr)


@pytest.mark.asyncio
async def test_script_engine_handles_timeout_gracefully():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    app.device_manager.write_word("D", 100, 42)

    # Script has an action with a heavy expression that times out
    script = [{
        "name": "timeout_script",
        "type": "periodic",
        "interval_ms": 20,
        "actions": [
            {"target": "D100", "expr": "2 ** 999999"}
        ]
    }]

    from src.scripting.engine import ScriptEngine
    engine = ScriptEngine(app.device_manager)
    engine.load_scripts(script)
    await engine.start()
    try:
        # Wait a few cycles
        await asyncio.sleep(0.1)
        # Script engine didn't crash, and D100 was not corrupted
        assert engine.running is True
        assert app.device_manager.read_word("D", 100) == 42
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_plc_server_communication_remains_responsive_during_heavy_expressions():
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")
    await app.start()
    try:
        plc_port = app.actual_plc_port

        # Start a script that attempts heavy expressions
        script = [{
            "name": "heavy_script",
            "type": "periodic",
            "interval_ms": 10,
            "actions": [
                {"target": "D10", "expr": "2 ** 999999"}
            ]
        }]
        from src.scripting.engine import ScriptEngine
        engine = ScriptEngine(app.device_manager)
        engine.load_scripts(script)
        await engine.start()

        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", plc_port)
            try:
                # PLC socket communication must respond promptly (< 50ms) without getting blocked
                req = make_3e_req(0x1401, 0x0000, DeviceCode3E.D, 50, 1, struct.pack("<H", 999))
                writer.write(req)
                await writer.drain()
                resp = await asyncio.wait_for(reader.readexactly(10), timeout=0.5)
                assert struct.unpack_from("<H", resp, 8)[0] == 0x0000
                assert app.device_manager.read_word("D", 50) == 999
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            await engine.stop()
    finally:
        await app.stop()
