#!/usr/bin/env python3
"""
Launcher alternativo para StockManager usando pywebview
Este launcher permite ejecutar la aplicación sin Electron, usando pywebview como frontend
"""

import os
import sys
import threading
import time
import signal
import requests
from flask import Flask

# Importar la aplicación Flask existente
from main import app

# Variable global para controlar el servidor
server_thread = None
should_exit = False

def run_flask():
    """Ejecuta el servidor Flask en un thread separado"""
    global should_exit
    port = int(os.environ.get("FLASK_PORT", 5000))
    try:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Error en servidor Flask: {e}")
        should_exit = True

def signal_handler(sig, frame):
    """Manejador de señales para salida limpia"""
    global should_exit
    print("\nCerrando aplicación...")
    should_exit = True
    sys.exit(0)

def main():
    """Función principal del launcher"""
    global server_thread, should_exit
    
    # Configurar manejadores de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Iniciar servidor Flask en thread separado
    print("Iniciando servidor Flask...")
    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()
    
    # Esperar a que el servidor esté listo
    port = int(os.environ.get("FLASK_PORT", 5000))
    url = f"http://127.0.0.1:{port}"
    
    max_attempts = 30
    for i in range(max_attempts):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code:
                print("Servidor Flask listo!")
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            # Servidor aún no está listo, continuar esperando
            pass
        except Exception as e:
            # Otros errores inesperados durante health check
            print(f"Warning: Error verificando servidor: {e}")
        time.sleep(0.5)
        if should_exit:
            return
    
    try:
        # Intentar importar webview
        import webview
        
        print("Iniciando interfaz webview...")
        
        # Configurar la ventana
        window = webview.create_window(
            'Stock Manager',
            url,
            width=1200,
            height=800,
            resizable=True,
            fullscreen=False,
            min_size=(800, 600)
        )
        
        # Iniciar la aplicación webview (bloquea hasta que se cierre la ventana)
        webview.start()
        
    except ImportError as e:
        print("=" * 60)
        print("ERROR: pywebview no está disponible")
        print("=" * 60)
        print(f"\nDetalle: {e}")
        print("\nSe requiere pywebview y un backend (PyQt5 o GTK):")
        print("  pip install pywebview PyQt5 PyQtWebEngine")
        print("  - o -")
        print("  pip install pywebview PyGObject")
        print("\nEn Arch Linux:")
        print("  sudo pacman -S python-pyqt5 python-pyqt5-webengine")
        print("  - o -")
        print("  sudo pacman -S python-gobject gtk3 webkit2gtk")
        print("=" * 60)
        
        # Mantener el servidor corriendo para acceso desde navegador
        print(f"\nEl servidor Flask sigue corriendo en: {url}")
        print("Puedes acceder desde tu navegador web.")
        print("Presiona Ctrl+C para salir.")
        
        try:
            while not should_exit:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    except Exception as e:
        print(f"Error al iniciar webview: {e}")
        print(f"\nEl servidor Flask está corriendo en: {url}")
        print("Puedes acceder desde tu navegador web.")
        
        try:
            while not should_exit:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    print("Aplicación cerrada.")

if __name__ == "__main__":
    main()
