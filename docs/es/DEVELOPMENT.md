# Desarrollo (Dev)

## Requisitos

- Python: 3.13
- Node.js: 20
- npm (incluido con Node)

## Setup del entorno

### 1) Python (venv + dependencias)

Desde la raíz del repo:

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Notas:
- Dependencias Python están fijadas en [requirements.txt](../../requirements.txt).

### 2) Node/Electron (dependencias)

```bash
npm ci
```

(En desarrollo local también sirve `npm install`, pero `npm ci` es reproducible.)

## Ejecutar en desarrollo

### Opción A — Ejecutar Electron (recomendado)

```bash
npm start
```

Esto levanta Electron y, desde el proceso principal, intenta lanzar el servidor Python y cargar la URL local.

### Opción B — Ejecutar solo Flask

Ejecuta el servidor directamente (útil para debug de backend):

```bash
source venv/bin/activate
python main.py
```

Luego abre `http://127.0.0.1:5000/` en el navegador.

## Variables de entorno

Se cargan desde `.env` (si existe) vía `python-dotenv`.

- `FLASK_SECRET_KEY`
  - Usado por Flask para firmar la cookie de sesión.
  - Default actual: `"a"` (solo para dev; en producción debe ser un secreto real).
- `FLASK_PORT`
  - Puerto del servidor Flask.
  - Default: `5000`.
- `FLASK_ENV`
  - Si es `development`, Flask inicia con `debug=True`.
  - Default: `production`.
- `DB_PATH`
  - Ruta de la base SQLite en desarrollo.
  - Default: `./bd/database.db`.
- `DEBUG`
  - Flag adicional usado por templates (ej. mostrar elementos extra si `DEBUG=1`).

Archivos relacionados:
- [main.py](../../main.py)
- [bd/bdInstance.py](../../bd/bdInstance.py)

## Logs

- En desarrollo, el logger escribe a `./logs/app_YYYYMMDD.log`.
- Nivel:
  - Archivo: DEBUG
  - Consola: WARNING

Implementación: [debug/logger.py](../../debug/logger.py)

## Base de datos (dev)

- SQLite; se crea si no existe y las tablas se inicializan con `CREATE TABLE IF NOT EXISTS` al iniciar.
- Ruta por defecto en dev: `./bd/database.db` (o `DB_PATH`).

Implementación:
- Instancia DB: [bd/bdInstance.py](../../bd/bdInstance.py)
- Esquema y operaciones: [bd/bdConector.py](../../bd/bdConector.py)

## Estructura y entrypoints

- Electron UI + launcher: [electron/main.js](../../electron/main.js), [electron/python-server.js](../../electron/python-server.js)
- Flask app: [main.py](../../main.py)
- API REST: [api/API.py](../../api/API.py)

## Nota sobre puerto dinámico (conocido)

Electron intenta seleccionar un puerto libre empezando en 5000.

El servidor Flask actualmente toma el puerto de `FLASK_PORT` (default 5000). El argumento `--port` que pasa Electron al binario del servidor no se parsea en el entrypoint Python actual.

Si `5000` está ocupado, esto puede provocar `ERR_CONNECTION_REFUSED`.
