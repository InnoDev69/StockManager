#!/bin/bash
# Script para construir StockManager como AppImage con todas las dependencias
# Este script crea un AppImage autónomo que incluye Python, Flask, pywebview y todas las dependencias de QT/GTK

set -e  # Salir si hay algún error

echo "=========================================="
echo "StockManager - AppImage Build Script"
echo "=========================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar que estamos en el directorio correcto
if [ ! -f "main.py" ]; then
    echo -e "${RED}Error: main.py no encontrado. Ejecuta este script desde la raíz del repositorio.${NC}"
    exit 1
fi

# Configuración
APP_NAME="StockManager"
VERSION="${VERSION:-1.1.0}"
PYTHON_VERSION="3.11"
ARCH="x86_64"
BUILD_DIR="build_appimage"
APPDIR="${BUILD_DIR}/AppDir"

echo -e "${GREEN}Configuración:${NC}"
echo "  App: ${APP_NAME}"
echo "  Versión: ${VERSION}"
echo "  Arquitectura: ${ARCH}"
echo ""

# Limpiar build anterior
echo -e "${YELLOW}[1/8] Limpiando build anterior...${NC}"
rm -rf "${BUILD_DIR}" dist/*.AppImage
mkdir -p "${BUILD_DIR}"

# Crear estructura AppDir
echo -e "${YELLOW}[2/8] Creando estructura AppDir...${NC}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Configurar entorno Python virtual para el build
echo -e "${YELLOW}[3/8] Configurando entorno Python...${NC}"
if [ ! -d "${BUILD_DIR}/venv" ]; then
    python3 -m venv "${BUILD_DIR}/venv"
fi
source "${BUILD_DIR}/venv/bin/activate"

# Instalar dependencias Python
echo -e "${YELLOW}[4/8] Instalando dependencias Python...${NC}"
pip install --upgrade pip
pip install PyInstaller
pip install flask werkzeug python-dotenv requests
pip install pywebview
# Instalar backends de pywebview - PyQt5 es más estable
pip install PyQt5 PyQtWebEngine

# Construir con PyInstaller usando el spec modificado
echo -e "${YELLOW}[5/8] Construyendo ejecutable con PyInstaller...${NC}"
pyinstaller build_appimage.spec --clean --noconfirm

# Copiar ejecutable al AppDir
echo -e "${YELLOW}[6/8] Copiando archivos al AppDir...${NC}"
cp -r dist/StockManager/* "${APPDIR}/usr/bin/"

# Copiar archivos de la aplicación
cp StockManager.desktop "${APPDIR}/usr/share/applications/${APP_NAME}.desktop"

# Copiar icono si existe
if [ -f "static/icon.png" ]; then
    cp static/icon.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/stockmanager.png"
    cp static/icon.png "${APPDIR}/stockmanager.png"
elif [ -f "static/app/icon.png" ]; then
    cp static/app/icon.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/stockmanager.png"
    cp static/app/icon.png "${APPDIR}/stockmanager.png"
else
    echo -e "${YELLOW}Advertencia: No se encontró icono, creando icono placeholder${NC}"
    # Crear un icono SVG simple como placeholder
    cat > "${APPDIR}/stockmanager.png" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg width="256" height="256" xmlns="http://www.w3.org/2000/svg">
  <rect width="256" height="256" fill="#4CAF50"/>
  <text x="128" y="140" font-size="72" text-anchor="middle" fill="white">SM</text>
</svg>
EOF
fi

# Crear symlinks requeridos por AppImage
ln -sf usr/share/applications/${APP_NAME}.desktop "${APPDIR}/${APP_NAME}.desktop"
ln -sf usr/bin/StockManager "${APPDIR}/AppRun"

# Hacer ejecutable el AppRun
chmod +x "${APPDIR}/AppRun"

# Descargar linuxdeploy y appimagetool si no existen
echo -e "${YELLOW}[7/8] Descargando herramientas AppImage...${NC}"
LINUXDEPLOY="linuxdeploy-${ARCH}.AppImage"
if [ ! -f "${BUILD_DIR}/${LINUXDEPLOY}" ]; then
    echo "  Descargando linuxdeploy..."
    wget -q "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/${LINUXDEPLOY}" \
        -O "${BUILD_DIR}/${LINUXDEPLOY}"
    chmod +x "${BUILD_DIR}/${LINUXDEPLOY}"
fi

APPIMAGETOOL="appimagetool-${ARCH}.AppImage"
if [ ! -f "${BUILD_DIR}/${APPIMAGETOOL}" ]; then
    echo "  Descargando appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/${APPIMAGETOOL}" \
        -O "${BUILD_DIR}/${APPIMAGETOOL}"
    chmod +x "${BUILD_DIR}/${APPIMAGETOOL}"
fi

# Generar AppImage
echo -e "${YELLOW}[8/8] Generando AppImage...${NC}"
cd "${BUILD_DIR}"
ARCH=${ARCH} ./${APPIMAGETOOL} AppDir "../${APP_NAME}-${VERSION}-${ARCH}.AppImage"
cd ..

# Limpiar
deactivate

echo ""
echo -e "${GREEN}=========================================="
echo "✓ AppImage generado exitosamente!"
echo "=========================================="
echo -e "Archivo: ${APP_NAME}-${VERSION}-${ARCH}.AppImage${NC}"
echo ""
echo "Para probar el AppImage:"
echo "  chmod +x ${APP_NAME}-${VERSION}-${ARCH}.AppImage"
echo "  ./${APP_NAME}-${VERSION}-${ARCH}.AppImage"
echo ""
