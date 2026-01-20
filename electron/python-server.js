const { app } = require('electron');
const { spawn, exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const findFreePort = require('find-free-port');

class PythonServer {
  constructor() {
    this.child = null;
    this.port = null;
    this.pid = null;
  }

  async start() {
    if (this.child) return this.url();

    this.port = await this._getPort();

    const binName = process.platform === 'win32'
      ? 'stock-manager-server.exe'
      : 'stock-manager-server';

    const binPath = app.isPackaged
      ? path.join(process.resourcesPath, 'server', binName)
      : path.join(__dirname, '..', 'dist', binName);

    if (!fs.existsSync(binPath)) {
      throw new Error(`No se encontró el binario del servidor en: ${binPath}`);
    }

    this.child = spawn(binPath, ['--port', String(this.port)], {
      stdio: 'ignore',  // Cambiado: evita problemas con stdio en Windows
      windowsHide: true,
      shell: false
    });

    this.pid = this.child.pid;
    console.log(`Servidor iniciado con PID: ${this.pid}`);

    this.child.on('exit', (code) => {
      console.log(`Servidor terminó (código: ${code})`);
      this.child = null;
      this.pid = null;
    });

    this.child.on('error', (err) => {
      console.error('Error en servidor:', err);
    });

    await new Promise(r => setTimeout(r, 1000));
    return this.url();
  }

  url() {
    return `http://127.0.0.1:${this.port}`;
  }

  stop() {
    if (!this.pid) return;

    console.log(`Deteniendo servidor (PID: ${this.pid})...`);

    if (process.platform === 'win32') {
      // Windows: taskkill con /T mata todo el arbol
      exec(`taskkill /PID ${this.pid} /T /F`, (err) => {
        if (err) {
          console.error('Error taskkill:', err.message);
        } else {
          console.log('Servidor detenido correctamente');
        }
      });
    } else {
      // Linux/macOS
      try {
        process.kill(this.pid, 'SIGTERM');
        setTimeout(() => {
          try {
            process.kill(this.pid, 0);
            process.kill(this.pid, 'SIGKILL');
          } catch (e) {}
        }, 500);
      } catch (e) {}
    }

    this.child = null;
    this.pid = null;
  }

  async _getPort() {
    const [port] = await findFreePort(5000);
    return port;
  }
}

module.exports = PythonServer;