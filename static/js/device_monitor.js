const DeviceMonitor = {
  ws: null,
  devices: [],
  currentTab: 'D',
  async init() {
    const container = document.getElementById('page-monitor');
    container.innerHTML = `
      <div class="panel">
        <h3 data-i18n="nav.monitor">Device Monitor</h3>
        <div class="device-tabs" id="device_tabs" style="display:flex;gap:0.4rem;margin-bottom:1rem;flex-wrap:wrap;">
          <button class="device-tab active" data-dev="D">D</button>
          <button class="device-tab" data-dev="W">W</button>
          <button class="device-tab" data-dev="M">M</button>
          <button class="device-tab" data-dev="X">X</button>
          <button class="device-tab" data-dev="Y">Y</button>
          <button class="device-tab" data-dev="L">L</button>
          <button class="device-tab" data-dev="B">B</button>
          <button class="device-tab" data-dev="R">R</button>
          <button class="device-tab" data-dev="ZR">ZR</button>
        </div>
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
            <div class="btn-row">
              <button id="mon_add">Add</button>
              <button id="mon_clear" class="secondary" data-i18n="monitor.clear">Clear All</button>
            </div>
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
    document.getElementById('mon_clear').addEventListener('click', () => this.clearAll());
    document.getElementById('mon_device').addEventListener('change', e => this.selectTab(e.target.value));
    document.querySelectorAll('.device-tab').forEach(btn => {
      btn.addEventListener('click', () => this.selectTab(btn.dataset.dev));
    });
    this.connectWs();
  },

  selectTab(dev) {
    this.currentTab = dev;
    const monDev = document.getElementById('mon_device');
    if (monDev) monDev.value = dev;
    document.querySelectorAll('.device-tab').forEach(b => {
      if (b.dataset.dev === dev) b.classList.add('active');
      else b.classList.remove('active');
    });
    this.renderTable();
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

  formatValue(val, fmt) {
    if (val === null || val === undefined) return '---';
    if (fmt === 'HEX') return `0x${val.toString(16).toUpperCase()}`;
    if (fmt === 'BIN') return `0b${val.toString(2)}`;
    return String(val);
  },

  addDevice() {
    const dev = document.getElementById('mon_device').value;
    const addr = parseInt(document.getElementById('mon_address').value);
    const fmt = document.getElementById('mon_format').value;
    this.devices.push({ device: dev, address: addr, format: fmt, value: null });
    if (dev !== this.currentTab) {
      this.selectTab(dev);
    } else {
      this.renderTable();
    }
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'monitor_add', device: dev, address: addr }));
    }
  },

  renderTable() {
    const tbody = document.getElementById('mon_table');
    const filtered = this.devices
      .map((d, i) => ({ ...d, originalIndex: i }))
      .filter(d => d.device === this.currentTab);

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:#888;padding:1rem;">No ${this.currentTab} devices monitored. Add one above.</td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map(d =>
      `<tr>
        <td>${d.device}</td>
        <td>${d.address}</td>
        <td id="val_${d.originalIndex}" class="editable-val" title="Double-click to edit" style="cursor:pointer;" ondblclick="DeviceMonitor.editCell(${d.originalIndex})">${this.formatValue(d.value, d.format)}</td>
        <td><button class="secondary" onclick="DeviceMonitor.removeDevice(${d.originalIndex})">×</button></td>
      </tr>`
    ).join('');
  },

  removeDevice(i) {
    this.devices.splice(i, 1);
    this.renderTable();
  },

  async clearAll() {
    if (!confirm('Are you sure you want to clear device memory?')) return;
    try {
      const resp = await fetch('/api/devices/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preserve_latch: false })
      });
      if (resp.ok) {
        this.devices.forEach(d => { d.value = 0; });
        this.renderTable();
      }
    } catch (e) {}
  },

  updateRow(msg) {
    const idx = this.devices.findIndex(d => d.device === msg.device && d.address === msg.address);
    if (idx >= 0) {
      this.devices[idx].value = msg.value;
      if (msg.device === this.currentTab) {
        const el = document.getElementById(`val_${idx}`);
        if (el && !el.querySelector('input')) {
          el.textContent = this.formatValue(msg.value, this.devices[idx].format);
        }
      }
    }
  },

  editCell(i) {
    const el = document.getElementById(`val_${i}`);
    if (!el || el.querySelector('input')) return;
    const currentVal = this.devices[i].value ?? 0;
    el.innerHTML = `<input type="text" id="edit_input_${i}" value="${currentVal}" style="width:100%;max-width:120px;padding:2px 4px;background:#1a1a2e;color:#fff;border:1px solid #4ecca3;border-radius:3px;">`;
    const input = document.getElementById(`edit_input_${i}`);
    input.focus();
    input.select();
    let committed = false;
    const commit = async () => {
      if (committed) return;
      committed = true;
      await this.commitEdit(i, input.value.trim());
    };
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') commit();
      else if (e.key === 'Escape') { committed = true; this.renderTable(); }
    });
    input.addEventListener('blur', commit);
  },

  async commitEdit(i, str) {
    const d = this.devices[i];
    if (!d) return;
    let val;
    if (str.startsWith('0x') || str.startsWith('0X')) val = parseInt(str, 16);
    else if (str.startsWith('0b') || str.startsWith('0B')) val = parseInt(str, 2);
    else val = parseInt(str, 10);

    if (isNaN(val)) {
      this.renderTable();
      return;
    }

    try {
      const resp = await fetch(`/api/devices/${encodeURIComponent(d.device)}/${d.address}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: val })
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(err.detail || 'Value update failed');
        this.renderTable();
        return;
      }
      d.value = val;
      this.renderTable();
    } catch (e) {
      this.renderTable();
    }
  }
};
