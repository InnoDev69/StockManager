/**
 * File Downloader - Sistema modular de descargas multiplataforma
 * Soporta: showDirectoryPicker → showSaveFilePicker → Fallback a Blob
 * Funciona con CSV, PNG, PDF, JSON, etc.
 */

class FileDownloader {
  constructor() {
    this.supportsDirectoryPicker = typeof window.showDirectoryPicker !== 'undefined';
    this.supportsSaveFilePicker = typeof window.showSaveFilePicker !== 'undefined';
  }

  /**
   * Obtener tipos de archivo para showSaveFilePicker (Windows compatible)
   * @param {String} fileName - Nombre del archivo con extensión
   * @returns {Array} - Array de tipos para showSaveFilePicker
   */
  getFileTypes(fileName) {
    const ext = fileName.split('.').pop().toLowerCase();
    const typeMap = {
      'csv': [{ description: 'Archivos CSV', accept: { 'text/csv': ['.csv'] } }],
      'pdf': [{ description: 'Archivos PDF', accept: { 'application/pdf': ['.pdf'] } }],
      'png': [{ description: 'Imágenes PNG', accept: { 'image/png': ['.png'] } }],
      'jpg': [{ description: 'Imágenes JPG', accept: { 'image/jpeg': ['.jpg', '.jpeg'] } }],
      'jpeg': [{ description: 'Imágenes JPEG', accept: { 'image/jpeg': ['.jpg', '.jpeg'] } }],
      'xlsx': [{ description: 'Archivos Excel', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }],
      'xls': [{ description: 'Archivos Excel', accept: { 'application/vnd.ms-excel': ['.xls'] } }],
      'json': [{ description: 'Archivos JSON', accept: { 'application/json': ['.json'] } }],
      'txt': [{ description: 'Archivos de texto', accept: { 'text/plain': ['.txt'] } }]
    };
    return typeMap[ext] || [];
  }

  /**
   * Modal genérico para seleccionar nombre de archivo
   * @param {String} defaultFileName - Nombre sugerido
   * @param {Function} onSubmit - Callback cuando el usuario confirma
   */
  showFileNameModal(defaultFileName, onSubmit) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-header">
          <h2>Guardar archivo</h2>
          <button class="modal-close" id="modal-close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <label for="download-filename" style="display: block; margin-bottom: 12px; font-weight: 600; color: var(--text); font-size: 0.9rem;">
            Nombre del archivo
          </label>
          <input type="text" id="download-filename" value="${defaultFileName}" 
                 style="width: 100%; padding: 11px 12px; border: 1px solid var(--border); border-radius: 8px; 
                        background: var(--panel); color: var(--text); font-size: 0.95rem; box-sizing: border-box; transition: all 0.2s ease;">
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" id="modal-cancel">
            Cancelar
          </button>
          <button class="btn btn-primary" id="modal-submit">
            Guardar
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    const input = modal.querySelector('#download-filename');
    const submitBtn = modal.querySelector('#modal-submit');
    const closeBtn = modal.querySelector('#modal-close');
    const cancelBtn = modal.querySelector('#modal-cancel');

    input.focus();
    input.select();

    const handleSubmit = () => {
      const fileName = input.value.trim() || defaultFileName;
      modal.remove();
      onSubmit(fileName);
    };

    submitBtn.addEventListener('click', handleSubmit);
    closeBtn.addEventListener('click', () => modal.remove());
    cancelBtn.addEventListener('click', () => modal.remove());

    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') handleSubmit();
    });

    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });
  }

  /**
   * Descargar usando APIs nativas (showDirectoryPicker + showSaveFilePicker)
   * @param {String} url - URL del archivo a descargar
   * @param {String} defaultFileName - Nombre sugerido
   * @returns {Boolean} - true si se descargó con APIs, false si falló
   */
  async downloadWithAPIs(url, defaultFileName) {
    try {
      // Paso 1: Intentar obtener la carpeta con showDirectoryPicker
      let dirHandle = null;
      try {
        dirHandle = await window.showDirectoryPicker();
      } catch (dirError) {
        console.log('showDirectoryPicker no disponible o cancelado:', dirError.name);
      }

      // Paso 2: Si obtuvimos la carpeta, usar showSaveFilePicker con suggestedName
      if (dirHandle) {
        try {
          const fileHandle = await window.showSaveFilePicker({
            suggestedName: defaultFileName,
            startIn: dirHandle,
            types: this.getFileTypes(defaultFileName)
          });

          // Descargar el archivo en la ubicación seleccionada
          const response = await fetch(url);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          
          const blob = await response.blob();
          const writable = await fileHandle.createWritable();
          await writable.write(blob);
          await writable.close();

          if (window.Notify) {
            Notify.success('Archivo guardado correctamente');
          }
          return true;
        } catch (saveError) {
          if (saveError.name !== 'AbortError') {
            console.error('showSaveFilePicker error:', saveError);
          }
        }
      } else {
        // Paso 3: Si no tenemos carpeta, intentar showSaveFilePicker directo
        try {
          const fileHandle = await window.showSaveFilePicker({
            suggestedName: defaultFileName,
            types: this.getFileTypes(defaultFileName)
          });

          const response = await fetch(url);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          
          const blob = await response.blob();
          const writable = await fileHandle.createWritable();
          await writable.write(blob);
          await writable.close();

          if (window.Notify) {
            Notify.success('Archivo guardado correctamente');
          }
          return true;
        } catch (saveError) {
          if (saveError.name !== 'AbortError') {
            console.error('showSaveFilePicker error:', saveError);
          }
        }
      }
    } catch (error) {
      console.error('APIs no disponibles:', error);
    }

    return false;
  }

  /**
   * Descargar usando blob y anchor element (fallback universal)
   * @param {String} url - URL del archivo
   * @param {String} fileName - Nombre del archivo
   */
  async downloadFileFallback(url, fileName) {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const blob = await response.blob();
      const link = document.createElement('a');
      const objectUrl = URL.createObjectURL(blob);

      link.href = objectUrl;
      link.download = fileName;
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      URL.revokeObjectURL(objectUrl);

      if (window.Notify) {
        Notify.success('Descarga iniciada');
      }
    } catch (error) {
      console.error('Error en descarga fallback:', error);
      if (window.Notify) {
        Notify.error('Error al descargar el archivo');
      }
    }
  }

  /**
   * Descargar blob directo (para contenido generado en cliente)
   * @param {Blob} blob - Objeto Blob
   * @param {String} fileName - Nombre del archivo
   */
  async downloadBlob(blob, fileName) {
    try {
      // Intentar APIs primero
      const url = URL.createObjectURL(blob);
      const success = await this.downloadWithAPIs(url, fileName);
      URL.revokeObjectURL(url);

      if (!success) {
        // Fallback: usar anchor element con blob
        const link = document.createElement('a');
        const objectUrl = URL.createObjectURL(blob);
        link.href = objectUrl;
        link.download = fileName;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(objectUrl);

        if (window.Notify) {
          Notify.success('Descarga iniciada');
        }
      }
    } catch (error) {
      console.error('Error en descarga de blob:', error);
      if (window.Notify) {
        Notify.error('Error al descargar el archivo');
      }
    }
  }

  /**
   * Función principal: Intenta APIs nativas, luego fallback con modal
   * @param {String} url - URL del archivo
   * @param {String} defaultFileName - Nombre sugerido
   */
  async download(url, defaultFileName) {
    const success = await this.downloadWithAPIs(url, defaultFileName);

    if (!success) {
      // Si las APIs no funcionan, mostrar modal para nombre de archivo
      this.showFileNameModal(defaultFileName, (fileName) => {
        this.downloadFileFallback(url, fileName);
      });
    }
  }

  /**
   * Descarga desde contenido CSV (para CSVExporter y similares)
   * @param {String} csvContent - Contenido CSV
   * @param {String} fileName - Nombre del archivo
   */
  async downloadCSVContent(csvContent, fileName) {
    const csvWithBOM = '\uFEFF' + csvContent;
    const blob = new Blob([csvWithBOM], { type: 'text/csv;charset=utf-8' });
    await this.downloadBlob(blob, fileName);
  }

  /**
   * Descarga de URL con nombre personalizable (abre modal si falla API)
   * @param {String} url - URL del archivo
   * @param {String} defaultFileName - Nombre sugerido
   */
  async downloadFromURL(url, defaultFileName) {
    await this.download(url, defaultFileName);
  }
}

// Instancia global
window.FileDownloader = new FileDownloader();
