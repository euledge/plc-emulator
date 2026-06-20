const ScriptEditor = {
  scriptList: [],
  current: null,

  async init() {
    const container = document.getElementById('page-scripts');
    container.innerHTML = `
      <div class="panel">
        <h3 data-i18n="nav.scripts">Scripts</h3>
        <div class="form-row">
          <div class="form-group">
            <label>Script Name</label>
            <input type="text" id="script_name" placeholder="my_script.yaml">
          </div>
          <div class="form-group">
            <label>&nbsp;</label>
            <div class="btn-row">
              <button id="script_new">New</button>
              <button id="script_load">Load</button>
              <button id="script_save">Save</button>
              <button id="script_start" class="secondary" data-i18n="script.start">Start</button>
              <button id="script_stop" class="secondary" data-i18n="script.stop">Stop</button>
            </div>
          </div>
        </div>
        <textarea id="script_editor" placeholder="# YAML script"></textarea>
      </div>
      <div class="panel">
        <h3>Saved Scripts</h3>
        <div id="script_list"></div>
      </div>`;

    document.getElementById('script_new').addEventListener('click', () => this.newScript());
    document.getElementById('script_load').addEventListener('click', () => this.loadScript());
    document.getElementById('script_save').addEventListener('click', () => this.saveScript());
    document.getElementById('script_start').addEventListener('click', () => this.startScript());
    document.getElementById('script_stop').addEventListener('click', () => this.stopScript());

    await this.refreshList();
  },

  async refreshList() {
    const resp = await fetch('/api/scripts');
    const scripts = await resp.json();
    const container = document.getElementById('script_list');
    container.innerHTML = scripts.map(s =>
      `<div style="padding:0.3rem;border-bottom:1px solid #0f3460;cursor:pointer" onclick="ScriptEditor.loadByName('${s}')">${s}</div>`
    ).join('');
  },

  newScript() {
    document.getElementById('script_name').value = '';
    document.getElementById('script_editor').value = '';
    this.current = null;
  },

  async loadScript() {
    const name = document.getElementById('script_name').value.trim();
    if (!name) return;
    const resp = await fetch(`/api/scripts/${encodeURIComponent(name)}`);
    if (!resp.ok) return;
    const data = await resp.json();
    document.getElementById('script_editor').value = data.content;
    this.current = name;
  },

  loadByName(name) {
    document.getElementById('script_name').value = name;
    this.loadScript();
  },

  async saveScript() {
    const name = document.getElementById('script_name').value.trim();
    if (!name) return;
    const content = document.getElementById('script_editor').value;
    await fetch(`/api/scripts/${encodeURIComponent(name)}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ content })
    });
    this.current = name;
    await this.refreshList();
  },

  async startScript() {
    const name = document.getElementById('script_name').value.trim();
    if (!name) return;
    await fetch(`/api/scripts/${encodeURIComponent(name)}/start`, { method: 'POST' });
  },

  async stopScript() {
    const name = document.getElementById('script_name').value.trim();
    if (!name) return;
    await fetch(`/api/scripts/${encodeURIComponent(name)}/stop`, { method: 'POST' });
  }
};
