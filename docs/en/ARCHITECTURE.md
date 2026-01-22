# Architecture (Dev)

## Overview

StockManager is a desktop app (Electron) that renders a local web app (Flask). Electron starts a separate process (the packaged Python server) and opens a window pointing to `http://127.0.0.1:<port>`.

## Components

### Electron (desktop shell)

- Main process: creates the window and loads the server URL.
  - Entrypoint: [electron/main.js](../../electron/main.js)
- Server launcher: resolves a free port, executes the server binary, and handles shutdown.
  - File: [electron/python-server.js](../../electron/python-server.js)

### Flask server (UI + API)

- The Flask app serves:
  - HTML views (Jinja) from `templates/`
  - Static assets from `static/`
  - A JSON REST API under `/api` via a blueprint
- Entrypoint: [main.py](../../main.py)
- API blueprint: [api/API.py](../../api/API.py)

### Persistence (SQLite)

- Global `db` instance is initialized when importing `bd/bdInstance.py`.
  - File: [bd/bdInstance.py](../../bd/bdInstance.py)
- DB connector/operations:
  - File: [bd/bdConector.py](../../bd/bdConector.py)

### Validation

- Business validators/rules live in `data/`.
  - File: [data/validators.py](../../data/validators.py)
  - Limits: [data/limits.py](../../data/limits.py)

### Logging

- Central logger writes to console and file.
  - File: [debug/logger.py](../../debug/logger.py)

## Runtime flow

1. Electron starts.
2. `PythonServer.start()` finds a free port (starting from 5000) and launches `stock-manager-server`.
3. Electron creates a `BrowserWindow` and calls `loadURL(serverUrl)`.
4. Flask handles requests:
   - UI routes render templates
   - API routes return JSON under `/api/*`
5. The DB layer uses SQLite with automatic transactions (commit/rollback).

## Ports (dev note)

- Electron attempts to use a free port (starting from 5000).
- The Flask server currently reads the port from `FLASK_PORT` (default 5000).
- Electron passes `--port` to the server binary, but the current Python entrypoint does not parse it.

Implication: if port 5000 is in use, Electron may pick another port and the connection can fail if the server still listens on 5000.

## Authentication and session

- The system uses Flask sessions (`session`) and a `secret_key` (`FLASK_SECRET_KEY`).
- The API uses a `require_auth()` guard that checks `session["user_id"]`.

## Roles and permissions (high level)

- The app stores a `role` string in both the session and the DB.
- “Admin” is evaluated as `role == "admin"`.

For label/value details, see [docs/en/SECURITY_ROLES.md](SECURITY_ROLES.md).
