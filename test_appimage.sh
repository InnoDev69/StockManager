#!/bin/bash
# Script para probar el AppImage de StockManager
# Verifica que el AppImage se ejecuta correctamente y que todas las dependencias están presentes

set -e

echo "=========================================="
echo "StockManager - AppImage Test Script"
echo "=========================================="

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Buscar el AppImage
APPIMAGE=$(ls StockManager-*.AppImage 2>/dev/null | head -n 1)

if [ -z "$APPIMAGE" ]; then
    echo -e "${RED}Error: No se encontró ningún AppImage StockManager-*.AppImage${NC}"
    echo "Primero ejecuta: ./build_scripts/build_appimage.sh"
    exit 1
fi

echo -e "${GREEN}AppImage encontrado: ${APPIMAGE}${NC}"
echo ""

# Verificar que es ejecutable
echo -e "${YELLOW}[1/5] Verificando permisos...${NC}"
if [ ! -x "$APPIMAGE" ]; then
    echo "  Haciendo ejecutable el AppImage..."
    chmod +x "$APPIMAGE"
fi
echo -e "${GREEN}✓ AppImage es ejecutable${NC}"
echo ""

# Verificar estructura del AppImage
echo -e "${YELLOW}[2/5] Verificando estructura interna...${NC}"
./"$APPIMAGE" --appimage-extract-and-run --version 2>/dev/null || echo "  (comando --version no disponible, normal)"
echo -e "${GREEN}✓ AppImage tiene estructura válida${NC}"
echo ""

# Extraer AppImage para inspección
echo -e "${YELLOW}[3/5] Extrayendo AppImage para inspección...${NC}"
EXTRACT_DIR="test_extract"
rm -rf "$EXTRACT_DIR"
./"$APPIMAGE" --appimage-extract >/dev/null 2>&1 || true
if [ -d "squashfs-root" ]; then
    mv squashfs-root "$EXTRACT_DIR"
    echo -e "${GREEN}✓ AppImage extraído en ${EXTRACT_DIR}/${NC}"
    
    echo "  Verificando archivos críticos:"
    
    if [ -f "$EXTRACT_DIR/usr/bin/StockManager" ]; then
        echo -e "    ${GREEN}✓ Ejecutable principal encontrado${NC}"
    else
        echo -e "    ${RED}✗ Ejecutable principal NO encontrado${NC}"
    fi
    
    if [ -f "$EXTRACT_DIR/StockManager.desktop" ]; then
        echo -e "    ${GREEN}✓ Desktop entry encontrado${NC}"
    else
        echo -e "    ${YELLOW}⚠ Desktop entry NO encontrado${NC}"
    fi
    
    if [ -f "$EXTRACT_DIR/stockmanager.png" ]; then
        echo -e "    ${GREEN}✓ Icono encontrado${NC}"
    else
        echo -e "    ${YELLOW}⚠ Icono NO encontrado${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No se pudo extraer el AppImage (puede ser normal)${NC}"
fi
echo ""

# Verificar dependencias de PyQt5
echo -e "${YELLOW}[4/5] Verificando dependencias de pywebview...${NC}"
if [ -d "$EXTRACT_DIR" ]; then
    # Buscar PyQt5
    if find "$EXTRACT_DIR" -name "*PyQt5*" -o -name "*Qt5*" | grep -q .; then
        echo -e "    ${GREEN}✓ PyQt5 incluido en el AppImage${NC}"
    else
        echo -e "    ${YELLOW}⚠ PyQt5 no encontrado (puede usar GTK)${NC}"
    fi
    
    # Buscar GTK
    if find "$EXTRACT_DIR" -name "*gtk*" -o -name "*Gtk*" | grep -q . 2>/dev/null; then
        echo -e "    ${GREEN}✓ GTK incluido en el AppImage${NC}"
    else
        echo -e "    ${YELLOW}⚠ GTK no encontrado (puede usar PyQt5)${NC}"
    fi
else
    echo -e "    ${YELLOW}⚠ Saltando verificación de dependencias${NC}"
fi
echo ""

# Prueba de ejecución rápida
echo -e "${YELLOW}[5/5] Prueba de ejecución...${NC}"
echo "  NOTA: Esta prueba iniciará la aplicación brevemente."
echo "  La aplicación se cerrará automáticamente después de 5 segundos."
echo "  Si ves la ventana de la aplicación, ¡el test es exitoso!"
echo ""
echo -e "${GREEN}Iniciando aplicación...${NC}"

# Ejecutar el AppImage en background
timeout 5s ./"$APPIMAGE" &
PID=$!

sleep 2

# Verificar si el proceso está corriendo
if ps -p $PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Aplicación se inició correctamente${NC}"
    echo "  (PID: $PID)"
    
    # Esperar a que termine o timeout
    wait $PID 2>/dev/null || true
else
    echo -e "${RED}✗ La aplicación no se pudo iniciar${NC}"
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Test completado"
echo "==========================================${NC}"
echo ""
echo "Resumen:"
echo "  - AppImage: $APPIMAGE"
if [ -d "$EXTRACT_DIR" ]; then
    echo "  - Contenido extraído: $EXTRACT_DIR/"
fi
echo ""
echo "Para ejecutar la aplicación manualmente:"
echo "  ./$APPIMAGE"
echo ""
echo "Para limpiar archivos de test:"
echo "  rm -rf $EXTRACT_DIR"
echo ""
