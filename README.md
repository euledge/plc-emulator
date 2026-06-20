# PLCEmulator

[![CI](https://github.com/euledge/plc-emulator/actions/workflows/ci.yml/badge.svg)](https://github.com/euledge/plc-emulator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

PLC communication emulator supporting MC protocol / SLMP

[**日本語版はこちら**](README.ja.md)

> **GitHub topics 候補**: `plc`, `mc-protocol`, `slmp`, `mitsubishi`, `emulator`, `fastapi`, `plc-simulator`, `python`, `scada`, `industrial-automation`

## Features

- **MC Protocol** 3E/1E/4E frames + **SLMP**
- **TCP / UDP** servers
- **Device memory** read/write (bit, word, batch)
- **PLC models** (Q/L/FX) with range checking
- **Latency emulation** (none/fixed/random/normal/timeout)
- **Scripting** (YAML DSL + AST-safe evaluation)
  - Periodic write / Ramp / Conditional / Sequence
- **Web UI** (FastAPI + dark theme)
  - Settings panel / Device monitor / Comm log / Script editor
  - WebSocket real-time push / i18n (English, Japanese)
- **State persistence** JSON save/load
- **113 tests** (90 unit + 7 Web API + 5 persistence + 16 E2E)

## Quick Start

```bash
# Install
uv sync

# Run all tests
uv run pytest --ignore=tests/test_e2e.py

# Start server (http://localhost:8000)
uv run uvicorn src.web.app:create_app --factory --reload

# E2E tests (in another terminal, with server stopped)
uv run pytest tests/test_e2e.py --headed
```

## Project Structure

```
src/
  config.py              # Configuration management
  constants.py           # Constants
  device/
    device_manager.py    # Device memory manager
    plc_models.py        # PLC model definitions
  protocol/
    base.py              # Protocol base class
    device_parser.py     # Device number parser
    mc_frame_3e.py       # MC 3E frame
    mc_frame_1e.py       # MC 1E frame
    mc_frame_4e.py       # MC 4E frame
    slmp_handler.py      # SLMP handler
    command_processor.py # Command processor
  server/
    tcp_server.py        # TCP server
    udp_server.py        # UDP server
    latency.py           # Latency emulator
  scripting/
    builtins.py          # Built-in functions
    evaluator.py         # AST evaluator
    parser.py            # YAML parser
    engine.py            # Script execution engine
  web/
    app.py               # FastAPI application
    api_routes.py        # API routes
    websocket_handler.py # WebSocket manager
  i18n/
    i18n.py              # Translation loader
    ja.json / en.json    # Translation data
  persistence/
    persistence_manager.py # JSON save/load
static/
  index.html             # Web UI
  css/style.css
  js/                    # Frontend JavaScript
scripts/examples/        # Sample scripts
tests/                   # Tests
```

## OpenAPI

Full OpenAPI 3.1 specification: [`docs/openapi.json`](docs/openapi.json)
(14 endpoints, 7 schemas)

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/config` | Get configuration |
| PUT | `/api/config` | Update configuration |
| GET | `/api/devices/{type}` | Batch read devices |
| PUT | `/api/devices/{type}/{addr}` | Write device |
| GET | `/api/latency/stats` | Latency statistics |
| PUT | `/api/latency/config` | Latency configuration |
| GET | `/api/scripts` | List scripts |
| GET | `/api/scripts/{name}` | Get script content |
| PUT | `/api/scripts/{name}` | Save script |
| POST | `/api/scripts/{name}/start` | Start script |
| POST | `/api/scripts/{name}/stop` | Stop script |
| POST | `/api/save` | Save device state |
| POST | `/api/load` | Load device state |
| GET | `/api/i18n/{lang}` | Translation data |
| WS | `/ws` | WebSocket |

## Sample Scripts

```yaml
# Periodic write (sawtooth into D100)
- type: periodic
  interval_ms: 1000
  actions:
    - target: D100
      expr: "t % 1000"

# Ramp (D200 from 0→1000 in 10s, looped)
- type: ramp
  target: D200
  start_value: 0
  end_value: 1000
  duration_ms: 10000
  loop: true

# Conditional (M0 ON when D100 > 500)
- type: conditional
  interval_ms: 200
  conditions:
    - when: "D100 > 500"
      actions:
        - target: M0
          value: 1
    - when: "D100 <= 500"
      actions:
        - target: M0
          value: 0
```

## License

MIT
