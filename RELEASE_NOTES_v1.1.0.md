# v1.1.0 — PLC Emulator Release Notes

**Release Date:** October 21, 2026

---

## Minor Release (v1.1.0) — 32-Bit Integer Display & Hex Addressing Conformance

PLCEmulator v1.1.0 introduces enhanced data representation capabilities in the Web Device Monitor, strict hexadecimal addressing conformance for MELSEC devices, configuration persistence across restarts, and rich visual documentation.

![PLCEmulator Web Dashboard — Device Monitor](docs/images/manual_device_monitor.png)

---

### ✨ New Features

#### 1. 32-Bit Integer Support in Device Monitor (DWORD & LONG) (#74)
- **32-Bit Display Formats**:
  - Added `DWORD` (unsigned 32-bit integer: 0 to 4,294,967,295) and `LONG` (signed 32-bit integer: -2,147,483,648 to 2,147,483,647) to the Device Monitor display format options.
  - Automatically reconstructs two consecutive 16-bit word registers (e.g. `D100` and `D101`) in little-endian order.
- **Real-Time WebSocket Multi-Word Subscription**:
  - The WebSocket monitor automatically subscribes to and tracks both low-word and high-word changes, keeping 32-bit composite values synchronized in real time.
- **Direct Inline Editing for 32-Bit Values**:
  - Double-click any value cell formatted as `DWORD` or `LONG` to edit directly.
  - The Web UI automatically decomposes the input into lower and upper 16-bit words and updates device memory via the REST API.

#### 2. Animated Demos & Promo Video Documentation (#76)
- **Visual Walkthroughs**:
  - Added interactive demo GIFs and high-resolution promo walkthrough videos in both English and Japanese to the README.
  - Showcases real-time packet inspection, device monitoring, and scenario-based simulation workflows.

---

### ⚡ Improvements

#### 1. Full Hexadecimal Device Addressing Conformance (#72)
- **MELSEC Specification Conformance**:
  - Fully supports hexadecimal addressing across all standard hexadecimal devices: Link Registers (`W`), Inputs (`X`), Outputs (`Y`), Link Relays (`B`), Special Link Registers (`SW`), and Special Link Relays (`SB`).
  - Addresses like `W10` represent hexadecimal `0x10` (decimal 16), eliminating addressing discrepancies with physical Mitsubishi PLCs.
- **Unified Across Engine & UI**:
  - Hexadecimal addressing is supported seamlessly in the YAML Script DSL (e.g. `W10`, `X1A`, `B20`), the SafeEvaluator math expression engine, and the Web UI Device Monitor.
- **Strict Validation**:
  - The script parser strictly rejects accidental hexadecimal address formats on decimal-based devices (`D`, `M`, `L`, etc.), catching syntax issues before execution.

#### 2. Configuration Persistence & Active Port Indicator (#70)
- **Automatic Settings Persistence**:
  - Settings modified through the Web UI (including PLC communication port, protocol, and latency configuration) are automatically saved to `saves/config.json` and restored on next application startup.
- **Active Port Monitoring**:
  - Added an `active_port` field to `/api/config` and a live indicator badge in the Settings UI showing the active port currently bound and listening.
- **Dynamic Port Re-binding Tests**:
  - Added integration and E2E tests validating runtime TCP port changes and reliable socket re-binding.

#### 3. Documentation Updates (#74)
- Updated both English and Japanese User Manuals ([`docs/user_manual.md`](docs/user_manual.md), [`docs/user_manual.ja.md`](docs/user_manual.ja.md)) and the Script DSL Reference ([`docs/script_dsl_reference.md`](docs/script_dsl_reference.md)) with 32-bit data type guidelines, hexadecimal device syntax rules, and PLC model memory limits.

---

### 🐛 Bug Fixes

- **Settings Page Error (#70)**: Fixed an unhandled `ReferenceError: params is not defined` occurring on Web settings page load.
- **Git Hygiene**: Untracked and excluded temporary YAML scripts in the repository root via updated `.gitignore` rules.

---

### 🧪 Test & Quality Verification

- **281 Automated Tests Passing**:
  - Unit, integration, and protocol matrix tests validating 3E/4E/1E/SLMP frames, bit/word operations, 32-bit format parsing, dynamic config updates, and AST expression safety.
  - 100% test pass rate with pytest.

---

## Documentation Links

- [User Manual (English)](docs/user_manual.md)
- [ユーザーマニュアル（日本語）](docs/user_manual.ja.md)
- [Script DSL Reference](docs/script_dsl_reference.md)
- [Release Notes (v1.0.0)](RELEASE_NOTES_v1.0.0.md)
- [Release Notes (v0.1.0)](RELEASE_NOTES_v0.1.0.md)
