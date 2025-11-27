const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
let pyProc;
let mainWin;

function startFlask() {
  pyProc = spawn('python3', [path.join(__dirname, '..', 'main.py')], {
    env: { ...process.env }
  });
  pyProc.stdout.on('data', d => process.stdout.write('[FLASK] ' + d));
  pyProc.stderr.on('data', d => process.stderr.write('[FLASK ERR] ' + d));
}

function createWindow() {
  mainWin = new BrowserWindow({
    width: 1100,
    height: 750,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  mainWin.loadURL('http://127.0.0.1:5000/');
}

app.whenReady().then(() => {
  startFlask();
  // Pequeño retry para esperar Flask (simple, sin wait-on)
  const tryConnect = () => {
    fetch('http://127.0.0.1:5000/login')
      .then(() => createWindow())
      .catch(() => setTimeout(tryConnect, 400));
  };
  tryConnect();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (pyProc) pyProc.kill('SIGTERM');
});