# PLCEmulator User Manual

This manual explains how to use **PLCEmulator**, an open-source PLC communication emulator compatible with Mitsubishi Electric MELSEC MC Protocol and SLMP.

---

## Table of Contents

1. [Overview & Features](#1-overview--features)
2. [Quick Start](#2-quick-start)
3. [UI Guide with Screenshots](#3-ui-guide-with-screenshots)
   - [3.1 Settings Panel](#31-settings-panel)
   - [3.2 Device Monitor](#32-device-monitor)
   - [3.3 Communication Log](#33-communication-log)
   - [3.4 Script Editor](#34-script-editor)
4. [Practical Testing Scenarios](#4-practical-testing-scenarios)
5. [REST API Reference](#5-rest-api-reference)
6. [Troubleshooting & FAQ](#6-troubleshooting--faq)

---

## 1. Overview & Features

PLCEmulator allows developers to test SCADA, MES, IoT gateways, and custom communication applications on PC without needing physical PLC hardware.

### Key Features
- **Multi-Protocol Support**: MC Protocol 3E (Binary/ASCII), 4E, 1E, and SLMP.
- **Flexible Transports**: Both TCP and UDP supported with dynamic runtime switching.
- **Essential PLC Commands**: Batch Read/Write (`0401`/`1401`), Random Read/Write (`0403`/`1402`), Monitor Register/Execute (`0801`/`0802`), CPU Model Read (`0101`), Remote RUN/STOP (`1001`/`1002`), Remote Password Lock/Unlock (`1630`/`1631`).
- **Real-Time Web Dashboard**: Interactive device monitoring, inline editing, parsed packet logging, 6 display formats, and script execution engine.
- **Latency & Fault Simulation**: Configurable network delays (Fixed, Random, Normal distribution), timeouts, and error response suppression.

---

## 2. Quick Start

### Starting the Server

```bash
# Sync dependencies (using uv)
uv sync

# Launch the emulator
uv run python main.py
```

Two services will start simultaneously:
- **PLC Server**: Default `TCP 5000` (listening on 0.0.0.0)
- **Web UI Dashboard**: `http://127.0.0.1:8000`

Open your web browser and navigate to `http://127.0.0.1:8000`. You can switch language between **JA** and **EN** at any time using the buttons in the top right.

---

## 3. UI Guide with Screenshots

### 3.1 Settings Panel

Configure server protocols, networking, PLC model range profiles, latency emulation, and state persistence.

![Settings Panel](images/manual_settings.png)

#### Features
1. **Server Configuration**:
   - **Protocol**: Choose from `3E`, `1E`, `4E`, `SLMP`. Changes apply dynamically without restarting the app.
   - **Transport**: `TCP` or `UDP`.
   - **Port**: Communication port (default: `5000`).
   - **Data Format**: `BINARY` or `ASCII` (for 3E).
   - **PLC Model**: Select `Q03UDE`, `Q06UDE`, `R04CPU`, `R08CPU`, `FX5U`, or `L06CPU`. Validates device ranges and provides CPU model identification strings.
   - **Error Response**: When disabled, dropped/silent error response behavior is simulated.
   - **Save Button**: Immediately updates the running server.

2. **Latency Emulation**:
   - Modes: `None`, `Fixed`, `Random`, `Normal`, `Timeout`.
   - Set delay in milliseconds or timeout rate to stress-test your client applications under adverse network conditions.

3. **Latency Statistics Panel**:
   - Tracks packet counts, average delay, maximum delay, minimum delay, and simulated timeout counts.
   - "Refresh" updates stats; "Reset" clears counters.

4. **State Persistence**:
   - **Save State**: Saves all current device memory values to a JSON file.
   - **Load State**: Restores saved values.

---

### 3.2 Device Monitor

Monitor and edit internal PLC device memory (D, W, M, X, Y, L, B, R, ZR, etc.) in real time.

![Device Monitor](images/manual_device_monitor.png)

#### Features
1. **Adding Devices**:
   - **Device**: Select device type (D, M, X, Y, etc.).
   - **Address**: Starting address.
   - **Points**: Number of consecutive addresses to monitor (e.g. `3` adds D100, D101, D102 in one click).
   - **Format**: Initial display format.
   - **Add Button**: Inserts devices into the monitoring table. Pressing Enter in the input fields also triggers addition.

2. **Device Type Tabs**:
   - **"ALL" Tab**: Shows all monitored devices across all types in a single table (default).
   - **Specific Tabs (D, W, M...)**: Filters the list to display only the selected device type.

3. **6 Display Formats**:
   - Switch format per row on the fly:
     - `DEC`: Unsigned 16-bit integer (0 to 65535)
     - `DEC (Signed)`: Signed 16-bit integer (-32768 to 32767)
     - `HEX`: Hexadecimal (`0x1234`)
     - `BIN`: Binary (`0b0001001000110100`)
     - `FLOAT`: 32-bit IEEE 754 float (combines two consecutive words)
     - `ASCII`: ASCII string (2 characters per word)

4. **Direct Inline Editing**:
   - **Double-click any value cell** to edit it directly from the browser. Changes immediately reflect in memory and over PLC sockets.

5. **Removing & Clearing**:
   - Row **"×" Button**: Removes the device from the monitor.
   - **"Clear All" Button**: Clears the entire monitoring table and resets device memory to 0 after confirmation.

---

### 3.3 Communication Log

Inspect live binary and ASCII packets exchanged between client software and the emulator.

![Communication Log](images/manual_comm_log.png)

#### Features
1. **Packet Inspection & Command Recognition**:
   - **RX (`<-`, Green)**: Incoming request packets from clients.
   - **TX (`->`, Blue)**: Outgoing response packets from the emulator.
   - **Parsed Command Badges**: Automatically detects and displays badges such as `[Batch Read (0401)]` and `[Batch Write (1401)]`.
   - **Hex Dump**: Verbatim payload in hexadecimal format.
   - **Sensitive Data Masking**: Passwords in `1630` packets are automatically masked with `**`.

2. **Controls**:
   - **Auto-scroll Checkbox**: Automatically scrolls to the newest log entries.
   - **Clear Button**: Empties the current display log.
   - **Save Log Button**: Exports the displayed communication log to a timestamped `.txt` file preserving timestamps, direction arrows, command badges, and hex dumps.

---

### 3.4 Script Editor

Run autonomous simulation scenarios written in YAML to mimic automated machinery, sensor inputs, and traffic sequences.

![Script Editor](images/manual_script_editor.png)

#### Features
1. **YAML Editor with Syntax Highlighting & Line Numbers**:
   - Highlights keys, strings, numbers, booleans, and comments (`#`). Synchronized line numbers gutter.

2. **Preset Scenario Templates**:
   - Select and load pre-configured industrial scenarios:
     - `traffic_light.yaml`: Traffic light sequencing
     - `tank_level_control.yaml`: Tank water level control and pump cycling
     - `alarm_interlock.yaml`: High threshold alarm interlocking
     - `cylinder_sequence.yaml`: Pneumatic cylinder stroke sequence
     - `sensor_simulation.yaml`: Sine wave and random noise sensor simulation
     - `ramp_loop.yaml`: Triangular ramp loop generator

3. **Safe Validation (Validate Button)**:
   - Evaluates YAML syntax and verifies that expressions strictly conform to sandbox safety rules (blocks `eval`, `import`, system calls).

4. **Execution Controls**:
   - **Start**: Begins running the script in the background.
   - **Pause**: Suspends updates without resetting internal script state.
   - **Stop**: Halts execution.

---

## 4. Practical Testing Scenarios

### Scenario A: Testing SCADA / Driver Connection
1. Set protocol to `3E (Binary)` and port `5000` in **Settings**.
2. Connect your SCADA software to `127.0.0.1:5000`.
3. Check the **Comm Log** panel to verify request and response packets.
4. Modify `D100` in **Device Monitor** and verify the SCADA screen updates immediately.

### Scenario B: Testing Resilience against Timeouts & Latency
1. Under **Settings**, select `Timeout` latency mode with `timeout rate: 0.3` (30% drop rate).
2. Verify that your client application properly logs timeout exceptions and executes retry logic.
3. Check the **Latency Statistics** panel for exact timeout counts.

### Scenario C: Long-running Unattended Polling Tests
1. Load `sensor_simulation.yaml` or `sawtooth.yaml` in **Script Editor**.
2. Click **Start** to run autonomous data generation.
3. Open **Device Monitor** to watch device values cycle automatically.

---

## 5. REST API Reference

All features can be automated via REST API:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/config` | Get current server configuration |
| `POST` | `/api/config` | Dynamically update configuration |
| `GET` | `/api/devices/{type}?start={s}&count={n}` | Read device memory batch |
| `PUT` | `/api/devices/{type}/{address}` | Write device value |
| `POST` | `/api/devices/clear` | Clear device memory to 0 |
| `GET` | `/api/comm_log/export` | Download communication log as text file |
| `GET` | `/api/latency/stats` | Retrieve latency statistics |
| `POST` | `/api/latency/stats/reset` | Reset latency statistics |
| `GET` | `/api/scripts/templates` | List pre-packaged templates |
| `POST` | `/api/scripts/{name}/start` | Start script execution |

---

## 6. Troubleshooting & FAQ

#### Q1: Client cannot connect (Connection Refused)
- Verify the port configured in Settings (default: `5000`).
- Ensure no firewall rule is blocking incoming connections.

#### Q2: Added devices are not visible in Device Monitor
- Make sure the device type tab is set to **"ALL"** or matches the added device type.

#### Q3: Server responds with error code `0xC051` or `0xC058`
- The requested address exceeds the valid memory boundary for the chosen PLC model (e.g. FX5U D limit is 32767). Switch to a larger PLC model such as `R08CPU` if needed.
