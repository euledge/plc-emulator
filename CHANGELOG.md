# Changelog

All notable changes to PLCEmulator, tracked by release date.

## October 10, 2026 — v1.0.0

### ✨ New

- **Multi-Protocol Communication** — Added support for MC Protocol 3E (Binary & ASCII), 1E, 4E (with serial number echo-back), and SLMP with runtime subheader auto-detection on a single port (#5, #7, #8, #9, #12, #13, #15).
- **Advanced Command Coverage** — Implemented random read/write (0403/1402), bit-level subcommands (0001/0003), monitor register/execute (0801/0802), remote RUN/STOP (1001/1002), and remote password authentication (1630/1631) (#6, #10, #11, #12, #27).
- **Enhanced Device Monitor** — Added "ALL" tab for simultaneous multi-device viewing, "Points" batch address addition, 6 display formats (DEC, DEC Signed, HEX, BIN, FLOAT, ASCII), inline value editing, and "Clear All" with memory reset (#16, #19, #21, #22, #58, #60).
- **Communication Log Improvements** — Added parsed command badges (e.g. `[Batch Read (0401)]`), automatic password payload masking (`**`), and one-click plain text log download (#7, #23, #24, #27).
- **Script Editor Upgrades** — Added syntax highlighting and line numbers for YAML, pre-packaged industrial scenario loading, AST sandbox safety validation, and complete Script DSL documentation (#8, #17, #18, #25, #26, #28).
- **Latency & Fault Simulation** — Added real-time latency statistics panel and error response suppression toggle (#15, #20).
- **Illustrated Documentation** — Added screenshot-backed User Manual in Japanese and English (`docs/user_manual.ja.md`, `docs/user_manual.md`).

### ⚡ Improved

- Dynamic runtime configuration updates without disconnecting active clients when settings are unchanged (#4).
- Strict conformance to official MELSEC error codes (`0xC050`, `0xC051`, `0xC056`, `0xC058`, `0xC059`, `0xC05B`, `0xC061`, `0x4A01`, `0x4A03`) (#14, #27).
- Port isolation using ephemeral ports (`port=0`) in test suites, avoiding collisions with active running instances.
- Automated CI test pipeline with full Playwright E2E coverage across 232 test cases.

### 🐛 Fixed

- Fixed device monitor overwriting previously registered devices when adding new ones (#58).
- Fixed "Clear All" button failing to remove rows from the device monitor table (#60).
- Enforced 1-client exclusive TCP connection policy (#9).
- Handled graceful PLC server shutdown upon unexpected web server termination (#3).

## June 20, 2026 — v0.1.0

### ✨ New

- **PLC Communication Server** — You can now run a fully functional PLC emulator that speaks MC Protocol (3E, 1E, 4E) and SLMP over TCP or UDP. Connect any HMI, SCADA, or test tool and get real PLC responses without physical hardware.

- **Device Memory Simulator** — You can now read and write thousands of virtual devices (D, W, M, X, Y, L, B, R, ZR) with bit and word access. Device ranges are automatically validated against built-in PLC models (Q03UDE, R04CPU, FX5U).

- **Web Dashboard** — You can now monitor and control the emulator from any browser. The dark-themed UI gives you four panels:
  - **Settings** — Change protocol, transport, port, latency behavior on the fly
  - **Device Monitor** — Watch device values update in real time via WebSocket
  - **Comm Log** — Inspect every packet the server sends and receives
  - **Script Editor** — Write and run YAML scripts to simulate device behavior

- **Scripting Engine** — You can now automate device value changes with simple YAML scripts. Four script types cover common simulation needs:
  - **Periodic** — Write values on a timer (e.g., sawtooth wave into D100 every second)
  - **Ramp** — Sweep a value between two endpoints over a duration (e.g., D200 from 0→1000 in 10s)
  - **Conditional** — Trigger actions when device values cross thresholds (e.g., M0 ON when D100 > 500)
  - **Sequence** — Step through a series of actions with configurable waits

- **State Persistence** — You can now save the entire device state to a JSON file and restore it later. Click "Save State" / "Load State" in the Settings panel.

- **Internationalization** — You can now switch between English and Japanese from the navigation bar. The full UI — labels, navigation, buttons — updates instantly.

### ⚡ Improved

- **Latency Emulation** — You can now simulate real-world network conditions with 5 modes: no delay, fixed delay, random range, normal distribution, and timeout simulation. Use the Settings panel to configure parameters.
- **Expression Evaluator** — Script expressions now include 4 built-in functions (`clamp`, `square`, `triangle`, `sawtooth`) and automatic access to runtime variables (`t`, `dt`, `tick`) plus any device value by name (e.g., `D100`).

### 🐛 Fixed

*(No bug fixes in initial release.)*

### 🔒 Security

- **Safe Script Execution** — The expression evaluator uses Python's AST parser with a strict allowlist. `__import__`, attribute access, and calls to non-whitelisted functions are blocked. Scripts cannot access the filesystem or execute arbitrary Python.
- **Thread-Safe Device Access** — Device memory operations use fine-grained locking to prevent race conditions in concurrent read/write scenarios.

---

## About Versioning

This project follows [Semantic Versioning](https://semver.org/).

[Compare v0.1.0 → v1.0.0](https://github.com/euledge/plc-emulator/compare/v0.1.0...v1.0.0) | [Compare v1.0.0 → HEAD](https://github.com/euledge/plc-emulator/compare/v1.0.0...HEAD)
