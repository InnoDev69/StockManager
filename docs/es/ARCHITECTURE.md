# Arquitectura (Dev)

## Resumen

StockManager es una app desktop (Electron) que renderiza una app web local (Flask). Electron levanta un proceso separado (servidor Python empaquetado) y abre una ventana apuntando a `http://127.0.0.1:<puerto>`.

## Componentes

### Electron (desktop shell)

- Proceso principal: crea la ventana y carga la URL del servidor.
  - Entrypoint: [electron/main.js](../../electron/main.js)
- Lanzador del servidor: resuelve puerto libre, ejecuta el binario y gestiona stop.
  - Archivo: [electron/python-server.js](../../electron/python-server.js)

### Servidor Flask (UI + API)

- App Flask sirve:
  - Vistas HTML (Jinja) desde `templates/`
  - Assets desde `static/`
  - API REST JSON bajo `/api` vía blueprint
- Entrypoint: [main.py](../../main.py)
- Blueprint API: [api/API.py](../../api/API.py)

### Persistencia (SQLite)

- Instancia global `db` se inicializa al importar `bd/bdInstance.py`.
  - Archivo: [bd/bdInstance.py](../../bd/bdInstance.py)
- Conector/operaciones DB:
  - Archivo: [bd/bdConector.py](../../bd/bdConector.py)

### Validación

- Reglas/validadores en `data/`.
  - Archivo: [data/validators.py](../../data/validators.py)
  - Límites: [data/limits.py](../../data/limits.py)

### Logging

- Logger central escribe en consola y archivo.
  - Archivo: [debug/logger.py](../../debug/logger.py)

## Flujo de ejecución (runtime)

1. Electron arranca.
2. `PythonServer.start()` busca un puerto libre (default base 5000) y lanza el binario `stock-manager-server`.
3. Electron crea `BrowserWindow` y hace `loadURL(serverUrl)`.
4. Flask procesa requests:
   - Rutas UI: renderizan templates
   - Rutas API: responden JSON bajo `/api/*`
5. La capa DB usa SQLite con transacciones automáticas (commit/rollback).

## Puertos (nota para dev)

- Electron intenta usar un puerto libre (comenzando desde 5000).
- El servidor Flask actualmente toma el puerto desde `FLASK_PORT` (default 5000).
- El argumento `--port` que pasa Electron se envía al binario, pero hoy el entrypoint Python no lo parsea.

Implicación: si el puerto 5000 está ocupado, Electron puede elegir otro puerto y fallar la conexión si el servidor sigue escuchando en 5000.

## Autenticación y sesión

- El sistema usa sesión de Flask (`session`) y un `secret_key` (`FLASK_SECRET_KEY`).
- La API utiliza un guard `require_auth()` que valida `session["user_id"]`.

## Roles y permisos (alto nivel)

- La app guarda un string `role` en sesión y DB.
- “Admin” se evalúa como `role == "admin"`.

Para detalles precisos (labels vs valores), ver [docs/es/SECURITY_ROLES.md](SECURITY_ROLES.md).
