const CommLog = {
  entries: [],

  init() {
    const container = document.getElementById('page-log');
    container.innerHTML = `
      <div class="panel">
        <h3 data-i18n="nav.log">Communication Log</h3>
        <div class="btn-row">
          <label><input type="checkbox" id="log_autoscroll" checked> Auto-scroll</label>
          <button id="log_clear" class="secondary">Clear</button>
        </div>
        <div id="log_container" style="max-height:60vh;overflow:auto;background:#0f3460;padding:0.5rem;border-radius:4px;font-family:monospace;font-size:0.8rem;"></div>
      </div>`;
    document.getElementById('log_clear').addEventListener('click', () => {
      this.entries = [];
      document.getElementById('log_container').innerHTML = '';
    });
    this.connectWs();
  },

  connectWs() {
    const ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onmessage = e => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'comm_log') this.addEntry(msg);
      if (msg.type === 'comm_log_bulk') msg.entries.forEach(ent => this.addEntry(ent));
    };
    ws.onclose = () => setTimeout(() => this.connectWs(), 1000);
  },

  addEntry(msg) {
    this.entries.push(msg);
    const container = document.getElementById('log_container');
    if (!container) return;
    const dir = msg.direction === 'tx' ? '→' : '←';
    const cls = msg.direction === 'tx' ? 'tx' : 'rx';
    const div = document.createElement('div');
    div.className = `log-entry ${cls}`;
    div.textContent = `[${msg.timestamp}] ${dir} ${msg.data}`;
    container.appendChild(div);
    if (document.getElementById('log_autoscroll')?.checked) {
      container.scrollTop = container.scrollHeight;
    }
  }
};
