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
              <select id="script_template" style="padding:0.3rem 0.5rem;background:#0f3460;color:#e0e0e0;border:1px solid #333;border-radius:4px;font-size:0.85rem;">
                <option value="">-- Template --</option>
              </select>
              <button id="script_load_template" class="secondary" data-i18n="script.load_template">Load Template</button>
              <button id="script_validate" class="secondary" data-i18n="script.validate">Validate</button>
              <button id="script_start" class="secondary" data-i18n="script.start">Start</button>
              <button id="script_pause" class="secondary" data-i18n="script.pause">Pause</button>
              <button id="script_stop" class="secondary" data-i18n="script.stop">Stop</button>
              <span id="script_status" style="margin-left:auto;padding:0.3rem 0.6rem;border-radius:4px;font-weight:bold;color:#888;">stopped</span>
            </div>
          </div>
        </div>
        <div id="script_validation_result" style="margin-bottom:0.5rem;padding:0.4rem 0.8rem;border-radius:4px;display:none;font-family:monospace;font-size:0.85rem;"></div>
        <div class="editor-container" style="display:flex;border:1px solid #0f3460;border-radius:4px;background:#0f3460;min-height:350px;overflow:hidden;position:relative;">
          <div id="editor_lines" style="width:45px;padding:0.5rem 0.3rem;text-align:right;background:#16213e;color:#666;font-family:monospace;font-size:0.85rem;line-height:1.5;user-select:none;border-right:1px solid #0f3460;white-space:pre-wrap;overflow:hidden;box-sizing:border-box;">1</div>
          <div style="position:relative;flex:1;min-height:350px;">
            <pre id="editor_highlight" aria-hidden="true" style="margin:0;padding:0.5rem;position:absolute;top:0;left:0;right:0;bottom:0;font-family:monospace;font-size:0.85rem;line-height:1.5;color:#e0e0e0;white-space:pre-wrap;word-wrap:break-word;pointer-events:none;overflow:hidden;box-sizing:border-box;"></pre>
            <textarea id="script_editor" placeholder="# YAML script" spellcheck="false" style="margin:0;padding:0.5rem;position:absolute;top:0;left:0;width:100%;height:100%;background:transparent;color:transparent;caret-color:#4ecca3;font-family:monospace;font-size:0.85rem;line-height:1.5;border:none;outline:none;resize:none;white-space:pre-wrap;word-wrap:break-word;box-sizing:border-box;overflow:auto;"></textarea>
          </div>
        </div>
      </div>
      <div class="panel">
        <div style="display:flex;gap:2rem;">
          <div style="flex:1;">
            <h3>Saved Scripts</h3>
            <div id="script_list"></div>
          </div>
          <div style="flex:1;">
            <h3 data-i18n="script.templates">Preset Templates</h3>
            <div id="template_list"></div>
          </div>
        </div>
      </div>`;

    document.getElementById('script_new').addEventListener('click', () => this.newScript());
    document.getElementById('script_load').addEventListener('click', () => this.loadScript());
    document.getElementById('script_save').addEventListener('click', () => this.saveScript());
    document.getElementById('script_load_template').addEventListener('click', () => this.loadTemplate());
    document.getElementById('script_validate').addEventListener('click', () => this.validateScript());
    document.getElementById('script_start').addEventListener('click', () => this.startScript());
    document.getElementById('script_pause').addEventListener('click', () => this.pauseScript());
    document.getElementById('script_stop').addEventListener('click', () => this.stopScript());
    const editor = document.getElementById('script_editor');
    if (editor) {
      editor.addEventListener('input', () => this.updateEditor());
      editor.addEventListener('scroll', () => this.updateEditor());
    }
    await this.refreshList();
    await this.refreshTemplates();
    this.updateEditor();
  },

  async refreshList() {
    const resp = await fetch('/api/scripts');
    const scripts = await resp.json();
    const container = document.getElementById('script_list');
    container.innerHTML = scripts.map(s =>
      `<div style="padding:0.3rem;border-bottom:1px solid #0f3460;cursor:pointer" onclick="ScriptEditor.loadByName('${s}')">${s}</div>`
    ).join('');
  },

  async refreshTemplates() {
    try {
      const resp = await fetch('/api/scripts/templates');
      if (!resp.ok) return;
      const templates = await resp.json();
      const select = document.getElementById('script_template');
      if (select) {
        select.innerHTML = '<option value="">-- Template --</option>' +
          templates.map(t => `<option value="${t}">${t}</option>`).join('');
      }
      const container = document.getElementById('template_list');
      if (container) {
        container.innerHTML = templates.map(t =>
          `<div style="padding:0.3rem;border-bottom:1px solid #0f3460;cursor:pointer;color:#4ecca3;" onclick="ScriptEditor.loadTemplate('${t}')">${t}</div>`
        ).join('');
      }
    } catch (e) {}
  },

  async loadTemplate(name) {
    const templateName = name || document.getElementById('script_template')?.value;
    if (!templateName) return;
    try {
      const resp = await fetch(`/api/scripts/templates/${encodeURIComponent(templateName)}`);
      if (!resp.ok) return;
      const data = await resp.json();
      document.getElementById('script_name').value = data.name;
      document.getElementById('script_editor').value = data.content;
      this.current = null;
      this.setStatus('stopped');
      this.updateEditor();
    } catch (e) {}
  },

  newScript() {
    document.getElementById('script_name').value = '';
    document.getElementById('script_editor').value = '';
    this.current = null;
    this.setStatus('stopped');
    const res = document.getElementById('script_validation_result');
    if (res) res.style.display = 'none';
    this.updateEditor();
  },

  async loadScript() {
    const name = document.getElementById('script_name').value.trim();
    if (!name) return;
    const resp = await fetch(`/api/scripts/${encodeURIComponent(name)}`);
    if (!resp.ok) return;
    const data = await resp.json();
    document.getElementById('script_editor').value = data.content;
    this.current = name;
    await this.refreshStatus();
    this.updateEditor();
  },
  loadByName(name) {
    document.getElementById('script_name').value = name;
    this.loadScript();
  },

  async saveScript() {
    let name = document.getElementById('script_name').value.trim();
    if (!name) {
      name = 'untitled.yaml';
      document.getElementById('script_name').value = name;
    } else if (!name.endsWith('.yaml') && !name.endsWith('.yml')) {
      name = `${name}.yaml`;
      document.getElementById('script_name').value = name;
    }
    const content = document.getElementById('script_editor').value;
    await fetch(`/api/scripts/${encodeURIComponent(name)}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ content })
    });
    this.current = name;
    await this.refreshList();
  },

  async validateScript() {
    const content = document.getElementById('script_editor').value;
    const resultEl = document.getElementById('script_validation_result');
    if (!resultEl) return false;
    try {
      const resp = await fetch('/api/scripts/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
      });
      const data = await resp.json();
      resultEl.style.display = 'block';
      if (data.valid) {
        resultEl.style.background = 'rgba(78, 204, 163, 0.2)';
        resultEl.style.color = '#8be6bd';
        resultEl.style.border = '1px solid #4ecca3';
        resultEl.textContent = '✓ Script is valid';
        return true;
      } else {
        resultEl.style.background = 'rgba(255, 99, 99, 0.2)';
        resultEl.style.color = '#ff8a8a';
        resultEl.style.border = '1px solid #ff6363';
        resultEl.innerHTML = `✗ Validation failed:<br>${(data.errors || []).join('<br>')}`;
        return false;
      }
    } catch (e) {
      resultEl.style.display = 'block';
      resultEl.style.color = '#ff8a8a';
      resultEl.textContent = `Validation error: ${e.message}`;
      return false;
    }
  },

  async startScript() {
    let name = document.getElementById('script_name').value.trim();
    if (!name) {
      name = 'untitled.yaml';
      document.getElementById('script_name').value = name;
    } else if (!name.endsWith('.yaml') && !name.endsWith('.yml')) {
      name = `${name}.yaml`;
      document.getElementById('script_name').value = name;
    }
    const content = document.getElementById('script_editor').value;
    const valid = await this.validateScript();
    if (valid === false) return;

    await this.saveScript();

    const resp = await fetch(`/api/scripts/${encodeURIComponent(name)}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      alert(err.detail || 'Failed to start script');
    }
    this.current = name;
    await this.refreshStatus();
  },

  async pauseScript() {
    let name = document.getElementById('script_name').value.trim() || this.current;
    if (!name) return;
    if (!name.endsWith('.yaml') && !name.endsWith('.yml')) name = `${name}.yaml`;
    await fetch(`/api/scripts/${encodeURIComponent(name)}/pause`, { method: 'POST' });
    await this.refreshStatus();
  },

  async stopScript() {
    let name = document.getElementById('script_name').value.trim() || this.current;
    if (!name) return;
    if (!name.endsWith('.yaml') && !name.endsWith('.yml')) name = `${name}.yaml`;
    await fetch(`/api/scripts/${encodeURIComponent(name)}/stop`, { method: 'POST' });
    await this.refreshStatus();
  },

  setStatus(status) {
    const statusEl = document.getElementById('script_status');
    if (!statusEl) return;
    statusEl.textContent = status;
    if (status === 'running') statusEl.style.color = '#8be6bd';
    else if (status === 'paused') statusEl.style.color = '#ffcc00';
    else statusEl.style.color = '#888';
  },

  async refreshStatus() {
    let name = document.getElementById('script_name').value.trim() || this.current;
    if (!name) {
      this.setStatus('stopped');
      return;
    }
    if (!name.endsWith('.yaml') && !name.endsWith('.yml')) name = `${name}.yaml`;
    try {
      const resp = await fetch(`/api/scripts/${encodeURIComponent(name)}/status`);
      if (resp.ok) {
        const data = await resp.json();
        this.setStatus(data.status);
      }
    } catch (e) {}
  },

  highlightYaml(text) {
    if (!text) return '';
    const escaped = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    return escaped.split('\n').map(line => {
      const commentIdx = line.indexOf('#');
      let codePart = commentIdx >= 0 ? line.slice(0, commentIdx) : line;
      const commentPart = commentIdx >= 0 ? `<span style="color:#6c757d;font-style:italic;">${line.slice(commentIdx)}</span>` : '';
      codePart = codePart.replace(/^(\s*(?:-\s*)?)([a-zA-Z0-9_-]+)(:)/g, '$1\u0001$2\u0002$3');
      codePart = codePart.replace(/(["'])(?:(?=(\\?))\2.)*?\1/g, '\u0003$&\u0004');
      codePart = codePart.replace(/\b(true|false)\b/gi, '\u0005$&\u0006');
      codePart = codePart.replace(/\b(\d+)\b/g, '\u0007$1\u0008');
      codePart = codePart
        .replace(/\u0001(.*?)\u0002/g, '<span style="color:#4fc3f7;font-weight:bold;">$1</span>')
        .replace(/\u0003(.*?)\u0004/g, '<span style="color:#ffe082;">$1</span>')
        .replace(/\u0005(.*?)\u0006/g, '<span style="color:#ba68c8;">$1</span>')
        .replace(/\u0007(.*?)\u0008/g, '<span style="color:#f06292;">$1</span>');
      return codePart + commentPart;
    }).join('\n') + '\n';
  },

  updateEditor() {
    const editor = document.getElementById('script_editor');
    const highlight = document.getElementById('editor_highlight');
    const lines = document.getElementById('editor_lines');
    if (!editor || !highlight || !lines) return;

    const val = editor.value;
    highlight.innerHTML = this.highlightYaml(val);
    highlight.scrollTop = editor.scrollTop;
    highlight.scrollLeft = editor.scrollLeft;

    const lineCount = Math.max(1, (val.match(/\n/g) || []).length + 1);
    lines.textContent = Array.from({ length: lineCount }, (_, i) => i + 1).join('\n');
    lines.scrollTop = editor.scrollTop;
  }
};
