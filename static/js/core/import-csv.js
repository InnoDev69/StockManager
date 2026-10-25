/**
 * CSV Import Module
 * Handles file upload, CSV parsing, column mapping, and import preview
 */

(function () {
  'use strict';

  /* ── Helpers ─────────────────────────────────────── */
  const importForm  = document.getElementById('importForm');
  const confirmForm = document.getElementById('confirmForm');
  const fileInput   = document.getElementById('file');
  const fileHint    = document.getElementById('fileHint');
  const delimInp    = document.getElementById('delimiter');
  const btnPreview  = document.getElementById('btnPreview');
  const btnImport   = document.getElementById('btnImport');
  const importAlerts  = document.getElementById('importAlerts');
  const previewAlerts = document.getElementById('previewAlerts');
  const previewMeta   = document.getElementById('previewMeta');
  const previewTable  = document.getElementById('previewTable');
  const thead         = previewTable.querySelector('thead');
  const tbody         = previewTable.querySelector('tbody');
  const tempKeyInput  = document.getElementById('temp_key');
  const dropzone      = document.getElementById('dropzone');

  let droppedFile = null;  // Guardar referencia al archivo deslizado

  const selectIds  = ['col_barcode','col_name','col_description','col_quantity','col_min_quantity','col_price','col_expiration_date'];
  const reqIds     = ['col_barcode','col_name','col_quantity','col_price'];
  const optIds     = ['col_description','col_min_quantity','col_expiration_date'];

  function clearNode(n) { while (n && n.firstChild) n.removeChild(n.firstChild); }

  function addInlineAlert(container, message, type) {
    if (!container) return;
    if (window.NotificationManager && typeof window.NotificationManager.createInlineAlert === 'function') {
      container.appendChild(window.NotificationManager.createInlineAlert(message, { type: type || 'info', dismissible: true }));
      return;
    }
    const div = document.createElement('div');
    div.className = 'alert-error';
    div.textContent = message;
    container.appendChild(div);
  }

  /* ── Dropzone UX ─────────────────────────────────── */
  function updateFileHint(file) {
    if (file) {
      const kb = (file.size / 1024).toFixed(1);
      fileHint.textContent = `${file.name} · ${kb} KB`;
      dropzone.classList.add('ci-dropzone--has-file');
    } else {
      fileHint.textContent = 'Ningún archivo seleccionado · Solo archivos .csv';
      dropzone.classList.remove('ci-dropzone--has-file');
    }
  }

  fileInput.addEventListener('change', () => {
    droppedFile = fileInput.files && fileInput.files[0];
    updateFileHint(droppedFile);
  });

  dropzone.addEventListener('click', (e) => {
    if (e.target !== fileInput) fileInput.click();
  });

  ['dragenter','dragover'].forEach(ev => dropzone.addEventListener(ev, e => {
    e.preventDefault(); dropzone.classList.add('ci-dropzone--drag');
  }));
  ['dragleave','drop'].forEach(ev => dropzone.addEventListener(ev, e => {
    e.preventDefault(); 
    dropzone.classList.remove('ci-dropzone--drag');
    if (ev === 'drop' && e.dataTransfer.files[0]) {
      droppedFile = e.dataTransfer.files[0];
      updateFileHint(droppedFile);
    }
  }));

  delimInp.addEventListener('input', () => {
    if (delimInp.value.length > 1) delimInp.value = delimInp.value.slice(0, 1);
  });

  /* ── Visibility ──────────────────────────────────── */
  function setPreviewVisible(v) {
    if (v) {
      confirmForm.classList.remove('hidden');
      confirmForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      confirmForm.classList.add('hidden');
    }
  }

  function setLoadingPreview(on) {
    btnPreview.disabled = on;
    btnPreview.innerHTML = on
      ? '<svg style="animation:spin .8s linear infinite;width:15px;height:15px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Procesando…'
      : '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> Previsualizar';
    fileInput.disabled = on;
    delimInp.disabled  = on;
    document.getElementById('has_header').disabled = on;
  }

  function setLoadingImport(on) {
    btnImport.disabled = on;
    btnImport.innerHTML = on
      ? '<svg style="animation:spin .8s linear infinite;width:15px;height:15px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Importando…'
      : '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Importar productos';
  }

  /* ── Mapping ─────────────────────────────────────── */
  function normalizeText(s) {
    return String(s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim();
  }
  function guessIndex(headers, synonyms) {
    const norm = headers.map(h => normalizeText(h));
    for (let i = 0; i < norm.length; i++)
      for (const syn of synonyms)
        if (norm[i].includes(normalizeText(syn))) return i;
    return null;
  }

  function fillSelects(headers) {
    selectIds.forEach(id => {
      const sel = document.getElementById(id);
      if (!sel) return;
      sel.innerHTML = '';
      if (optIds.includes(id)) {
        const o = document.createElement('option'); o.value = ''; o.textContent = '— No importar —'; o.selected = true; sel.appendChild(o);
      } else {
        const o = document.createElement('option'); o.value = ''; o.textContent = '— Selecciona —'; o.disabled = true; o.selected = true; sel.appendChild(o);
      }
      headers.forEach((h, i) => {
        const o = document.createElement('option'); o.value = String(i); o.textContent = `${h} (col. ${i})`; sel.appendChild(o);
      });
    });
  }

  function autoMap(headers) {
    const mapping = {
      col_barcode:    ['codigo de barras','barcode','ean','upc'],
      col_name:       ['nombre','name','producto','product'],
      col_description:['descripcion','descripcion','detalle','desc'],
      col_quantity:   ['cantidad','stock','qty','quantity','existencia'],
      col_min_quantity:['min','minimo','min stock','stock minimo'],
      col_price:      ['precio','price','valor','costo','cost'],
      col_expiration_date:['vencimiento','expiration','expiration_date','fecha vencimiento','fecha de vencimiento']
    };
    const picked = new Set();
    Object.keys(mapping).forEach(id => {
      const sel = document.getElementById(id);
      if (!sel) return;
      const idx = guessIndex(headers, mapping[id]);
      if (idx === null) return;
      if (reqIds.includes(id) && picked.has(String(idx))) return;
      sel.value = String(idx);
      if (reqIds.includes(id)) picked.add(String(idx));
    });
  }

  function validateMapping(showAlerts) {
    clearNode(previewAlerts);
    const values = {};
    selectIds.forEach(id => { const s = document.getElementById(id); values[id] = s ? s.value : ''; });

    const missing = reqIds.filter(id => !values[id]);
    if (missing.length) {
      if (showAlerts) addInlineAlert(previewAlerts, 'Completa el mapeo de los campos obligatorios (*).', 'warning');
      return false;
    }
    const seen = new Map(), dups = [];
    reqIds.forEach(id => {
      const v = values[id];
      if (seen.has(v)) dups.push([seen.get(v), id, v]);
      else seen.set(v, id);
    });
    if (dups.length) {
      if (showAlerts) addInlineAlert(previewAlerts, 'No uses la misma columna en dos campos obligatorios.', 'error');
      return false;
    }
    return true;
  }

  /* ── Table builder ───────────────────────────────── */
  function buildTable(headers, rows) {
    thead.innerHTML = ''; tbody.innerHTML = '';

    const htr = document.createElement('tr');
    headers.forEach(h => {
      const th = document.createElement('th');
      th.textContent = h;
      th.className = 'ci-th';
      htr.appendChild(th);
    });
    thead.appendChild(htr);

    rows.slice(0, 10).forEach(r => {
      const tr = document.createElement('tr');
      tr.className = 'ci-tr';
      (Array.isArray(r) ? r : []).forEach(cell => {
        const td = document.createElement('td');
        td.textContent = (cell === null || cell === undefined) ? '' : String(cell);
        td.className = 'ci-td';
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  function resetPreview() {
    setPreviewVisible(false);
    clearNode(previewAlerts);
    previewMeta.textContent = '';
    tempKeyInput.value = '';
    thead.innerHTML = ''; tbody.innerHTML = '';
    selectIds.forEach(id => { const s = document.getElementById(id); if (s) s.innerHTML = ''; });
    setLoadingImport(false);
  }

  /* ── Submit: preview ─────────────────────────────── */
  importForm.addEventListener('submit', async e => {
    e.preventDefault();
    clearNode(importAlerts);

    const file = droppedFile || (fileInput.files && fileInput.files[0]);
    if (!file) { if (typeof NotificationManager !== 'undefined') NotificationManager.error('Selecciona un archivo CSV antes de previsualizar.'); return; }

    let d = (delimInp.value || '').trim();
    if (!d) d = ',';
    if (d.length > 1) d = d.slice(0, 1);
    delimInp.value = d;

    setLoadingPreview(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('delimiter', d);
      fd.append('has_header', document.getElementById('has_header').checked ? '1' : '0');
      
      const action = importForm.getAttribute('action') || window.location.href;
      const res = await fetch(action, { method: 'POST', body: fd });

      if (!res.ok) {
        const errorText = await res.text();
        console.error('Error response:', res.status, errorText);
        addInlineAlert(importAlerts, `Error ${res.status}: No se pudo procesar el archivo.`, 'error');
        return;
      }

      let responseText = await res.text();
      let _data;
      try {
        _data = JSON.parse(responseText);
      } catch (parseErr) {
        console.error('JSON parse error:', parseErr);
        console.error('Response text:', responseText.substring(0, 500));
        addInlineAlert(importAlerts, 'Respuesta inválida del servidor.', 'error');
        return;
      }

      const data = _data;
      const headers = Array.isArray(data.headers) ? data.headers.map(h => String(h)) : [];
      const rows    = Array.isArray(data.rows)    ? data.rows : [];

      if (!data || !data.temp_key) {
        addInlineAlert(importAlerts, 'La previsualización no devolvió una clave temporal. Intenta nuevamente.', 'error');
        return;
      }

      tempKeyInput.value    = data.temp_key;
      previewMeta.textContent = `${headers.length} columna${headers.length !== 1 ? 's' : ''} · ${Math.min(rows.length, 10)} fila${Math.min(rows.length,10) !== 1 ? 's' : ''} de muestra`;

      buildTable(headers, rows);
      fillSelects(headers);
      autoMap(headers);
      setPreviewVisible(true);
      validateMapping(false);

      if (typeof NotificationManager !== 'undefined') NotificationManager.success('Previsualización lista.');
    } catch (err) {
      addInlineAlert(importAlerts, 'Ocurrió un error inesperado al previsualizar. Intenta de nuevo.', 'error');
      console.log('Error en previsualización:', err);
      if (typeof NotificationManager !== 'undefined') NotificationManager.error('Error al previsualizar el CSV.');
    } finally {
      setLoadingPreview(false);
    }
  });

  /* ── Submit: import ──────────────────────────────── */
  confirmForm.addEventListener('submit', e => {
    if (!validateMapping(true)) { e.preventDefault(); return; }
    setLoadingImport(true);
  });

  selectIds.forEach(id => {
    const sel = document.getElementById(id);
    if (sel) sel.addEventListener('change', () => validateMapping(false));
  });

  document.getElementById('cancelPreview').addEventListener('click', resetPreview);
})();
