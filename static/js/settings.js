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
            <select id="transport"><option>TCP</option><option>UDP</option></select>
          </div>
          <div class="form-group">
            <label data-i18n="config.port">Port</label>
            <input type="number" id="port" min="1" max="65535">
          </div>
          <div class="form-group">
            <label data-i18n="config.format">Format</label>
            <select id="data_format"><option>BINARY</option><option>ASCII</option></select>
          </div>
          <div class="form-group">
            <label data-i18n="config.plc_model">PLC Model</label>
            <select id="plc_model"><option>Q</option><option>L</option><option>FX</option></select>
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
          <div class="form-group"><label>min ms</label><input type="number" id="latency_min"></div>
          <div class="form-group"><label>max ms</label><input type="number" id="latency_max"></div>
          <div class="form-group"><label>mean ms</label><input type="number" id="latency_mean"></div>
          <div class="form-group"><label>std ms</label><input type="number" id="latency_std"></div>
        </div>
        <div class="btn-row">
          <button id="save_config">Save</button>
          <button id="btn_save_state" class="secondary">Save State</button>
          <button id="btn_load_state" class="secondary">Load State</button>
          <span id="server_status" style="margin-left:auto;padding:0.3rem 0.6rem;border-radius:4px;">Stopped</span>
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
    document.getElementById('transport').value = cfg.transport || 'TCP';
    document.getElementById('port').value = cfg.port || 5000;
    document.getElementById('data_format').value = cfg.data_format || 'BINARY';
    document.getElementById('plc_model').value = cfg.plc_model || 'Q';
    document.getElementById('latency_mode').value = cfg.latency?.mode || 'none';
    document.getElementById('latency_min').value = cfg.latency?.min || 0;
    document.getElementById('latency_max').value = cfg.latency?.max || 0;
    document.getElementById('latency_mean').value = cfg.latency?.mean || 0;
    document.getElementById('latency_std').value = cfg.latency?.std || 0;
  },

  async saveConfig() {
    const body = {
      protocol: document.getElementById('protocol').value,
      transport: document.getElementById('transport').value,
      port: parseInt(document.getElementById('port').value),
      data_format: document.getElementById('data_format').value,
      plc_model: document.getElementById('plc_model').value,
      latency: {
        mode: document.getElementById('latency_mode').value,
        min: parseInt(document.getElementById('latency_min').value),
        max: parseInt(document.getElementById('latency_max').value),
        mean: parseInt(document.getElementById('latency_mean').value),
        std: parseInt(document.getElementById('latency_std').value),
      }
    };
    await fetch('/api/config', { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
  },

  async saveState() {
    await fetch('/api/save', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: 'plc_state.json'}) });
  },

  async loadState() {
    await fetch('/api/load', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: 'plc_state.json'}) });
  }
};
