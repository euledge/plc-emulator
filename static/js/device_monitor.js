const DeviceMonitor = {
  ws: null,
  devices: [],
  currentTab: 'ALL',

  async init() {
    const container = document.getElementById('page-monitor');
    container.innerHTML = `
      <div class="panel">
        <h3 data-i18n="nav.monitor">Device Monitor</h3>
        <div class="device-tabs" id="device_tabs" style="display:flex;gap:0.4rem;margin-bottom:1rem;flex-wrap:wrap;">
          <button class="device-tab active" data-dev="ALL" data-i18n="monitor.tab_all">ALL</button>
          <button class="device-tab" data-dev="D">D</button>
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
            <label data-i18n="monitor.points">Points</label>
            <input type="number" id="mon_points" value="1" min="1" max="1000">
          </div>
          <div class="form-group">
            <label data-i18n="monitor.format">Format</label>
            <select id="mon_format">
              <option value="DEC">DEC</option>
              <option value="DEC_SIGNED">DEC (Signed)</option>
              <option value="HEX">HEX</option>
              <option value="BIN">BIN</option>
              <option value="FLOAT">FLOAT</option>
              <option value="ASCII">ASCII</option>
            </select>
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
          <th data-i18n="monitor.format">Format</th>
          <th data-i18n="monitor.value">Value</th>
          <th></th>
        </tr></thead><tbody id="mon_table"></tbody></table>
      </div>`;
    document.getElementById('mon_add').addEventListener('click', () => this.addDevice());
    document.getElementById('mon_clear').addEventListener('click', () => this.clearAll());
    document.getElementById('mon_device').addEventListener('change', e => {
      if (this.currentTab !== 'ALL') {
        this.selectTab(e.target.value);
      }
    });
    document.getElementById('mon_address').addEventListener('keydown', e => {
      if (e.key === 'Enter') this.addDevice();
    });
    document.getElementById('mon_points').addEventListener('keydown', e => {
      if (e.key === 'Enter') this.addDevice();
    });
    document.querySelectorAll('.device-tab').forEach(btn => {
      btn.addEventListener('click', () => this.selectTab(btn.dataset.dev));
    });
    this.connectWs();
  },

  selectTab(dev) {
    this.currentTab = dev;
    const monDev = document.getElementById('mon_device');
    if (monDev && dev !== 'ALL') monDev.value = dev;
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

  formatValue(val, fmt, d) {
    if (val === null || val === undefined) return '---';
    const num = Number(val);
    if (fmt === 'DEC' || fmt === 'DEC_UNSIGNED') {
      return String(num & 0xFFFF);
    }
    if (fmt === 'DEC_SIGNED') {
      const u16 = num & 0xFFFF;
      const s16 = u16 >= 0x8000 ? u16 - 0x10000 : u16;
      return String(s16);
    }
    if (fmt === 'HEX') {
      return '0x' + (num & 0xFFFF).toString(16).toUpperCase().padStart(4, '0');
    }
    if (fmt === 'BIN') {
      return '0b' + (num & 0xFFFF).toString(2).padStart(16, '0');
    }
    if (fmt === 'ASCII') {
      const u16 = num & 0xFFFF;
      const b0 = u16 & 0xFF;
      const b1 = (u16 >> 8) & 0xFF;
      const c0 = (b0 >= 32 && b0 <= 126) ? String.fromCharCode(b0) : '.';
      const c1 = (b1 >= 32 && b1 <= 126) ? String.fromCharCode(b1) : '.';
      return `'${c0}${c1}'`;
    }
    if (fmt === 'FLOAT') {
      let highWord = 0;
      if (d) {
        const next = this.devices.find(x => x.device === d.device && x.address === d.address + 1);
        if (next && next.value !== null && next.value !== undefined) {
          highWord = Number(next.value) & 0xFFFF;
        } else if (d.highWord !== undefined && d.highWord !== null) {
          highWord = Number(d.highWord) & 0xFFFF;
        }
      }
      const buf = new ArrayBuffer(4);
      const view = new DataView(buf);
      view.setUint16(0, num & 0xFFFF, true);
      view.setUint16(2, highWord & 0xFFFF, true);
      const f = view.getFloat32(0, true);
      if (!Number.isFinite(f)) return String(f);
      return Number.isInteger(f) ? f.toFixed(1) : parseFloat(f.toPrecision(7)).toString();
    }
    return String(val);
  },

  addDevice() {
    const dev = document.getElementById('mon_device').value;
    const startAddr = parseInt(document.getElementById('mon_address').value) || 0;
    const pointsInput = document.getElementById('mon_points');
    const points = pointsInput ? Math.max(1, parseInt(pointsInput.value) || 1) : 1;
    const fmt = document.getElementById('mon_format').value;

    for (let i = 0; i < points; i++) {
      const addr = startAddr + i;
      const existing = this.devices.find(d => d.device === dev && d.address === addr);
      if (existing) {
        existing.format = fmt;
      } else {
        this.devices.push({ device: dev, address: addr, format: fmt, value: null });
      }
      if (fmt === 'FLOAT' && this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'monitor_add', device: dev, address: addr + 1 }));
      }
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'monitor_add', device: dev, address: addr }));
      }
    }

    if (this.currentTab !== 'ALL' && dev !== this.currentTab) {
      this.selectTab(dev);
    } else {
      this.renderTable();
    }
  },

  renderTable() {
    const tbody = document.getElementById('mon_table');
    const filtered = this.devices
      .map((d, i) => ({ ...d, originalIndex: i }))
      .filter(d => this.currentTab === 'ALL' || d.device === this.currentTab);

    if (filtered.length === 0) {
      const tabLabel = this.currentTab === 'ALL' ? '' : `${this.currentTab} `;
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#888;padding:1rem;">No ${tabLabel}devices monitored. Add one above.</td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map(d =>
      `<tr>
        <td>${d.device}</td>
        <td>${d.address}</td>
        <td>
          <select class="row-format" style="width:auto;padding:2px 4px;font-size:0.8rem;" onchange="DeviceMonitor.changeFormat(${d.originalIndex}, this.value)">
            <option value="DEC"${d.format === 'DEC' ? ' selected' : ''}>DEC</option>
            <option value="DEC_SIGNED"${d.format === 'DEC_SIGNED' ? ' selected' : ''}>DEC (Signed)</option>
            <option value="HEX"${d.format === 'HEX' ? ' selected' : ''}>HEX</option>
            <option value="BIN"${d.format === 'BIN' ? ' selected' : ''}>BIN</option>
            <option value="FLOAT"${d.format === 'FLOAT' ? ' selected' : ''}>FLOAT</option>
            <option value="ASCII"${d.format === 'ASCII' ? ' selected' : ''}>ASCII</option>
          </select>
        </td>
        <td id="val_${d.originalIndex}" class="editable-val" title="Double-click to edit" style="cursor:pointer;" ondblclick="DeviceMonitor.editCell(${d.originalIndex})">${this.formatValue(d.value, d.format, d)}</td>
        <td><button class="secondary" onclick="DeviceMonitor.removeDevice(${d.originalIndex})">×</button></td>
      </tr>`
    ).join('');
  },

  changeFormat(i, fmt) {
    if (this.devices[i]) {
      this.devices[i].format = fmt;
      if (fmt === 'FLOAT' && this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'monitor_add', device: this.devices[i].device, address: this.devices[i].address + 1 }));
      }
      this.renderTable();
    }
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
    let touched = false;
    this.devices.forEach((d, idx) => {
      if (d.device === msg.device) {
        if (d.address === msg.address) {
          d.value = msg.value;
          touched = true;
        } else if (d.format === 'FLOAT' && d.address + 1 === msg.address) {
          d.highWord = msg.value;
          touched = true;
        }
      }
    });
    if (touched) {
      this.renderTable();
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

    if (d.format === 'FLOAT') {
      const f = parseFloat(str);
      if (isNaN(f) || !isFinite(f)) {
        this.renderTable();
        return;
      }
      const buf = new ArrayBuffer(4);
      const view = new DataView(buf);
      view.setFloat32(0, f, true);
      const low = view.getUint16(0, true);
      const high = view.getUint16(2, true);
      try {
        await fetch(`/api/devices/${encodeURIComponent(d.device)}/${d.address}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value: low })
        });
        await fetch(`/api/devices/${encodeURIComponent(d.device)}/${d.address + 1}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value: high })
        });
        d.value = low;
        d.highWord = high;
      } catch (e) {}
      this.renderTable();
      return;
    }

    if (d.format === 'ASCII') {
      let clean = str.replace(/^['"]|['"]$/g, '');
      const c0 = clean.length > 0 ? clean.charCodeAt(0) : 0;
      const c1 = clean.length > 1 ? clean.charCodeAt(1) : 0;
      const val = (c0 & 0xFF) | ((c1 & 0xFF) << 8);
      try {
        await fetch(`/api/devices/${encodeURIComponent(d.device)}/${d.address}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value: val })
        });
        d.value = val;
      } catch (e) {}
      this.renderTable();
      return;
    }

    let val;
    if (d.format === 'DEC_SIGNED') {
      val = parseInt(str, 10);
      if (!isNaN(val)) {
        val = val < 0 ? (val + 0x10000) & 0xFFFF : val & 0xFFFF;
      }
    } else if (str.startsWith('0x') || str.startsWith('0X')) {
      val = parseInt(str, 16);
    } else if (str.startsWith('0b') || str.startsWith('0B')) {
      val = parseInt(str, 2);
    } else {
      val = parseInt(str, 10);
    }

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
