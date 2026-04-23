# Sistema Modular de Descargas - Documentación

## Descripción General
Sistema centralizado y modular para descargas de archivos (CSV, PNG, PDF, etc.) que funciona en Windows, Linux, macOS y todas los navegadores.

**Flujo de descarga:**
1. Intenta `showDirectoryPicker()` - Usuario elige carpeta
2. Intenta `showSaveFilePicker()` - Usuario elige nombre/ubicación
3. Fallback modal - Modal personalizado para nombre
4. Fallback blob - Descarga tradicional por anchor element

---

## Componentes

### 1. `static/js/file-downloader.js` (Nuevo - Centralizado)
Clase `FileDownloader` con métodos:

```javascript
// Descargar desde URL con selección de directorio
window.FileDownloader.download(url, defaultFileName);

// Descargar contenido CSV directo
await window.FileDownloader.downloadCSVContent(csvContent, fileName);

// Descargar blob generado en cliente
await window.FileDownloader.downloadBlob(blob, fileName);
```

**Ejemplo de uso:**
```javascript
const url = '/products/123/barcode/image';
const fileName = 'barcode_PROD123.png';
window.FileDownloader.download(url, fileName);
```

---

### 2. `static/js/csv-exporter.js` (Actualizado)
Clase `CSVExporter` que ahora usa `FileDownloader` internamente.

```javascript
// Exportar tabla HTML a CSV
await window.CSVExporter.exportFromHTMLTable(
  tableElement,          // <table> element
  'export.csv',         // filename
  1,                    // columnas a excluir desde el final
  onSuccess             // callback opcional
);

// Exportar array de arrays a CSV
await window.CSVExporter.exportFromArray(
  rows,                 // [[col1, col2], [data1, data2]]
  'export.csv',
  onSuccess
);
```

---

### 3. Templates con descargas actualizadas:

#### `templates/barcode_management.html`
Funciones simples que usan `FileDownloader`:
```javascript
downloadSingleBarcode(productId, barcodeText);  // Descarga PNG
downloadBarcodesPDF(selectedIds);               // Descarga PDF
```

#### `templates/sales.html`
Ya funciona automáticamente:
```javascript
window.exportToCSV();  // Exporta tabla a CSV
```

#### `templates/metrics.html`
Ya funciona automáticamente:
```javascript
initExportButtons();   // Configura botones de descarga
```

---

## Carga de Scripts

En `templates/base.html`:
```html
<script src="{{ url_for('static', filename='js/file-downloader.js') }}"></script>
<script src="{{ url_for('static', filename='js/csv-exporter.js') }}"></script>
```

**Orden importante:** `file-downloader.js` debe ir ANTES de `csv-exporter.js`

---

## Ejemplos de Uso

### Descargar archivo desde URL
```javascript
// PNG
window.FileDownloader.download('/products/123/barcode/image', 'barcode_ABC123.png');

// PDF
window.FileDownloader.download('/api/report/monthly', 'report_2026-04.pdf');

// CSV
window.FileDownloader.download('/api/export/sales', 'ventas_2026-04.csv');
```

### Descargar contenido generado (CSV)
```javascript
const csvContent = 'Nombre,Email,Teléfono\nJuan,juan@mail,123456';
await window.FileDownloader.downloadCSVContent(csvContent, 'contactos.csv');
```

### Descargar Blob generado
```javascript
const canvas = document.getElementById('chart');
canvas.toBlob(blob => {
  window.FileDownloader.downloadBlob(blob, 'chart.png');
});
```

---

## Características

✅ **Multiplataforma:** Windows, Linux, macOS  
✅ **Multinavegador:** Chrome, Firefox, Safari, Edge, Opera  
✅ **Desktop:** Funciona en pywebview (PyInstaller)  
✅ **UX:** Diálogos nativos con fallback modal personalizado  
✅ **Modular:** Reutilizable en cualquier página  
✅ **Robusto:** Manejo de errores y timeouts  
✅ **Formatos:** CSV, PNG, PDF, JSON, etc.  

---

## Flujos Internos

### Opción 1: APIs Nativas (Preferida)
```
showDirectoryPicker()
    → showSaveFilePicker { suggestedName, startIn: dirHandle }
        → fetch() → blob
            → fileHandle.createWritable()
                → fileHandle.write(blob)
                    → Éxito
```

### Opción 2: Fallback Modal
```
showDirectoryPicker() falla
    → showFileNameModal()
        → Usuario ingresa nombre
            → downloadFileFallback()
                → fetch() → blob
                    → anchor element click
                        → Descarga
```

---

## Integración en Nuevas Páginas

Para agregar descarga a una nueva página:

```html
<!-- En el template -->
<button onclick="downloadFile('/api/data', 'archivo.csv')">Descargar</button>

<!-- En el <script> -->
<script>
function downloadFile(url, fileName) {
  if (window.FileDownloader) {
    window.FileDownloader.download(url, fileName);
  } else {
    console.error('FileDownloader no disponible');
  }
}
</script>
```

¡Eso es todo! No necesitas duplicar lógica de descarga.

---

## Notas Importantes

- `FileDownloader` se carga automáticamente en todas las páginas vía `base.html`
- El modal de nombre de archivo reutiliza los estilos existentes `.modal-overlay` y `.modal-dialog`
- Las notificaciones usan el sistema `window.Notify` existente
- Compatible con `window.Notify.success()` y `window.Notify.error()`
