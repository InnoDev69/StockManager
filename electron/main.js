const { app, BrowserWindow } = require('electron');
const path = require('path');
const PythonServer = require('./python-server');

let mainWindow;
let server;

async function createWindow() {
  // Inicia el servidor Flask
  server = new PythonServer();
  const serverUrl = await server.start();

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    icon: path.join(__dirname, '..', 'static', 'icon.png')
  });

  // Carga la app Flask
  mainWindow.loadURL(serverUrl);

  // DevTools en desarrollo
  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (server) server.stop();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  if (server) server.stop();
});