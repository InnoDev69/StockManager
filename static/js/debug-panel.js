/**
 * Debug Panel para aplicación empaquetada
 * Accesible solo para administradores via Ctrl+Shift+D
 */

class DebugPanel {
    constructor() {
        this.isOpen = false;
        this.logs = [];
        this.autoSend = true;
        this.init();
    }

    init() {
        this.setupConsoleInterception();
        
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.code === 'KeyD') {
                e.preventDefault();
                this.toggle();
            }
        });
    }

    setupConsoleInterception() {
        const originalLog = console.log;
        const originalError = console.error;
        const originalWarn = console.warn;
        const self = this;

        console.log = function(...args) {
            originalLog.apply(console, args);
            self.captureLog('info', args);
        };

        console.error = function(...args) {
            originalError.apply(console, args);
            self.captureLog('error', args);
        };

        console.warn = function(...args) {
            originalWarn.apply(console, args);
            self.captureLog('warning', args);
        };

        window.addEventListener('error', (event) => {
            self.captureLog('error', [
                `Uncaught: ${event.message}`,
                `File: ${event.filename}:${event.lineno}:${event.colno}`
            ]);
        });

        window.addEventListener('unhandledrejection', (event) => {
            self.captureLog('error', [
                `Unhandled Promise Rejection: ${event.reason}`
            ]);
        });
    }

    captureLog(level, args) {
        const message = args.map(arg => {
            if (typeof arg === 'object') {
                return JSON.stringify(arg);
            }
            return String(arg);
        }).join(' ');

        const logEntry = {
            timestamp: new Date().toLocaleTimeString('es-ES'),
            level: level.toUpperCase(),
            message: message,
            context: {
                url: window.location.pathname,
                userAgent: navigator.userAgent
            }
        };

        this.logs.push(logEntry);
        
        if (this.isOpen) {
            this.updatePanelDisplay();
        }

        if (this.autoSend && level === 'error') {
            this.sendToServer(logEntry);
        }
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    open() {
        if (document.getElementById('debug-panel')) {
            this.isOpen = true;
            document.getElementById('debug-panel').style.display = 'flex';
            return;
        }

        this.isOpen = true;
        const panel = document.createElement('div');
        panel.id = 'debug-panel';
        panel.innerHTML = `
            <div style="
                position: fixed;
                bottom: 0;
                right: 0;
                width: 400px;
                height: 300px;
                background: #1e1e1e;
                border: 1px solid #444;
                border-radius: 8px 8px 0 0;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                color: #aaa;
                box-shadow: 0 -2px 10px rgba(0,0,0,0.5);
            ">
                <div style="
                    padding: 8px;
                    background: #252525;
                    border-bottom: 1px solid #444;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <strong style="color: #0ff;"> DEBUG PANEL</strong>
                    <div style="display: flex; gap: 8px;">
                        <button id="debug-clear" style="
                            background: #444;
                            border: none;
                            color: #aaa;
                            padding: 2px 8px;
                            cursor: pointer;
                            border-radius: 3px;
                            font-size: 10px;
                        ">Limpiar</button>
                        <button id="debug-close" style="
                            background: #444;
                            border: none;
                            color: #aaa;
                            padding: 2px 8px;
                            cursor: pointer;
                            border-radius: 3px;
                            font-size: 10px;
                        ">✕</button>
                    </div>
                </div>
                <div id="debug-logs" style="
                    flex: 1;
                    overflow-y: auto;
                    padding: 8px;
                    background: #1e1e1e;
                    line-height: 1.4;
                "></div>
                <div style="
                    padding: 8px;
                    background: #252525;
                    border-top: 1px solid #444;
                    display: flex;
                    gap: 8px;
                ">
                    <label style="display: flex; align-items: center; gap: 4px; color: #0f0; cursor: pointer;">
                        <input type="checkbox" id="debug-autosend" checked style="cursor: pointer;">
                        Auto-send errors
                    </label>
                </div>
            </div>
        `;

        document.body.appendChild(panel);

        document.getElementById('debug-close').onclick = () => this.close();
        document.getElementById('debug-clear').onclick = () => this.clearLogs();
        document.getElementById('debug-autosend').onchange = (e) => {
            this.autoSend = e.target.checked;
        };

        this.updatePanelDisplay();
    }

    close() {
        this.isOpen = false;
        const panel = document.getElementById('debug-panel');
        if (panel) {
            panel.style.display = 'none';
        }
    }

    updatePanelDisplay() {
        const logsDiv = document.getElementById('debug-logs');
        if (!logsDiv) return;

        logsDiv.innerHTML = this.logs
            .map(log => {
                const color = {
                    'ERROR': '#ff6b6b',
                    'WARNING': '#ffd93d',
                    'INFO': '#0ff',
                    'DEBUG': '#888'
                }[log.level] || '#aaa';

                return `<div style="color: ${color}; margin-bottom: 4px;">
                    <span style="color: #666;">[${log.timestamp}]</span>
                    <strong>${log.level}</strong>: ${log.message}
                </div>`;
            })
            .join('');

        logsDiv.scrollTop = logsDiv.scrollHeight;
    }

    clearLogs() {
        this.logs = [];
        const logsDiv = document.getElementById('debug-logs');
        if (logsDiv) {
            logsDiv.innerHTML = '<div style="color: #666;">Panel limpio</div>';
        }
    }

    sendToServer(logEntry) {
        fetch('/api/debug/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logEntry)
        }).catch(err => console.error('Failed to send log:', err));
    }
}

const debugPanel = new DebugPanel();