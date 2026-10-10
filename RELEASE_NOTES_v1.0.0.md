# v1.0.0 — PLC Emulator Release Notes

**Release Date:** October 10, 2026

---

## First Major Release (v1.0.0) — Production-Ready Hardware-Free PLC Simulation

PLCEmulator v1.0.0 marks our first major production-stable release. Following extensive test coverage, protocol enhancements, and real-world refinements, the emulator delivers reliable, full-featured MELSEC MC Protocol and SLMP simulation for SCADA, MES, and industrial automation testing.

![PLCEmulator Web Dashboard — Device Monitor](docs/images/manual_device_monitor.png)

---

### ✨ New Features

#### 1. Comprehensive Protocol & Command Support
- **Multi-Protocol Auto-Detection**:
  - MC Protocol 3E frames (both Binary and ASCII).
  - 1E frames (A-series compatible, TCP and UDP).
  - 4E frames (with serial number echo-back).
  - SLMP (with 2-byte extended device codes and 4-byte address support).
  - Single port auto-detects incoming frame subheaders dynamically.
- **Extended Commands**:
  - Random Read (`0403`) & Random Write (`1402`): mixed word and double-word point specifications.
  - Bit-unit subcommands (`0001` / `0003`): 2-bits-per-byte packed transfers.
  - Monitor Register (`0801`) & Monitor Execute (`0802`): batch status inspection of registered devices.
  - Remote RUN (`1001`) & Remote STOP (`1002`): control emulator PLC operational state.
- **Remote Password Authentication (`1630` / `1631`)**:
  - Password unlock (`1630`) and lock (`1631`) commands.
  - Rejects incorrect passwords with `0x4A01` (`REMOTE_PASSWORD_MISMATCH`).
  - Rejects write operations with `0x4A03` (`REMOTE_PASSWORD_LOCKED`) when locked.
  - Automatically restores locked state upon client disconnection / reconnection.
  - Masks password payload in communication logs with `**`.

#### 2. Enhanced Device Monitor
- **"ALL" Tab & Device Type Filtering**:
  - "ALL" tab displays all monitored devices across all types in a single table by default.
  - Specific device type tabs (D, W, M, X, Y, L, B, R, ZR) filter the table cleanly.
- **Batch Address Addition (Points)**:
  - Add multiple consecutive addresses at once (e.g. D100..D104 with `Points = 5`).
  - Deduplication updates format instead of adding redundant rows.
- **6 Display Formats**:
  - Per-row switching between `DEC`, `DEC (Signed)`, `HEX`, `BIN`, `FLOAT` (32-bit float across 2 words), and `ASCII` (2 characters per word).
- **Direct Inline Editing & Clear All**:
  - Double-click any value cell to modify memory directly from the browser.
  - "Clear All" with confirmation clears the table view and resets PLC device memory to 0.

#### 3. Communication Log Command Badges & Export
- **Parsed Command Badges**:
  - Displays badges such as `[Batch Read (0401)]` and `[Batch Write (1401)]` alongside hex dumps.
- **Text Log Export**:
  - "Save Log" downloads a timestamped `.txt` file preserving timestamps, direction arrows, command badges, and hex dumps.
- **Auto-scroll Toggle**:
  - Pause or resume auto-scroll on incoming traffic.

#### 4. Script Editor & Full DSL Reference
- **Syntax Highlighting & Line Numbers**:
  - Highlights YAML keys, strings, numbers, booleans, and comments (`#`).
- **Pre-packaged Scenario Templates**:
  - One-click loading of industrial templates: traffic lights (`traffic_light.yaml`), tank level control (`tank_level_control.yaml`), alarm interlocks (`alarm_interlock.yaml`), cylinder sequences, sensor simulations, and ramp loops.
- **AST Sandbox Validation**:
  - "Validate" button checks YAML structure and expression safety prior to execution.
- **Script DSL Reference Manual**:
  - Comprehensive guide covering all 4 script types, built-in variables (`t`, `dt`, `tick`), functions, and operators in [`docs/script_dsl_reference.md`](docs/script_dsl_reference.md).

#### 5. Latency Statistics & Fault Emulation
- **Latency Statistics Panel**:
  - Live metrics for packet counts, average delay, maximum delay, minimum delay, and simulated timeout occurrences.
- **Error Response Suppression**:
  - Simulate silent drops on invalid packets for robust client retry testing.

#### 6. User Manual with Screenshots
- Fully illustrated documentation in Japanese ([`docs/user_manual.ja.md`](docs/user_manual.ja.md)) and English ([`docs/user_manual.md`](docs/user_manual.md)).

---

### ⚡ Improvements

- **Dynamic Server Configuration**: Runtime updates to PLC models, transports (TCP/UDP), and latency parameters without dropping existing sessions when unchanged.
- **Official MELSEC Error Codes**: Full conformance to official error codes (`0xC050`, `0xC051`, `0xC056`, `0xC058`, `0xC059`, `0xC05B`, `0xC061`, `0x4A01`, `0x4A03`).
- **CI Test Suite Isolation**: Port isolation with ephemeral ports (`port=0`), Playwright dependencies installed with `--with-deps`, all 232 tests passing cleanly in CI.

---

### 🐛 Bug Fixes

- **Fixed Device Overwrite on Multiple Address Additions (#58)**: Resolved tab-filtering confusion by introducing default "ALL" tab and decoupled dropdown selection.
- **Fixed Clear All Not Clearing Monitored Rows (#60)**: Empties internal monitoring table rows alongside backend memory zeroing.
- **Enforced 1-Client TCP Connection Policy (#9)**: Protects active sessions by immediately closing secondary connections.
- **Graceful Server Shutdown (#3)**: Prevents duplicate cleanup on unexpected exit.
- **Direct Start from Unsaved Script Editor Content (#62)**: Allows immediately starting newly written scripts directly from the editor with automatic saving and default naming, transitioning state to `running`.
- **Exclusive Script Execution on Start (#64)**: Automatically stops previously running scripts when starting a new script from the Web UI to eliminate device memory contention and flipping values, and adds a "Stop All" button.

---

## Documentation Links

- [User Manual (English)](docs/user_manual.md)
- [ユーザーマニュアル（日本語）](docs/user_manual.ja.md)
- [Script DSL Reference](docs/script_dsl_reference.md)
- [Release Notes (v0.1.0)](RELEASE_NOTES_v0.1.0.md)
