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
          <button id="log_save" class="secondary" data-i18n="log.save">Save Log</button>
        </div>
        <div id="log_container" style="max-height:60vh;overflow:auto;background:#0f3460;padding:0.5rem;border-radius:4px;font-family:monospace;font-size:0.8rem;"></div>
      </div>`;
    document.getElementById('log_clear').addEventListener('click', () => {
      this.entries = [];
      document.getElementById('log_container').innerHTML = '';
    });
    document.getElementById('log_save').addEventListener('click', () => this.saveLog());
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
    const cmdBadge = msg.command ? ` [${msg.command}]` : '';
    div.textContent = `[${msg.timestamp}] ${dir}${cmdBadge} ${msg.data}`;
    container.appendChild(div);
    if (document.getElementById('log_autoscroll')?.checked) {
      container.scrollTop = container.scrollHeight;
    }
  },

  saveLog() {
    const lines = this.entries.map(msg => {
      const dir = msg.direction === 'tx' ? '→' : '←';
      const cmdBadge = msg.command ? ` [${msg.command}]` : '';
      return `[${msg.timestamp}] ${dir}${cmdBadge} ${msg.data}`;
    });
    const text = lines.join('\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `comm_log_${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
};
