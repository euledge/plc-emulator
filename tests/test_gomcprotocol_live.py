import asyncio
import subprocess
import pytest
from main import PLCEmulatorApp
from src.config import ConfigManager


@pytest.mark.asyncio
async def test_gomcprotocol_basic_read_live():
    # Use ephemeral port
    cfg = ConfigManager(port=0, transport="tcp")
    app = PLCEmulatorApp(config=cfg, web_port=0, web_host="127.0.0.1")

    # Set D100=100, D101=101, D102=102, D103=103, D104=104
    for i in range(5):
        app.device_manager.write_word("D", 100 + i, 100 + i)

    await app.start()
    try:
        plc_port = app.actual_plc_port
        go_code = f"""package main

import (
\t"fmt"
\tmc "github.com/moge800/gomcprotocol"
)

func main() {{
\tc, err := mc.New3EClient("127.0.0.1", {plc_port}, mc.ModeBinary)
\tif err != nil {{
\t\tpanic(err)
\t}}
\tif err := c.Connect(); err != nil {{
\t\tpanic(err)
\t}}
\tdefer c.Close()

\twords, err := c.ReadWords("D", 100, 5)
\tif err != nil {{
\t\tpanic(err)
\t}}
\tfor i, v := range words {{
\t\tfmt.Printf("D%d = %d\\n", 100+i, v)
\t}}
}}
"""
        from pathlib import Path
        runner_path = Path("C:/Users/hitos/Documents/workspace/gomcprotocol/examples/01_basic_read/runner.go")
        runner_path.write_text(go_code, encoding="utf-8")
        try:
            proc = await asyncio.create_subprocess_exec(
                "go", "run", "runner.go",
                cwd="C:/Users/hitos/Documents/workspace/gomcprotocol/examples/01_basic_read",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            assert proc.returncode == 0, f"Go error: {stderr.decode()}"
            out = stdout.decode()
            assert "D100 = 100" in out
            assert "D101 = 101" in out
            assert "D102 = 102" in out
            assert "D103 = 103" in out
            assert "D104 = 104" in out
        finally:
            if runner_path.exists():
                runner_path.unlink()
    finally:
        await app.stop()
