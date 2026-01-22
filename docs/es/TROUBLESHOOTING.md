# Troubleshooting

Guía rápida para diagnosticar problemas comunes en desarrollo y en empaquetados (especialmente Linux/AppImage).

## Electron: `ERR_CONNECTION_REFUSED` al abrir la app

Síntoma:
- Electron intenta cargar `http://127.0.0.1:<puerto>` y falla con `ERR_CONNECTION_REFUSED`.
- En logs se ve que el servidor “arranca” y luego termina con código distinto de 0.

Checklist:

1) **Confirmar que el servidor realmente está vivo**
- El proceso se lanza desde `electron/python-server.js`.
- Si el binario se cierra inmediatamente, Electron nunca podrá cargar la UI.

2) **Revisar logs de Python**
- En empaquetado (PyInstaller), los logs se escriben en:
  - Linux/macOS: `~/.stock_manager/logs/app_YYYYMMDD.log`
  - Windows: `%APPDATA%/StockManager/logs/app_YYYYMMDD.log`
- En desarrollo: `./logs/app_YYYYMMDD.log`

3) **Permisos del binario embebido (Linux/AppImage)**
- El servidor embebido debe ser ejecutable (`chmod +x`).
- La configuración de `electron-builder` incluye `extraResources.permissions = "0755"` para el binario en Linux.
- Si falla igual: inspeccionar el AppImage y verificar permisos del archivo extraído.

## Mismatch de puerto (muy importante)

Comportamiento actual:
- Electron selecciona un puerto libre empezando en 5000 y lanza el servidor con `--port <puerto>`.
- El servidor Flask (en `main.py`) toma el puerto de `FLASK_PORT` (default 5000) y **no parsea `--port`**.

Consecuencia:
- Si Electron elige un puerto distinto de 5000, Flask podría seguir intentando 5000 y Electron quedará apuntando al puerto equivocado.

Workarounds:
- Forzar `FLASK_PORT=5000` y evitar que el lanzador seleccione otro.
- O (solución definitiva) implementar parsing de argumentos en el servidor para aceptar `--port`.

## AppImage: errores por rutas / escritura en disco

El servidor en modo frozen crea la BD en `data/database.db` al lado del ejecutable (`sys.executable`).

En AppImage, el directorio del ejecutable puede estar en un mount temporal que suele ser **solo lectura**.

Síntomas típicos:
- El servidor termina con error al iniciar.
- En logs aparece `OperationalError: unable to open database file` o similar.

Mitigación recomendada:
- Mover la BD a un directorio de usuario escribible (similar a cómo se resuelven los logs).
- Como mínimo, permitir configurar `DB_PATH` también en modo frozen.

## No se ve el error real del servidor (stdout/stderr ocultos)

En `electron/python-server.js` el proceso se lanza con `stdio: 'ignore'`, lo que oculta stdout/stderr.

Para depurar:
- Cambiar temporalmente `stdio` a `'pipe'` y loguear `child.stdout`/`child.stderr`, o a `'inherit'` para ver salida en consola.
- Ejecutar el binario del servidor manualmente en terminal y leer el log generado.

## Errores de plantilla / rutas (Flask)

Si la app inicia pero luego falla al navegar:
- Revisar el log del día.
- Errores comunes: `BuildError` por `url_for()` apuntando a un endpoint inexistente.

