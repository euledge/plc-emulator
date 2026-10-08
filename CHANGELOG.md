# Changelog

All notable changes to PLCEmulator, tracked by release date.

## Unreleased

### Fixed

- Unexpected Web server exit now completes PLC shutdown before signaling stopped, without duplicate cleanup (#3).
- Web settings now persist the selected PLC model and latency, report save errors, and apply TCP/UDP or port changes without dropping clients when a switch fails (#4).
- Unsupported protocol and data-format selections return an error instead of reporting a successful switch; only MC 3E binary is currently available (#4).
- Configuration updates validate all fields before changing live state and normalize transport values so TCP remains TCP after restart (#4).

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

This project follows [Semantic Versioning](https://semver.org/). As an initial development release (0.x), breaking changes may occur in MINOR versions until 1.0.0.

[Compare v0.1.0 → HEAD](https://github.com/euledge/plc-emulator/compare/v0.1.0...HEAD)
