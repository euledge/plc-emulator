const SettingsPage = {
  async init() {
    const container = document.getElementById('page-settings');
    container.innerHTML = `
      <div class="panel">
        <h3 data-i18n="nav.settings">Settings</h3>
        <div class="form-row">
          <div class="form-group">
            <label data-i18n="config.protocol">Protocol</label>
            <select id="protocol"><option value="3E">MC 3E</option><option value="1E">MC 1E</option><option value="4E">MC 4E</option><option value="SLMP">SLMP</option></select>
          </div>
          <div class="form-group">
            <label data-i18n="config.transport">Transport</label>
            <select id="transport"><option value="tcp">TCP</option><option value="udp">UDP</option></select>
          </div>
          <div class="form-group">
            <label data-i18n="config.port">Port</label>
            <input type="number" id="port" min="0" max="65535">
          </div>
          <div class="form-group">
            <label data-i18n="config.format">Format</label>
            <select id="data_format"><option value="binary">BINARY</option><option value="ascii">ASCII</option></select>
          </div>
          <div class="form-group">
            <label data-i18n="config.plc_model">PLC Model</label>
            <select id="plc_model"><option value="Q03UDE">Q03UDE (MELSEC-Q)</option><option value="Q06UDE">Q06UDE (MELSEC-Q)</option><option value="R04CPU">R04CPU (MELSEC iQ-R)</option><option value="R08CPU">R08CPU (MELSEC iQ-R)</option><option value="FX5U">FX5U (MELSEC iQ-F)</option><option value="L06CPU">L06CPU (MELSEC-L)</option></select>
          </div>
        </div>
      </div>
      <div class="panel">
        <h3 data-i18n="latency.mode">Latency Mode</h3>
        <div class="form-row">
          <div class="form-group">
            <label data-i18n="latency.mode">Mode</label>
            <select id="latency_mode"><option value="none" data-i18n="latency.none">None</option><option value="fixed" data-i18n="latency.fixed">Fixed</option><option value="random" data-i18n="latency.random">Random</option><option value="normal" data-i18n="latency.normal">Normal</option><option value="timeout" data-i18n="latency.timeout">Timeout</option></select>
          </div>
          <div class="form-group"><label>fixed ms</label><input type="number" id="latency_delay" min="0"></div>
          <div class="form-group"><label>min ms</label><input type="number" id="latency_min" min="0"></div>
          <div class="form-group"><label>max ms</label><input type="number" id="latency_max" min="0"></div>
          <div class="form-group"><label>mean ms</label><input type="number" id="latency_mean" min="0"></div>
          <div class="form-group"><label>std ms</label><input type="number" id="latency_std" min="0"></div>
          <div class="form-group"><label>timeout rate</label><input type="number" id="latency_timeout_rate" min="0" max="1" step="0.01"></div>
        </div>
        <div class="btn-row">
          <button id="save_config">Save</button>
          <button id="btn_save_state" class="secondary">Save State</button>
          <button id="btn_load_state" class="secondary">Load State</button>
          <span id="server_status" role="status" aria-live="polite" style="margin-left:auto;padding:0.3rem 0.6rem;border-radius:4px;">Ready</span>
        </div>
      </div>`;
    document.getElementById('save_config').addEventListener('click', () => this.saveConfig());
    document.getElementById('btn_save_state').addEventListener('click', () => this.saveState());
    document.getElementById('btn_load_state').addEventListener('click', () => this.loadState());
    await this.loadConfig();
  },

  async loadConfig() {
    const resp = await fetch('/api/config');
    const cfg = await resp.json();
    if (!document.getElementById('protocol')) return;
    document.getElementById('protocol').value = cfg.protocol || '3E';
    document.getElementById('transport').value = (cfg.transport || 'tcp').toLowerCase();
    document.getElementById('port').value = cfg.port ?? 5000;
    document.getElementById('data_format').value = (cfg.data_format || 'binary').toLowerCase();
    document.getElementById('plc_model').value = cfg.plc_model || 'Q03UDE';
    document.getElementById('latency_mode').value = cfg.latency_mode || 'none';
    const params = cfg.latency_params || {};
    document.getElementById('latency_delay').value = params.delay_ms ?? 0;
    document.getElementById('latency_min').value = params.min_ms ?? 0;
    document.getElementById('latency_max').value = params.max_ms ?? 0;
    document.getElementById('latency_mean').value = params.mean_ms ?? 0;
    document.getElementById('latency_std').value = params.std_ms ?? 0;
    document.getElementById('latency_timeout_rate').value = params.timeout_rate ?? 0;
  },

  async saveConfig() {
    const status = document.getElementById('server_status');
    const showStatus = (message, error) => {
      status.textContent = message;
      status.style.color = error ? '#ff8a8a' : '#8be6bd';
    };
    const port = document.getElementById('port');
    if (!port.value || !port.checkValidity()) {
      showStatus('Invalid port', true);
      return;
    }
    const mode = document.getElementById('latency_mode').value;
    const number = (id) => Number(document.getElementById(id).value);
    let params = {};
    if (mode === 'fixed') {
      params = { delay_ms: number('latency_delay') };
    } else if (mode === 'random') {
      params = { min_ms: number('latency_min'), max_ms: number('latency_max') };
    } else if (mode === 'normal') {
      params = { mean_ms: number('latency_mean'), std_ms: number('latency_std') };
    } else if (mode === 'timeout') {
      params = { timeout_rate: number('latency_timeout_rate') };
    }
    const body = {
      protocol: document.getElementById('protocol').value,
      transport: document.getElementById('transport').value,
      port: Number(port.value),
      data_format: document.getElementById('data_format').value,
      plc_model: document.getElementById('plc_model').value,
      latency_mode: mode,
      latency_params: params,
    };
    try {
      const response = await fetch('/api/config', {
        method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
      });
      const result = await response.json();
      if (!response.ok) {
        showStatus(typeof result.detail === 'string' ? result.detail : `Save failed (${response.status})`, true);
        return;
      }
      showStatus('Saved', false);
    } catch (error) {
      showStatus(`Save failed: ${error.message}`, true);
    }
  },

  async saveState() {
    await fetch('/api/save', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: 'plc_state.json'}) });
  },

  async loadState() {
    await fetch('/api/load', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: 'plc_state.json'}) });
  }
};
