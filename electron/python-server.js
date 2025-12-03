const { app } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const findFreePort = require('find-free-port');

class PythonServer {
  constructor() {
    this.child = null;
    this.port = null;
  }

  async start() {
    if (this.child) return this.url();

    this.port = await this._getPort();

    // Usa .exe en Windows
    const binName = process.platform === 'win32'
      ? 'stock-manager-server.exe'
      : 'stock-manager-server';

    // En dev: usa dist/<binario>; en producción: resources/server/<binario>
    const binPath = app.isPackaged
      ? path.join(process.resourcesPath, 'server', binName)
      : path.join(__dirname, '..', 'dist', binName);

    if (!fs.existsSync(binPath)) {
      throw new Error(`No se encontró el binario del servidor en: ${binPath}`);
    }

    this.child = spawn(binPath, ['--port', String(this.port)], {
      stdio: 'inherit',
      windowsHide: true,
      shell: false
    });

    this.child.on('exit', () => { this.child = null; });

    // Espera breve a que el server esté listo; sustituye por un healthcheck si tienes endpoint
    await new Promise(r => setTimeout(r, 800));
    return this.url();
  }

  url() {
    return `http://127.0.0.1:${this.port}`;
  }

  stop() {
    if (this.child) {
      this.child.kill();
      this.child = null;
    }
  }

  async _getPort() {
    const [port] = await findFreePort(5000);
    return port;
  }
}

module.exports = PythonServer;