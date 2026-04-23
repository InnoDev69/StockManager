/**
 * CSV Exporter - Usa FileDownloader modular
 * Soporta: showDirectoryPicker → showSaveFilePicker → Blob
 * Funciona en Windows, Linux, macOS y navegadores
 */

class CSVExporter {
    constructor() {
        this.waitForFileDownloader();
    }

    /**
     * Espera a que FileDownloader esté disponible
     */
    waitForFileDownloader() {
        if (!window.FileDownloader) {
            console.warn('FileDownloader aún no disponible, reintentando...');
            setTimeout(() => this.waitForFileDownloader(), 100);
        }
    }

    /**
     * Exporta datos a CSV desde array de arrays
     * @param {Array<Array>} rows - Array de arrays: [[col1, col2], [data1, data2]]
     * @param {String} filename - Nombre del archivo (ej: "datos_2026-04-20.csv")
     * @param {Function} onSuccess - Callback opcional cuando se completa
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
     * @param {Function} onSuccess - Callback opcional
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
        if (cell.includes(',') || cell.includes('"') || cell.includes('\n')) {
            return '"' + cell.replace(/"/g, '""') + '"';
        }
        return cell;
    }

    /**
     * Guardar archivo usando FileDownloader (modular)
     */
    async saveFile(csvContent, filename) {
        if (!window.FileDownloader) {
            console.error('FileDownloader no disponible');
            throw new Error('FileDownloader no cargado');
        }
        
        // Crear blob y descargar usando el sistema modular
        await window.FileDownloader.downloadCSVContent(csvContent, filename);
    }
}

window.CSVExporter = new CSVExporter();