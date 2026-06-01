/**
 * DebugPanel
 * Panel de depuración para administradores.
 * Activación: Ctrl + Shift + D
 */

(function () {
  'use strict';

  // ─── Constantes ──────────────────────────────────────────────────────────────

  const PANEL_ID       = 'dbg-panel';
  const KEYBIND        = { ctrl: true, shift: true, code: 'KeyD' };
  const MAX_LOGS       = 500;
  const SERVER_LOG_URL = '/api/debug/log';
  const SERVER_CMD_URL = '/api/debug/command';

  const LEVEL_COLOR = {
    ERROR   : '#e06c75',
    WARNING : '#e5c07b',
    INFO    : '#61afef',
    RESULT  : '#98c379',
    COMMAND : '#c678dd',
    DEBUG   : '#5c6370',
  };

  // ─── Estilos ──────────────────────────────────────────────────────────────────

  const STYLES = `
    #dbg-panel *,
    #dbg-panel *::before,
    #dbg-panel *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    #dbg-panel {
      --dbg-bg        : #1a1b26;
      --dbg-surface   : #24283b;
      --dbg-border    : #414868;
      --dbg-text      : #a9b1d6;
      --dbg-text-dim  : #565f89;
      --dbg-accent    : #7aa2f7;
      --dbg-green     : #9ece6a;
      --dbg-font      : 'JetBrains Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
      --dbg-radius    : 6px;
      --dbg-width     : 520px;
      --dbg-height    : 420px;
      --dbg-shadow    : 0 -4px 24px rgba(0, 0, 0, 0.6);

      position         : fixed;
      bottom           : 0;
      right            : 20px;
      width            : var(--dbg-width);
      height           : var(--dbg-height);
      background       : var(--dbg-bg);
      border           : 1px solid var(--dbg-border);
      border-bottom    : none;
      border-radius    : var(--dbg-radius) var(--dbg-radius) 0 0;
      z-index          : 2147483647;
      display          : flex;
      flex-direction   : column;
      font-family      : var(--dbg-font);
      font-size        : 11px;
      color            : var(--dbg-text);
      box-shadow       : var(--dbg-shadow);
      user-select      : none;
    }

    /* ── Header ── */
    #dbg-panel .dbg-header {
      display          : flex;
      align-items      : center;
      justify-content  : space-between;
      padding          : 8px 12px;
      background       : var(--dbg-surface);
      border-bottom    : 1px solid var(--dbg-border);
      border-radius    : var(--dbg-radius) var(--dbg-radius) 0 0;
      flex-shrink      : 0;
    }

    #dbg-panel .dbg-title {
      font-size        : 11px;
      font-weight      : 700;
      letter-spacing   : 0.12em;
      text-transform   : uppercase;
      color            : var(--dbg-accent);
    }

    #dbg-panel .dbg-header-actions {
      display          : flex;
      gap              : 6px;
      align-items      : center;
    }

    /* ── Tabs ── */
    #dbg-panel .dbg-tabs {
      display          : flex;
      background       : var(--dbg-surface);
      border-bottom    : 1px solid var(--dbg-border);
      flex-shrink      : 0;
    }

    #dbg-panel .dbg-tab {
      flex             : 1;
      padding          : 7px 0;
      background       : transparent;
      border           : none;
      border-bottom    : 2px solid transparent;
      color            : var(--dbg-text-dim);
      font-family      : var(--dbg-font);
      font-size        : 10px;
      font-weight      : 600;
      letter-spacing   : 0.08em;
      text-transform   : uppercase;
      cursor           : pointer;
      transition       : color 0.15s, border-color 0.15s;
    }

    #dbg-panel .dbg-tab:hover {
      color            : var(--dbg-text);
    }

    #dbg-panel .dbg-tab.active {
      color            : var(--dbg-accent);
      border-bottom-color: var(--dbg-accent);
    }

    /* ── Log Output ── */
    #dbg-panel .dbg-output {
      flex             : 1;
      overflow-y       : auto;
      padding          : 10px 12px;
      line-height      : 1.6;
      scrollbar-width  : thin;
      scrollbar-color  : var(--dbg-border) transparent;
    }

    #dbg-panel .dbg-output::-webkit-scrollbar {
      width            : 4px;
    }

    #dbg-panel .dbg-output::-webkit-scrollbar-thumb {
      background       : var(--dbg-border);
      border-radius    : 2px;
    }

    #dbg-panel .dbg-entry {
      display          : flex;
      gap              : 8px;
      margin-bottom    : 3px;
      word-break       : break-word;
      white-space      : pre-wrap;
      user-select      : text;
    }

    #dbg-panel .dbg-entry-time {
      flex-shrink      : 0;
      color            : var(--dbg-text-dim);
      font-size        : 10px;
      padding-top      : 1px;
    }

    #dbg-panel .dbg-entry-level {
      flex-shrink      : 0;
      font-weight      : 700;
      font-size        : 10px;
      min-width        : 52px;
      padding-top      : 1px;
    }

    #dbg-panel .dbg-entry-msg {
      flex             : 1;
    }

    /* ── Footer ── */
    #dbg-panel .dbg-footer {
      padding          : 8px 12px;
      background       : var(--dbg-surface);
      border-top       : 1px solid var(--dbg-border);
      display          : flex;
      flex-direction   : column;
      gap              : 6px;
      flex-shrink      : 0;
    }

    #dbg-panel .dbg-input-row {
      display          : flex;
      align-items      : center;
      gap              : 8px;
    }

    #dbg-panel .dbg-prompt {
      color            : var(--dbg-green);
      font-weight      : 700;
      flex-shrink      : 0;
    }

    #dbg-panel .dbg-input {
      flex             : 1;
      background       : transparent;
      border           : none;
      color            : var(--dbg-green);
      font-family      : var(--dbg-font);
      font-size        : 11px;
      outline          : none;
    }

    #dbg-panel .dbg-input::placeholder {
      color            : var(--dbg-text-dim);
    }

    #dbg-panel .dbg-autosend-row {
      display          : flex;
      align-items      : center;
      gap              : 6px;
      color            : var(--dbg-text-dim);
      font-size        : 10px;
    }

    #dbg-panel .dbg-autosend-row input[type="checkbox"] {
      cursor           : pointer;
      accent-color     : var(--dbg-accent);
    }

    /* ── Buttons ── */
    #dbg-panel .dbg-btn {
      background       : transparent;
      border           : 1px solid var(--dbg-border);
      color            : var(--dbg-text-dim);
      padding          : 3px 10px;
      cursor           : pointer;
      border-radius    : 3px;
      font-family      : var(--dbg-font);
      font-size        : 10px;
      font-weight      : 600;
      letter-spacing   : 0.05em;
      transition       : color 0.15s, border-color 0.15s;
    }

    #dbg-panel .dbg-btn:hover {
      color            : var(--dbg-text);
      border-color     : var(--dbg-text-dim);
    }

    #dbg-panel .dbg-btn-close:hover {
      color            : #e06c75;
      border-color     : #e06c75;
    }

    #dbg-panel .dbg-empty {
      color            : var(--dbg-text-dim);
      padding          : 4px 0;
    }

    /* ── Scrollbar ── */
    #dbg-panel .dbg-output::-webkit-scrollbar-track {
      background       : transparent;
    }
  `;

  // ─── Helpers ──────────────────────────────────────────────────────────────────

  function timestamp() {
    return new Date().toLocaleTimeString('es-ES', { hour12: false });
  }

  function safeStringify(value) {
    if (typeof value === 'object' && value !== null) {
      try { return JSON.stringify(value, null, 2); } catch { return String(value); }
    }
    return String(value);
  }

  function injectStyles() {
    if (document.getElementById('dbg-styles')) return;
    const style = document.createElement('style');
    style.id = 'dbg-styles';
    style.textContent = STYLES;
    document.head.appendChild(style);
  }

  // ─── Clase Principal ──────────────────────────────────────────────────────────

  class DebugPanel {
    constructor() {
      this._isOpen        = false;
      this._logs          = [];
      this._history       = [];
      this._historyIdx    = -1;
      this._currentTab    = 'logs';
      this._autoSend      = true;

      this._bindConsole();
      this._bindPageEvents();
      this._bindKeybind();
    }

    // ── Inicialización ──────────────────────────────────────────────────────────

    _bindKeybind() {
      document.addEventListener('keydown', (e) => {
        if (e.ctrlKey === KEYBIND.ctrl && e.shiftKey === KEYBIND.shift && e.code === 
          KEYBIND.code && window.ROLES?.ROOT === window.APP?.role) {
          e.preventDefault();
          this.toggle();
        }
      });
    }

    _bindPageEvents() {
      window.addEventListener('beforeunload', () => this.close());

      const self = this;
      const patchHistory = (method) => {
        const original = history[method];
        history[method] = function (...args) {
          self.close();
          return original.apply(this, args);
        };
      };

      patchHistory('pushState');
      patchHistory('replaceState');
    }

    _bindConsole() {
      const self = this;
      const methods = { log: 'INFO', error: 'ERROR', warn: 'WARNING' };

      for (const [name, level] of Object.entries(methods)) {
        const original = console[name].bind(console);
        console[name] = (...args) => {
          original(...args);
          self._capture(level, args);
        };
      }

      window.addEventListener('error', (ev) => {
        self._capture('ERROR', [
          `Uncaught: ${ev.message}`,
          `Source: ${ev.filename}:${ev.lineno}:${ev.colno}`,
        ]);
      });

      window.addEventListener('unhandledrejection', (ev) => {
        self._capture('ERROR', [`Unhandled Promise Rejection: ${ev.reason}`]);
      });
    }

    // ── Captura de Logs ─────────────────────────────────────────────────────────

    _capture(level, args) {
      const message = args.map(safeStringify).join(' ');
      const entry = {
        timestamp : timestamp(),
        level     : level.toUpperCase(),
        message,
      };

      this._logs.push(entry);
      if (this._logs.length > MAX_LOGS) this._logs.shift();

      if (this._isOpen) this._renderLogs();
      if (this._autoSend && level === 'ERROR') this._sendToServer(entry);
    }

    _pushEntry(level, message) {
      this._capture(level, [message]);
    }

    // ── Comandos ────────────────────────────────────────────────────────────────

    executeCommand(raw) {
      const cmd = raw.trim();
      if (!cmd) return;

      this._history.unshift(cmd);
      this._historyIdx = -1;
      this._pushEntry('COMMAND', `> ${cmd}`);

      const dispatch = {
        clear   : () => this._clearLogs(),
        help    : () => this._showHelp(),
        vars    : () => this._showVars(),
        history : () => this._showHistory(),
      };

      if (cmd.startsWith('server:')) {
        this._runServer(cmd.slice(7).trim());
      } else if (cmd.startsWith('client:')) {
        this._runClient(cmd.slice(7).trim());
      } else if (dispatch[cmd]) {
        dispatch[cmd]();
      } else {
        this._runClient(cmd);
      }

      if (this._isOpen) this._renderLogs();
    }

    _runClient(code) {
      try {
        // eslint-disable-next-line no-eval
        const result = eval(`(${code})`);
        this._pushEntry('RESULT', safeStringify(result));
      } catch (e) {
        this._pushEntry('ERROR', `Client error: ${e.message}`);
      }
    }

    _runServer(code) {
      fetch(SERVER_CMD_URL, {
        method  : 'POST',
        headers : { 'Content-Type': 'application/json' },
        body    : JSON.stringify({ code }),
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.error) {
            this._pushEntry('ERROR', `Server error: ${data.error}`);
          } else {
            this._pushEntry('RESULT', data.output ?? data.result ?? 'OK');
          }
          if (this._isOpen) this._renderLogs();
        })
        .catch((err) => this._pushEntry('ERROR', `Request failed: ${err.message}`));
    }

    // ── Comandos integrados ─────────────────────────────────────────────────────

    _showHelp() {
      const lines = [
        'COMMANDS',
        '  help              Show this message',
        '  clear             Clear log output',
        '  vars              Show client environment',
        '  history           Show command history',
        '',
        'EXECUTION',
        '  client:<code>     Evaluate JavaScript (eval)',
        '  server:<code>     Execute Python on server',
        '  <code>            Defaults to client execution',
        '',
        'EXAMPLES',
        '  > document.cookie',
        '  > client: window.APP',
        '  > server: import sys; print(sys.version)',
        '  > fetch("/api/ping").then(r => r.json())',
      ].join('\n');
      this._pushEntry('INFO', lines);
    }

    _showVars() {
      const info = {
        pathname    : window.location.pathname,
        href        : window.location.href,
        userAgent   : navigator.userAgent,
        APP         : typeof window.APP !== 'undefined' ? window.APP : undefined,
        localStorage: typeof localStorage !== 'undefined' ? 'available' : 'unavailable',
      };
      this._pushEntry('INFO', safeStringify(info));
    }

    _showHistory() {
      const out = this._history.length
        ? this._history.map((c, i) => `${String(i + 1).padStart(2, ' ')}. ${c}`).join('\n')
        : 'No history.';
      this._pushEntry('INFO', out);
    }

    // ── Interfaz ────────────────────────────────────────────────────────────────

    toggle() {
      this._isOpen ? this.close() : this.open();
    }

    open() {
      injectStyles();

      const existing = document.getElementById(PANEL_ID);
      if (existing) {
        existing.style.display = 'flex';
        this._isOpen = true;
        this._focusInput();
        return;
      }

      this._isOpen = true;
      const panel = document.createElement('div');
      panel.id = PANEL_ID;
      panel.innerHTML = this._template();
      document.body.appendChild(panel);

      this._attachEvents(panel);
      this._renderLogs();
      this._focusInput();
    }

    close() {
      this._isOpen = false;
      const panel = document.getElementById(PANEL_ID);
      if (panel) panel.remove();
    }

    _focusInput() {
      const input = document.getElementById('dbg-input');
      if (input) input.focus();
    }

    // ── Plantilla HTML ──────────────────────────────────────────────────────────

    _template() {
      return `
        <div class="dbg-header">
          <span class="dbg-title">Debug Panel</span>
          <div class="dbg-header-actions">
            <button class="dbg-btn" id="dbg-clear-btn">Clear</button>
            <button class="dbg-btn dbg-btn-close" id="dbg-close-btn">Close</button>
          </div>
        </div>

        <div class="dbg-tabs" style="display: none;">
          <button class="dbg-tab active" data-tab="logs">Logs</button>
          <button class="dbg-tab" data-tab="console">Console</button>
        </div>

        <div class="dbg-output" id="dbg-output"></div>

        <div class="dbg-footer">
          <div class="dbg-input-row">
            <span class="dbg-prompt">&gt;</span>
            <input
              id="dbg-input"
              class="dbg-input"
              type="text"
              autocomplete="off"
              spellcheck="false"
              placeholder="Type a command  (help for reference)"
            />
          </div>
          <label class="dbg-autosend-row">
            <input type="checkbox" id="dbg-autosend" checked />
            Auto-send errors to server
          </label>
        </div>
      `;
    }

    // ── Eventos de UI ───────────────────────────────────────────────────────────

    _attachEvents(panel) {
      panel.querySelector('#dbg-close-btn').addEventListener('click', () => this.close());
      panel.querySelector('#dbg-clear-btn').addEventListener('click', () => this._clearLogs());
      panel.querySelector('#dbg-autosend').addEventListener('change', (e) => {
        this._autoSend = e.target.checked;
      });

      panel.querySelectorAll('.dbg-tab').forEach((btn) => {
        btn.addEventListener('click', () => this._switchTab(btn.dataset.tab, panel));
      });

      const input = panel.querySelector('#dbg-input');
      input.addEventListener('keydown', (e) => this._handleInput(e, input));
    }

    _handleInput(e, input) {
      if (e.key === 'Enter') {
        const cmd = input.value;
        input.value = '';
        this.executeCommand(cmd);
        return;
      }

      if (e.key === 'ArrowUp') {
        e.preventDefault();
        this._historyIdx = Math.min(this._historyIdx + 1, this._history.length - 1);
        input.value = this._history[this._historyIdx] ?? '';
        return;
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        this._historyIdx = Math.max(this._historyIdx - 1, -1);
        input.value = this._historyIdx >= 0 ? (this._history[this._historyIdx] ?? '') : '';
      }
    }

    _switchTab(tab, panel) {
      this._currentTab = tab;
      panel.querySelectorAll('.dbg-tab').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
      });
      this._renderLogs();
    }

    // ── Renderizado ─────────────────────────────────────────────────────────────

    _renderLogs() {
      const output = document.getElementById('dbg-output');
      if (!output) return;

      if (this._logs.length === 0) {
        output.innerHTML = '<span class="dbg-empty">No log entries.</span>';
        return;
      }

      output.innerHTML = this._logs.map((entry) => {
        const color = LEVEL_COLOR[entry.level] ?? LEVEL_COLOR.DEBUG;
        return `
          <div class="dbg-entry">
            <span class="dbg-entry-time">${entry.timestamp}</span>
            <span class="dbg-entry-level" style="color:${color}">${entry.level}</span>
            <span class="dbg-entry-msg">${escapeHtml(entry.message)}</span>
          </div>
        `;
      }).join('');

      output.scrollTop = output.scrollHeight;
    }

    _clearLogs() {
      this._logs = [];
      const output = document.getElementById('dbg-output');
      if (output) output.innerHTML = '<span class="dbg-empty">Log cleared.</span>';
    }

    // ── Servidor ────────────────────────────────────────────────────────────────

    _sendToServer(entry) {
      fetch(SERVER_LOG_URL, {
        method  : 'POST',
        headers : { 'Content-Type': 'application/json' },
        body    : JSON.stringify(entry),
      }).catch(() => { /* silently ignore */ });
    }
  }

  // ─── Bootstrap ───────────────────────────────────────────────────────────────

  window.__debugPanel = new DebugPanel();

})();