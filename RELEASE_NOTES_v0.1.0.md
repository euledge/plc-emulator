# Release v0.1.0 — "PLC Emulator"

Released: June 20, 2026

## 🎉 Highlights

This is the initial release of **PLCEmulator**, a full-featured PLC communication emulator supporting Mitsubishi MC protocol and SLMP.

- **MC Protocol 3E/1E/4E** + **SLMP** frame handling
- **Web UI** for real-time device monitoring and control
- **YAML Scripting** for automated device value simulation
- **113 tests** (97 unit + 16 E2E) ensuring reliability

## ✨ Features

### Core Protocol

- MC 3E, 1E, 4E frame parsing and response generation
- SLMP (Simplified SLMP) batch read/write support
- 10+ commands: batch read/write, loopback, remote RUN/STOP, monitor register/execute, CPU type read
- TCP and UDP servers with configurable ports
- Latency emulation with 5 modes (none, fixed, random, normal distribution, timeout)

### Device & PLC Models

- Word and bit device memory with thread-safe access
- Batch read/write operations
- Built-in PLC models: Q03UDE, R04CPU, FX5U with automatic range checking
- Change callbacks for real-time event notification

### Scripting Engine

- YAML-based DSL for simulation scenarios
- 4 script types: periodic, ramp, conditional, sequence
- Safe AST-based expression evaluator (no arbitrary code execution)
- Built-in functions: clamp, square, triangle, sawtooth
- Access to device values and runtime variables (t, dt, tick)

### Web UI

- Dark-themed interface with 4 panels: Settings, Device Monitor, Comm Log, Scripts
- Real-time device value monitoring via WebSocket
- Settings panel for protocol, transport, port, latency configuration
- Script editor with save/load/start/stop
- Communication log with direction indicators
- Internationalization (English / Japanese)

### Developer Experience

- uv-managed Python 3.12 project
- 97 unit tests + 16 Playwright E2E tests
- OpenAPI 3.1 specification
- GitHub Actions CI pipeline
- Bilingual documentation (English / Japanese)

## 🔒 Security

- AST-based expression evaluator blocks arbitrary code execution (no `__import__`, `eval`, attribute access)
- Thread-safe device memory access with fine-grained locking

## 📚 Documentation

- Bilingual README with quick-start guide and API reference
- OpenAPI 3.1 JSON spec (`docs/openapi.json`)
- Architecture Decision Records (5 ADRs)
- Implementation plan and requirements documentation

## 🙏 Contributors

- @euledge — All initial development

## 🚀 Quick Start

```bash
git clone https://github.com/euledge/plc-emulator.git
cd plc-emulator
uv sync
uv run uvicorn src.web.app:create_app --factory --reload
```

Then open http://localhost:8000 in your browser.

## 📦 Installation

```bash
uv sync
uv run pytest  # run all tests
```

## 🔗 Links

- [Repository](https://github.com/euledge/plc-emulator)
- [Changelog](CHANGELOG.md)
- [OpenAPI Spec](docs/openapi.json)
- [English README](README.md)
- [日本語 README](README.ja.md)

---

**Note:** This is an initial development release (0.x). Breaking changes may occur in minor versions until 1.0.0.
