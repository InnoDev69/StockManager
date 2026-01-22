# Development (Dev)

## Requirements

- Python: 3.13
- Node.js: 20
- npm (bundled with Node)

## Environment setup

### 1) Python (venv + dependencies)

From the repo root:

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Notes:
- Python dependencies are pinned in [requirements.txt](../../requirements.txt).

### 2) Node/Electron (dependencies)

```bash
npm ci
```

(For local dev, `npm install` also works, but `npm ci` is reproducible.)

## Run in development

### Option A — Run Electron (recommended)

```bash
npm start
```

This launches Electron and, from the main process, attempts to start the Python server and load the local URL.

### Option B — Run Flask only

Run the server directly (useful for backend debugging):

```bash
source venv/bin/activate
python main.py
```

Then open `http://127.0.0.1:5000/` in your browser.

## Environment variables

They are loaded from `.env` (if present) via `python-dotenv`.

- `FLASK_SECRET_KEY`
  - Used by Flask to sign the session cookie.
  - Current default: `"a"` (dev-only; production should use a real secret).
- `FLASK_PORT`
  - Flask server port.
  - Default: `5000`.
- `FLASK_ENV`
  - If set to `development`, Flask starts with `debug=True`.
  - Default: `production`.
- `DB_PATH`
  - SQLite database path in development.
  - Default: `./bd/database.db`.
- `DEBUG`
  - Extra flag used by templates (e.g. to show additional UI if `DEBUG=1`).

Related files:
- [main.py](../../main.py)
- [bd/bdInstance.py](../../bd/bdInstance.py)

## Logs

- In development, logs are written to `./logs/app_YYYYMMDD.log`.
- Levels:
  - File: DEBUG
  - Console: WARNING

Implementation: [debug/logger.py](../../debug/logger.py)

## Database (dev)

- SQLite; created if missing and initialized with `CREATE TABLE IF NOT EXISTS` at startup.
- Default path in dev: `./bd/database.db` (or `DB_PATH`).

Implementation:
- DB instance: [bd/bdInstance.py](../../bd/bdInstance.py)
- Schema and operations: [bd/bdConector.py](../../bd/bdConector.py)

## Structure and entrypoints

- Electron UI + launcher: [electron/main.js](../../electron/main.js), [electron/python-server.js](../../electron/python-server.js)
- Flask app: [main.py](../../main.py)
- REST API: [api/API.py](../../api/API.py)

## Note about dynamic port (known)

Electron tries to select a free port starting from 5000.

The Flask server currently reads the port from `FLASK_PORT` (default 5000). The `--port` argument passed by Electron to the server binary is not parsed by the current Python entrypoint.

If `5000` is already in use, this may cause `ERR_CONNECTION_REFUSED`.
