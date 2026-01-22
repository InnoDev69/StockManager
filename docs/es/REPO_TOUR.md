# Repo Tour (Dev)

Este documento es un mapa rápido del repositorio: qué contiene cada carpeta y por dónde empezar a leer/depurar el sistema.

## Carpetas principales

- `api/`: Blueprint de Flask con la API REST (endpoints JSON) y validaciones de request.
- `bd/`: Capa de acceso a datos (SQLite): conector, helpers y utilidades relacionadas con persistencia.
- `data/`: Validadores y límites/reglas de negocio compartidas (p. ej. validación de items/usuarios).
- `debug/`: Logging y utilidades de depuración.
- `electron/`: Código de Electron (proceso principal, preload) y lanzador del servidor Python.
- `static/`: Assets estáticos servidos por Flask (CSS/JS, etc.).
- `templates/`: Vistas HTML (Jinja) servidas por Flask.
- `build/`: Artefactos intermedios de PyInstaller (salida temporal del build del servidor).
- `dist/`: Salidas de build/empaquetado (binarios y artefactos generados por PyInstaller/electron-builder).
- `logs/`: Archivos de log locales para diagnóstico durante desarrollo (utilitario; seguro de limpiar).

## Entrypoints clave

- `electron/main.js`: Entrypoint del proceso principal de Electron. Crea la ventana y carga la URL del servidor.
- `electron/python-server.js`: Arranca/detiene el binario del servidor Python y resuelve el puerto a usar.
- `main.py`: Entrypoint del servidor Flask (UI + registro del blueprint de API).
- `api/API.py`: Definición de endpoints del blueprint `api_bp`.
- `bd/bdInstance.py`: Inicialización de la instancia `db` (resuelve la ruta de la BD y ejecuta init).

## Qué NO tocar (a menos que sepas por qué)

- `build/`: Salida temporal del proceso de PyInstaller; se regenera.
- `dist/`: Artefactos de distribución/build; se regenera.
- `node_modules/`: Dependencias de Node; se regenera con `npm install`.
- `venv/`: Entorno virtual local de Python; es específico de tu máquina.
- `**/__pycache__/`: Caché de bytecode; se regenera.

## Logs

- `logs/` se usa para guardar logs de ejecución durante desarrollo.
- Borrar archivos dentro de `logs/` es seguro (solo perderás historial de diagnóstico).
