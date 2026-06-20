const DeviceMonitor = {
  ws: null,
  devices: [],

  async init() {
    const container = document.getElementById('page-monitor');
    container.innerHTML = `
      <div class="panel">
        <h3 data-i18n="nav.monitor">Device Monitor</h3>
        <div class="form-row">
          <div class="form-group">
            <label data-i18n="monitor.device">Device</label>
            <select id="mon_device"><option>D</option><option>W</option><option>M</option><option>X</option><option>Y</option><option>L</option><option>B</option><option>R</option><option>ZR</option></select>
          </div>
          <div class="form-group">
            <label data-i18n="monitor.address">Address</label>
            <input type="number" id="mon_address" value="0">
          </div>
          <div class="form-group">
            <label data-i18n="monitor.format">Format</label>
            <select id="mon_format"><option>DEC</option><option>HEX</option><option>BIN</option></select>
          </div>
          <div class="form-group">
            <label>&nbsp;</label>
            <button id="mon_add">Add</button>
          </div>
        </div>
      </div>
      <div class="panel">
        <table><thead><tr>
          <th data-i18n="monitor.device">Device</th>
          <th data-i18n="monitor.address">Address</th>
          <th data-i18n="monitor.value">Value</th>
        </tr></thead><tbody id="mon_table"></tbody></table>
      </div>`;
    document.getElementById('mon_add').addEventListener('click', () => this.addDevice());
    this.connectWs();
  },

  connectWs() {
    if (this.ws) this.ws.close();
    this.ws = new WebSocket(`ws://${location.host}/ws`);
    this.ws.onmessage = e => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'device_update') this.updateRow(msg);
    };
    this.ws.onclose = () => setTimeout(() => this.connectWs(), 1000);
  },

  addDevice() {
    const dev = document.getElementById('mon_device').value;
    const addr = parseInt(document.getElementById('mon_address').value);
    const fmt = document.getElementById('mon_format').value;
    this.devices.push({ device: dev, address: addr, format: fmt });
    this.renderTable();
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'monitor_add', device: dev, address: addr }));
    }
  },

  renderTable() {
    const tbody = document.getElementById('mon_table');
    tbody.innerHTML = this.devices.map((d, i) =>
      `<tr>
        <td>${d.device}</td>
        <td>${d.address}</td>
        <td id="val_${i}">---</td>
        <td><button class="secondary" onclick="DeviceMonitor.removeDevice(${i})">×</button></td>
      </tr>`
    ).join('');
  },

  removeDevice(i) {
    this.devices.splice(i, 1);
    this.renderTable();
  },

  updateRow(msg) {
    const idx = this.devices.findIndex(d => d.device === msg.device && d.address === msg.address);
    if (idx >= 0) {
      const el = document.getElementById(`val_${idx}`);
      if (el) {
        const fmt = this.devices[idx].format;
        el.textContent = fmt === 'HEX' ? `0x${msg.value.toString(16).toUpperCase()}` : fmt === 'BIN' ? `0b${msg.value.toString(2)}` : msg.value;
      }
    }
  }
};
