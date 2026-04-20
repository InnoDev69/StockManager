/**
 * CSV Exporter - File System Access API with Fallback
 * Usa showSaveFilePicker para diálogo "Guardar como" (Chrome, Edge, Opera)
 * Fallback a descarga tradicional para otros navegadores
 */

class CSVExporter {
    constructor() {
        this.supportsFileSystemAPI = typeof window.showSaveFilePicker !== 'undefined';
    }

    /**
     * Exporta datos a CSV desde array de arrays
     * @param {Array<Array>} rows - Array de arrays: [[col1, col2], [data1, data2]]
     * @param {String} filename - Nombre del archivo (ej: "datos_2026-04-20.csv")
     * @param {String} format - Formato: 'array' (por defecto) o 'custom'
     */
    async exportFromArray(rows, filename = 'export.csv', onSuccess = null) {
        try {
            const csvContent = this.arrayToCSV(rows);
            await this.saveFile(csvContent, filename);
            if (onSuccess) onSuccess();
        } catch (err) {
            console.error('Error exportando CSV:', err);
            throw err;
        }
    }

    /**
     * Exporta datos desde tabla HTML
     * @param {Element} tableElement - Elemento <table> a exportar
     * @param {String} filename - Nombre del archivo
     * @param {Number} excludeLastCols - Columnas a excluir desde el final
     */
    async exportFromHTMLTable(tableElement, filename = 'export.csv', excludeLastCols = 1, onSuccess = null) {
        try {
            const rows = [];
            const table = tableElement;
            const tr_list = table.querySelectorAll('tr');

            tr_list.forEach(row => {
                const cells = Array.from(row.querySelectorAll('td, th'));
                
                const filteredCells = excludeLastCols > 0 
                    ? cells.slice(0, -excludeLastCols) 
                    : cells;
                
                const rowData = filteredCells.map(cell => 
                    this.escapeCSVCell(cell.innerText.replace(/\n/g, ' ')).trim()
                );
                if (rowData.some(cell => cell.length > 0)) {
                    rows.push(rowData);
                }
            });

            const csvContent = this.arrayToCSV(rows);
            await this.saveFile(csvContent, filename);
            if (onSuccess) onSuccess();
        } catch (err) {
            console.error('Error exportando tabla:', err);
            throw err;
        }
    }

    /**
     * Convierte array de arrays a string CSV
     */
    arrayToCSV(rows) {
        return rows
            .map(row => 
                row.map(cell => this.escapeCSVCell(String(cell || ''))).join(',')
            )
            .join('\n');
    }

    /**
     * Escapa celdas CSV según RFC 4180
     */
    escapeCSVCell(cell) {
        // Si contiene comoma, comillas o saltos de línea, encapsular en comillas
        if (cell.includes(',') || cell.includes('"') || cell.includes('\n')) {
            return '"' + cell.replace(/"/g, '""') + '"';
        }
        return cell;
    }

    /**
     * Guardar archivo - Intenta File System API, fallback a blob
     */
    async saveFile(csvContent, filename) {
        const csvWithBOM = '\uFEFF' + csvContent;
        
        if (this.supportsFileSystemAPI) {
            return this.saveWithFileSystemAPI(csvWithBOM, filename);
        } else {
            return this.saveWithBlobFallback(csvWithBOM, filename);
        }
    }

    /**
     * Guarda usando File System Access API (diálogo nativo)
     */
    async saveWithFileSystemAPI(csvContent, filename) {
        try {
            const handle = await window.showSaveFilePicker({
                suggestedName: filename,
                types: [
                    {
                        description: 'CSV Files',
                        accept: { 'text/csv': ['.csv'] }
                    },
                    {
                        description: 'All Files',
                        accept: { '*/*': [''] }
                    }
                ],
                startInDownloads: true
            });

            const writable = await handle.createWritable();
            await writable.write(csvContent);
            await writable.close();

            console.log(`✓ Archivo guardado: ${filename}`);
            return true;
        } catch (err) {
            if (err.name === 'AbortError') {
                console.log('Descarga cancelada por el usuario');
                return false;
            }
            console.warn('File System API no disponible, usando fallback:', err.message);
            return this.saveWithBlobFallback(csvContent, filename);
        }
    }

    /**
     * Fallback: Descarga tradicional con Blob
     */
    saveWithBlobFallback(csvContent, filename) {
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);

        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';

        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        URL.revokeObjectURL(url);
        console.log(`✓ Archivo descargado (blob): ${filename}`);
        return true;
    }
}

window.CSVExporter = new CSVExporter();