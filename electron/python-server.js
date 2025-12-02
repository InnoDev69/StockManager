const { spawn } = require('child_process');
const path = require('path');
const findFreePort = require('find-free-port');

class PythonServer {
  constructor() {
    this.process = null;
    this.port = null;
  }

  async start() {
    // Encuentra puerto libre
    const [port] = await findFreePort(5000, 5100);
    this.port = port;

    // Ruta al ejecutable empaquetado
    const isDev = !require('electron').app.isPackaged;
    const serverPath = isDev
      ? path.join(__dirname, '..', 'main.py')
      : path.join(process.resourcesPath, 'server', 'stock-manager-server');

    const args = isDev ? ['main.py'] : [];
    const command = isDev ? 'python' : serverPath;

    this.process = spawn(command, args, {
      env: { ...process.env, FLASK_PORT: port.toString() },
      cwd: isDev ? path.join(__dirname, '..') : process.resourcesPath
    });

    this.process.stdout.on('data', (data) => {
      console.log(`[Python] ${data}`);
    });

    this.process.stderr.on('data', (data) => {
      console.error(`[Python Error] ${data}`);
    });

    // Espera a que Flask inicie
    await this.waitForServer(port);
    return `http://127.0.0.1:${port}`;
  }

  async waitForServer(port, timeout = 10000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      try {
        const http = require('http');
        await new Promise((resolve, reject) => {
          http.get(`http://127.0.0.1:${port}`, resolve).on('error', reject);
        });
        return;
      } catch {
        await new Promise(r => setTimeout(r, 200));
      }
    }
    throw new Error('Flask server failed to start');
  }

  stop() {
    if (this.process) {
      this.process.kill();
    }
  }
}

module.exports = PythonServer;