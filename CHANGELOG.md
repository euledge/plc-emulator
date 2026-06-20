# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- MC protocol 3E/1E/4E frame parsing and response building
- SLMP handler with batch read/write
- Command processor supporting 10+ commands (batch R/W, loopback, remote RUN/STOP, monitor register/execute, CPU type read)
- TCP and UDP servers with configurable host/port
- Latency emulation (none, fixed, random, normal distribution, timeout simulation)
- Device memory manager with word/bit read/write, batch operations, range checking, and change callbacks
- PLC model definitions (Q03UDE, R04CPU, FX5U) with device range validation
- Scripting engine with YAML-based DSL supporting periodic, ramp, conditional, and sequence script types
- Safe AST-based expression evaluator with built-in functions (clamp, square, triangle, sawtooth) and device reference resolution
- Web UI built with FastAPI including settings panel, device monitor, communication log, and script editor
- WebSocket manager for real-time device value push
- Internationalization (English and Japanese) with JSON translation files
- State persistence via JSON save/load (POST /api/save, POST /api/load)
- OpenAPI 3.1 specification (`docs/openapi.json`)
- Sample YAML scripts in `scripts/examples/` (sawtooth, ramp loop, conditional)
- E2E tests with Playwright (16 tests covering navigation, settings, monitor, scripts, persistence, i18n)

### Infrastructure

- uv-managed Python 3.12 project with FastAPI, uvicorn, websockets, PyYAML
- pyproject.toml with keywords, classifiers, license, and project URLs for PyPI/GitHub
- MIT License
- GitHub Actions CI workflow (checkout@v6, setup-uv@v8.2.0, pytest + Playwright)
- `.gitignore` extended for IDE, OS, runtime artifacts
- Bilingual README (English, Japanese) with cross-links and badges

### Documentation

- Bilingual README with quick-start, API reference, and project structure
- OpenAPI 3.1 JSON specification
- Architecture Decision Records (ADR-001 through ADR-005)
- Implementation plan and requirements docs

[unreleased]: https://github.com/euledge/plc-emulator/compare/v0.1.0...HEAD
