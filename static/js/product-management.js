/**
 * Product Management CRUD Operations
 * Handles product list, search, filtering, editing, deletion and attributes
 */

(function() {
  'use strict';

  let pageProducts = [];
  let currentPage  = 1;
  let totalPages   = 1;
  let pageSize     = 50;
  let currentProductId = null;

  // ===== SELECCIÓN MASIVA / EDICIÓN DE PRECIOS EN LOTE =====
  // Map<productId, productSnapshot> — persiste la selección entre cambios de página.
  let selectedProducts = new Map();
  let lastRenderTotal  = 0;
  let lastRenderPages  = 1;

  function $(id) { return document.getElementById(id); }
  function show(el) { if (el) el.style.display = ''; }
  function hide(el) { if (el) el.style.display = 'none'; }

  // ===== ATRIBUTOS DINÁMICOS =====
  async function loadProductAttributes(productId) {
    currentProductId = productId;
    const container = $('attributes-container');
    const loading = $('attributes-loading');
    const addBtn = $('add-attribute-btn');

    show(loading);
    container.innerHTML = '';
    hide(addBtn);

    try {
      const res = await fetch(`/api/products/${productId}/attributes`, {
        credentials: 'same-origin'
      });

      if (!res.ok) {
        container.innerHTML = '<div class="attribute-empty">No hay atributos configurados</div>';
        show(addBtn);
        hide(loading);
        return;
      }

      const json = await res.json();
      const data = json.data || [];

      hide(loading);

      if (data.length === 0) {
        container.innerHTML = '<div class="attribute-empty">No hay atributos disponibles</div>';
        show(addBtn);
        return;
      }

      data.forEach(attr => renderAttributeField(attr));
      show(addBtn);

    } catch (error) {
      console.error('Error cargando atributos:', error);
      hide(loading);
      container.innerHTML = '<div class="attribute-empty">Error cargando atributos</div>';
      show(addBtn);
    }
  }

  function renderAttributeField(attr) {
    const container = $('attributes-container');
    const fieldDiv = document.createElement('div');
    fieldDiv.className = 'attribute-field';
    fieldDiv.dataset.attributeId = attr.attribute_id;

    const header = document.createElement('div');
    header.className = 'attribute-field-header';

    const label = document.createElement('label');
    label.innerHTML = escapeHtml(attr.name) + (attr.required ? '<span class="required">*</span>' : '');

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'attribute-delete-btn';
    deleteBtn.type = 'button';
    deleteBtn.textContent = 'Eliminar';
    deleteBtn.onclick = (e) => {
      e.preventDefault();
      openDeleteAttributeModal(attr.attribute_id, attr.name);
    };

    header.appendChild(label);
    header.appendChild(deleteBtn);

    const input = document.createElement('input');
    input.type = attr.data_type === 'date' ? 'date' : 'text';
    input.value = (attr.value && attr.value.trim()) ? attr.value.trim() : '';
    input.dataset.attributeId = attr.attribute_id;
    input.dataset.dataType = attr.data_type;
    input.required = attr.required;
    input.placeholder = escapeHtml(attr.name);

    fieldDiv.appendChild(header);
    fieldDiv.appendChild(input);
    container.appendChild(fieldDiv);
  }

  async function saveProductAttributes(productId) {
    const inputs = document.querySelectorAll('[data-attribute-id]');
    if (inputs.length === 0) return true;

    const attributes = [];
    let isValid = true;

    inputs.forEach(input => {
      const rawValue = input.value;
      const value = (rawValue && typeof rawValue === 'string') ? rawValue.trim() : '';

      if (input.required && !value) {
        input.style.borderColor = 'var(--danger)';
        isValid = false;
      } else {
        input.style.borderColor = '';
      }

      attributes.push({
        attribute_id: parseInt(input.dataset.attributeId),
        value: value || null
      });
    });

    if (!isValid) {
      $('edit-error').textContent = 'Completa todos los atributos requeridos';
      show($('edit-error'));
      return false;
    }

    try {
      const res = await fetch(`/api/products/${productId}/attributes`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ attributes })
      });

      const text = await res.text();
      let json = {};
      try {
        json = text ? JSON.parse(text) : {};
      } catch (e) {
        console.error('JSON inválido:', text);
        throw new Error('Respuesta inválida del servidor');
      }

      if (!res.ok) {
        $('edit-error').textContent = 'Error: ' + (json.error || json.message || res.statusText);
        show($('edit-error'));
        return false;
      }

      return true;
    } catch (error) {
      console.error('Error guardando atributos:', error);
      $('edit-error').textContent = error.message || 'Error guardando atributos';
      show($('edit-error'));
      return false;
    }
  }

  function openNewAttributeModal() {
    $('new-attr-product-id').value = currentProductId;
    $('new-attr-name').value = '';
    $('new-attr-type').value = '';
    $('new-attr-required').checked = false;
    hide($('new-attr-error'));
    show($('new-attribute-modal'));
    $('new-attribute-modal').setAttribute('aria-hidden', 'false');
    $('new-attr-name').focus();
  }

  function closeNewAttributeModal() {
    hide($('new-attribute-modal'));
    $('new-attribute-modal').setAttribute('aria-hidden', 'true');
  }

  async function handleNewAttributeSubmit(e) {
    e.preventDefault();
    const productId = $('new-attr-product-id').value;
    const name = $('new-attr-name').value.trim();
    const dataType = $('new-attr-type').value;
    const required = $('new-attr-required').checked ? 1 : 0;

    if (!name || !dataType) {
      $('new-attr-error').textContent = 'Completa todos los campos';
      show($('new-attr-error'));
      return;
    }

    try {
      const res = await fetch(`/api/products/${productId}/attributes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ name, data_type: dataType, required })
      });

      const json = await res.json();
      if (!res.ok) {
        $('new-attr-error').textContent = 'Error: ' + json.error;
        show($('new-attr-error'));
        return;
      }

      closeNewAttributeModal();
      if (typeof Notify !== 'undefined') Notify.success('Atributo creado correctamente');
      loadProductAttributes(productId);
    } catch (error) {
      console.error('Error:', error);
      $('new-attr-error').textContent = error.message;
      show($('new-attr-error'));
    }
  }

  function openDeleteAttributeModal(attrId, attrName) {
    $('delete-attr-id').value = attrId;
    $('delete-attr-name').textContent = attrName;
    show($('delete-attribute-modal'));
    $('delete-attribute-modal').setAttribute('aria-hidden', 'false');
  }

  function closeDeleteAttributeModal() {
    hide($('delete-attribute-modal'));
    $('delete-attribute-modal').setAttribute('aria-hidden', 'true');
  }

  async function confirmDeleteAttribute() {
    const attrId = $('delete-attr-id').value;
    const productId = currentProductId;

    try {
      const res = await fetch(`/api/attributes/${attrId}`, {
        method: 'DELETE',
        credentials: 'same-origin'
      });

      if (!res.ok) {
        const json = await res.json();
        throw new Error(json.error || 'Error al eliminar');
      }

      closeDeleteAttributeModal();
      if (typeof Notify !== 'undefined') Notify.success('Atributo eliminado correctamente');
      loadProductAttributes(productId);
    } catch (error) {
      if (typeof Notify !== 'undefined') Notify.error(error.message || 'Error al eliminar atributo');
    }
  }

  function buildParams(page) {
    const search  = ($('search').value || '').trim();
    const sortRaw = $('sort-by').value;
    const [sort, order] = sortRaw.split('_');
    const p = new URLSearchParams({
      page: page,
      limit: pageSize,
      view_mode: $('filter-stock').value,
      sort: sort,
      order: order,
    });
    if (search) p.set('search', search);
    return p;
  }

  async function fetchPage(page) {
    const loadingState = $('loading-state');
    const emptyState   = $('empty-state');
    const errorState   = $('error-state');
    const tableBody    = $('products-table-body');

    show(loadingState);
    hide(emptyState);
    hide(errorState);
    hide($('pagination-controls'));
    hide($('pagination-info-top'));
    tableBody.innerHTML = '';

    try {
      const res = await fetch('/api/products_all?' + buildParams(page), {
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' }
      });

      if (res.status === 401) { window.location.href = '/login'; return; }
      if (!res.ok) throw new Error('Error ' + res.status + ': ' + res.statusText);

      const json   = await res.json();
      pageProducts = json.data  || [];
      currentPage  = json.page  || 1;
      totalPages   = json.pages || 1;

      hide(loadingState);
      renderTable(pageProducts, json.total || 0, totalPages);
      loadStats();

    } catch (err) {
      console.error('Error cargando productos:', err);
      if (typeof Notify !== 'undefined') Notify.error('Error al cargar los productos.');
      hide(loadingState);
      $('error-message').textContent = err.message || 'No se pudieron cargar los productos.';
      show(errorState);
    }
  }

  function loadProducts() { fetchPage(currentPage); }
  function applyFilters() { fetchPage(1); }

  function renderTable(products, total, pages) {
    const tableBody          = $('products-table-body');
    const emptyState         = $('empty-state');
    const paginationControls = $('pagination-controls');
    const paginationInfoTop  = $('pagination-info-top');

    $('products-count').textContent = total + ' producto' + (total !== 1 ? 's' : '');
    lastRenderTotal = total;
    lastRenderPages = pages;

    if (products.length === 0) {
      tableBody.innerHTML = '';
      show(emptyState);
      hide(paginationControls);
      hide(paginationInfoTop);
      syncSelectAllCheckbox();
      updateBulkBar();
      return;
    }

    hide(emptyState);

    const startIndex = (currentPage - 1) * pageSize;
    $('page-from').textContent  = startIndex + 1;
    $('page-to').textContent    = Math.min(startIndex + products.length, total);
    $('page-total').textContent = total;
    show(paginationInfoTop);

    let html = '';
    for (let i = 0; i < products.length; i++) {
      const p      = products[i];
      const status = getStockStatus(p);
      const name   = escapeHtml(p.name);
      const desc   = p.description
        ? escapeHtml(p.description.substring(0, 50)) + (p.description.length > 50 ? '...' : '')
        : '';
      const price  = (p.price || 0).toFixed(2);
      const isSelected = selectedProducts.has(p.id);

      html +=
        '<tr data-id="' + p.id + '" class="' + (isSelected ? 'row-selected' : '') + '">' +
          '<td style="padding:0.875rem 0.75rem;text-align:center;vertical-align:middle;width:2.5rem;"><input type="checkbox" class="row-select-checkbox" data-select-id="' + p.id + '"' + (isSelected ? ' checked' : '') + ' aria-label="Seleccionar ' + name + '"></td>' +
          '<td style="padding:0.875rem 1rem;"><span class="mono" style="font-size:0.85rem;color:var(--text-muted);">' + (p.barcode || '—') + '</span></td>' +
          '<td style="padding:0.875rem 1rem;"><div style="font-weight:600;">' + name + '</div>' +
            (desc ? '<div class="text-muted" style="font-size:0.8rem;margin-top:0.25rem;">' + desc + '</div>' : '') + '</td>' +
          '<td style="padding:0.875rem 1rem;text-align:center;"><span class="mono" style="font-size:1rem;font-weight:600;color:' + status.color + ';">' + (p.stock || 0) + '</span></td>' +
          '<td style="padding:0.875rem 1rem;text-align:center;"><span class="mono text-muted">' + (p.min_stock || 0) + '</span></td>' +
          '<td style="padding:0.875rem 1rem;text-align:right;"><span class="mono" style="font-weight:600;">$' + price + '</span></td>' +
          '<td style="padding:0.875rem 1rem;text-align:center;"><span class="status-badge ' + status.cssClass + '">' + status.text + '</span></td>' +
          '<td style="padding:0.875rem 1rem;text-align:center;"><span class="mono text-muted">' + (p.expiration_date || '—') + '</span></td>' +
          '<td style="padding:0.875rem 1rem;text-align:center;">' +
            '<div style="display:flex;gap:0.25rem;justify-content:center;">' +
              '<button class="action-btn stock" data-action="stock" data-id="' + p.id + '" title="Ajustar stock"><svg style="width:18px;height:18px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/></svg></button>' +
              '<button class="action-btn edit"  data-action="edit"  data-id="' + p.id + '" title="Editar"><svg style="width:18px;height:18px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg></button>' +
              (p.status === 0 ? '<button class="action-btn reactivate" data-action="reactivate" data-id="' + p.id + '" title="Reactivar"><svg style="width:18px;height:18px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg></button>' : '<button class="action-btn delete" data-action="delete" data-id="' + p.id + '" title="Eliminar"><svg style="width:18px;height:18px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button>') +
            '</div>' +
          '</td>' +
        '</tr>';
    }
    tableBody.innerHTML = html;

    renderPaginationButtons(pages);
    show(paginationControls);
    syncSelectAllCheckbox();
    updateBulkBar();
    tableBody.closest('.card').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function renderPaginationButtons(totalPages) {
    const container = $('page-buttons');
    if (totalPages <= 1) { container.innerHTML = ''; return; }

    let pages = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (currentPage > 3) pages.push('...');
      for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) {
        pages.push(i);
      }
      if (currentPage < totalPages - 2) pages.push('...');
      pages.push(totalPages);
    }

    let html = '';
    html += '<button ' + (currentPage === 1 ? 'disabled' : 'onclick="goToPage(' + (currentPage - 1) + ')"') + ' title="Anterior">' +
      '<svg style="width:14px;height:14px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>' +
    '</button>';

    for (let i = 0; i < pages.length; i++) {
      const p = pages[i];
      if (p === '...') {
        html += '<span class="page-ellipsis">…</span>';
      } else {
        html += '<button class="' + (p === currentPage ? 'active' : '') + '" onclick="goToPage(' + p + ')">' + p + '</button>';
      }
    }

    html += '<button ' + (currentPage === totalPages ? 'disabled' : 'onclick="goToPage(' + (currentPage + 1) + ')"') + ' title="Siguiente">' +
      '<svg style="width:14px;height:14px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>' +
    '</button>';

    container.innerHTML = html;
  }

  function goToPage(page) {
    if (page < 1 || page > totalPages) return;
    fetchPage(page);
  }

  async function loadStats() {
    try {
      const res = await fetch('/api/stats', { credentials: 'same-origin' });
      if (!res.ok) return;
      const d = await res.json();
      $('stat-total').textContent     = d.products  || 0;
      $('stat-low-stock').textContent = d.low_stock || 0;

      const [rIn, rOut] = await Promise.all([
        fetch('/api/products_all?view_mode=in_stock&limit=1',     { credentials: 'same-origin' }),
        fetch('/api/products_all?view_mode=out_of_stock&limit=1', { credentials: 'same-origin' }),
      ]);
      if (rIn.ok)  { const j = await rIn.json();  $('stat-in-stock').textContent  = j.total || 0; }
      if (rOut.ok) { const j = await rOut.json(); $('stat-out-stock').textContent = j.total || 0; }
    } catch (_) { /* stats no son críticos */ }
  }

  function getStockStatus(product) {
    const stock    = product.stock || 0;
    const minStock = product.min_stock || 0;
    if (product.status === 0) return { cssClass: 'out-of-stock', text: 'Deshabilitado', color: 'var(--danger)' };
    if (stock === 0)          return { cssClass: 'out-of-stock', text: 'Sin stock',     color: 'var(--danger)' };
    if (stock <= minStock)    return { cssClass: 'low-stock',    text: 'Stock bajo',    color: 'var(--warning)' };
    return                           { cssClass: 'in-stock',     text: 'En stock',      color: 'var(--success)' };
  }

  function openEditModal(productId) {
    const product = pageProducts.find(p => p.id === productId);
    if (!product) return;
    $('edit-id').value           = product.id;
    $('edit-barcode').value      = product.barcode || '';
    $('edit-name').value         = product.name || '';
    $('edit-description').value  = product.description || '';
    $('edit-quantity').value     = product.stock || 0;
    $('edit-min-quantity').value = product.min_stock || 0;
    $('edit-price').value        = product.price || 0;
    $('edit-expiration-date').value = product.expiration_date || '';
    $('edit-status').checked     = product.status === 1;
    hide($('edit-error'));
    show($('edit-modal'));
    loadProductAttributes(productId);
    $('edit-modal').setAttribute('aria-hidden', 'false');

    // Reinitialize CalendarPicker for the expiration date field
    if (typeof CalendarPicker !== 'undefined') {
      const input = $('edit-expiration-date');
      if (input._calendarPicker) {
        input._calendarPicker.destroy?.();
        delete input._calendarPicker;
      }
      new CalendarPicker('#edit-expiration-date', {
        minYear: 2020,
        maxYear: 2030
      });
    }
  }

  function closeEditModal() {
    hide($('edit-modal'));
    $('edit-modal').setAttribute('aria-hidden', 'true');
  }

  async function handleEditSubmit(e) {
    e.preventDefault();
    const productId = $('edit-id').value;
    const data = {
      name:         $('edit-name').value,
      description:  $('edit-description').value,
      quantity:     parseInt($('edit-quantity').value) || 0,
      min_quantity: parseInt($('edit-min-quantity').value) || 0,
      price:        parseFloat($('edit-price').value) || 0,
      expiration_date: $('edit-expiration-date').value || null,
      status:       $('edit-status').checked ? 1 : 0
    };

    try {
      const response = await fetch('/api/products/' + productId, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Error al actualizar');
      }

      const attrsSaved = await saveProductAttributes(productId);
      if (!attrsSaved) return;

      closeEditModal();
      if (typeof Notify !== 'undefined') Notify.success('Producto actualizado correctamente');
      loadProducts();
    } catch (error) {
      Notify.error(error.message || 'Error al actualizar producto');
      $('edit-error').textContent = error.message;
      show($('edit-error'));
    }
  }

  function openDeleteModal(productId) {
    const product = pageProducts.find(p => p.id === productId);
    if (!product) return;
    $('delete-product-id').value         = productId;
    $('delete-product-name').textContent = product.name || 'este producto';
    show($('delete-modal'));
    $('delete-modal').setAttribute('aria-hidden', 'false');
  }

  function closeDeleteModal() {
    hide($('delete-modal'));
    $('delete-modal').setAttribute('aria-hidden', 'true');
  }

  async function confirmDelete() {
    const productId = $('delete-product-id').value;
    try {
      const response = await fetch('/api/products/' + productId, {
        method: 'DELETE',
        credentials: 'same-origin'
      });
      if (!response.ok) { const err = await response.json(); throw new Error(err.error || 'Error al deshabilitar'); }
      closeDeleteModal();
      if (typeof Notify !== 'undefined') Notify.success('Producto deshabilitado correctamente');
      loadProducts();
    } catch (error) {
      if (typeof Notify !== 'undefined') Notify.error(error.message || 'Error al deshabilitar producto');
    }
  }

  function openStockModal(productId) {
    const product = pageProducts.find(p => p.id === productId);
    if (!product) return;
    $('stock-product-id').value       = productId;
    $('stock-product-name').textContent = product.name || '';
    $('stock-current').textContent    = product.stock || 0;
    $('stock-adjustment').value       = product.stock || 0;
    show($('stock-modal'));
    $('stock-modal').setAttribute('aria-hidden', 'false');
  }

  function closeStockModal() {
    hide($('stock-modal'));
    $('stock-modal').setAttribute('aria-hidden', 'true');
  }

  async function saveStockAdjustment() {
    const productId = $('stock-product-id').value;
    const newStock  = parseInt($('stock-adjustment').value) || 0;
    try {
      const response = await fetch('/api/products/' + productId, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quantity: newStock })
      });
      if (!response.ok) { const err = await response.json(); throw new Error(err.error || 'Error al actualizar stock'); }
      closeStockModal();
      if (typeof Notify !== 'undefined') Notify.success('Stock actualizado correctamente');
      loadProducts();
    } catch (error) {
      if (typeof Notify !== 'undefined') Notify.error(error.message || 'Error al actualizar stock');
    }
  }

  function redirectToEditPage(productId) {
    window.location.href = '/products/' + productId + '/edit';
  }

  function openReactivateModal(productId) {
    const product = pageProducts.find(p => p.id === productId);
    if (!product) return;
    $('reactivate-product-id').value = productId;
    $('reactivate-product-name').textContent = product.name || 'este producto';
    show($('reactivate-modal'));
    $('reactivate-modal').setAttribute('aria-hidden', 'false');
  }

  function closeReactivateModal() {
    hide($('reactivate-modal'));
    $('reactivate-modal').setAttribute('aria-hidden', 'true');
  }

  async function confirmReactivate() {
    const productId = $('reactivate-product-id').value;
    try {
      const response = await fetch('/api/products/' + productId + '/activate', {
        method: 'POST',
        credentials: 'same-origin'
      });
      if (!response.ok) { const err = await response.json(); throw new Error(err.error || 'Error al reactivar'); }
      closeReactivateModal();
      if (typeof Notify !== 'undefined') Notify.success('Producto reactivado correctamente');
      loadProducts();
    } catch (error) {
      if (typeof Notify !== 'undefined') Notify.error(error.message || 'Error al reactivar producto');
    }
  }

  // ======================================================================
  // SELECCIÓN MASIVA DE PRODUCTOS
  // ======================================================================

  function handleTableChange(e) {
    const cb = e.target.closest('.row-select-checkbox');
    if (!cb) return;
    const id = parseInt(cb.getAttribute('data-select-id'));
    setRowSelected(id, cb.checked);
  }

  function setRowSelected(id, selected) {
    const product = pageProducts.find(p => p.id === id);
    if (selected) {
      if (product) selectedProducts.set(id, product);
    } else {
      selectedProducts.delete(id);
    }
    const cb = document.querySelector('.row-select-checkbox[data-select-id="' + id + '"]');
    if (cb) cb.checked = selected;
    const row = cb ? cb.closest('tr') : null;
    if (row) row.classList.toggle('row-selected', selected);
    syncSelectAllCheckbox();
    updateBulkBar();
  }

  function toggleSelectAllOnPage(e) {
    const checked = e.target.checked;
    document.querySelectorAll('.row-select-checkbox').forEach(cb => {
      const id = parseInt(cb.getAttribute('data-select-id'));
      const product = pageProducts.find(p => p.id === id);
      cb.checked = checked;
      if (checked) {
        if (product) selectedProducts.set(id, product);
      } else {
        selectedProducts.delete(id);
      }
      const row = cb.closest('tr');
      if (row) row.classList.toggle('row-selected', checked);
    });
    syncSelectAllCheckbox();
    updateBulkBar();
  }

  function syncSelectAllCheckbox() {
    const selectAll = $('select-all-checkbox');
    if (!selectAll) return;
    const rowCheckboxes = document.querySelectorAll('.row-select-checkbox');
    if (rowCheckboxes.length === 0) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
      return;
    }
    const checkedCount = document.querySelectorAll('.row-select-checkbox:checked').length;
    selectAll.checked = checkedCount === rowCheckboxes.length;
    selectAll.indeterminate = checkedCount > 0 && checkedCount < rowCheckboxes.length;
  }

  function clearSelection() {
    selectedProducts.clear();
    document.querySelectorAll('.row-select-checkbox').forEach(cb => {
      cb.checked = false;
      const row = cb.closest('tr');
      if (row) row.classList.remove('row-selected');
    });
    syncSelectAllCheckbox();
    updateBulkBar();
  }

  function updateBulkBar() {
    const bar = $('bulk-actions-bar');
    if (!bar) return;
    const count = selectedProducts.size;
    if (count === 0) {
      hide(bar);
      return;
    }
    const countEl = $('bulk-selected-count');
    const labelEl = $('bulk-selected-label');
    if (countEl) countEl.textContent = count;
    if (labelEl) labelEl.textContent = count === 1 ? 'producto seleccionado' : 'productos seleccionados';
    bar.style.display = 'flex';
  }

  // ======================================================================
  // AJUSTE MASIVO DE PRECIOS
  // ======================================================================

  function getPriceMax() {
    const modal = $('bulk-price-modal');
    const raw = modal ? parseFloat(modal.getAttribute('data-price-max')) : NaN;
    return (isFinite(raw) && raw > 0) ? raw : 999999999;
  }

  function computeNewPrice(currentPrice, mode, sign, value) {
    const base = currentPrice || 0;
    if (mode === 'percent') {
      const factor = value / 100;
      return sign === 'decrease' ? base * (1 - factor) : base * (1 + factor);
    }
    if (mode === 'fixed') {
      return sign === 'decrease' ? base - value : base + value;
    }
    return value; // exact
  }

  function roundCurrency(n) {
    return Math.round((n + Number.EPSILON) * 100) / 100;
  }

  function getBulkFormValues() {
    const modeInput = document.querySelector('input[name="bulk-mode"]:checked');
    const mode = modeInput ? modeInput.value : 'percent';
    const sign = $('bulk-sign').value;
    const rawValue = $('bulk-value').value;
    const value = rawValue === '' ? NaN : parseFloat(rawValue);
    const includeDisabled = $('bulk-include-disabled').checked;
    return { mode, sign, value, includeDisabled };
  }

  function validateBulkValue(mode, sign, value) {
    if (isNaN(value) || !isFinite(value)) return 'Ingresa un valor numérico válido.';
    if (value < 0) return 'El valor no puede ser negativo.';
    if (mode === 'percent') {
      if (value === 0) return 'El porcentaje debe ser mayor a 0.';
      if (sign === 'decrease' && value > 100) return 'No puedes disminuir más del 100%.';
    }
    if (mode === 'fixed' && value === 0) {
      return 'El monto debe ser mayor a 0.';
    }
    if (mode === 'exact') {
      const max = getPriceMax();
      if (value > max) return 'El precio excede el máximo permitido ($' + max.toFixed(2) + ').';
    }
    return null;
  }

  function getSelectedForOperation(includeDisabled) {
    const all = Array.from(selectedProducts.values());
    const included = all.filter(p => includeDisabled || p.status !== 0);
    const excludedDisabledCount = all.length - included.length;
    return { included, excludedDisabledCount };
  }

  function updateBulkModeUI() {
    const modeInput = document.querySelector('input[name="bulk-mode"]:checked');
    const mode = modeInput ? modeInput.value : 'percent';
    const signField  = $('bulk-sign-field');
    const valueLabel = $('bulk-value-label');
    const suffix     = $('bulk-value-suffix');
    const valueInput = $('bulk-value');

    if (mode === 'exact') {
      hide(signField);
      valueLabel.textContent = 'Nuevo precio exacto';
      suffix.textContent = '$';
      valueInput.placeholder = 'Ej: 1500.00';
    } else if (mode === 'percent') {
      show(signField);
      valueLabel.textContent = 'Porcentaje a aplicar';
      suffix.textContent = '%';
      valueInput.placeholder = 'Ej: 10';
    } else {
      show(signField);
      valueLabel.textContent = 'Monto a aplicar';
      suffix.textContent = '$';
      valueInput.placeholder = 'Ej: 50.00';
    }
  }

  function renderBulkPreviewRows(rows) {
    const body = $('bulk-preview-body');
    if (!body) return;
    if (rows.length === 0) {
      body.innerHTML = '';
      return;
    }
    let html = '';
    rows.forEach(r => {
      html += '<tr class="' + (r.negative ? 'preview-row-invalid' : '') + '">' +
        '<td>' + escapeHtml(r.name) + (r.disabled ? '<span class="preview-tag disabled-tag">Deshabilitado</span>' : '') + '</td>' +
        '<td style="text-align:right;" class="mono">$' + r.currentPrice.toFixed(2) + '</td>' +
        '<td style="text-align:center;">' + r.adjustmentLabel + '</td>' +
        '<td style="text-align:right;" class="mono">' + (r.negative ? '<span class="preview-tag negative-tag">Inválido</span>' : '$' + r.newPrice.toFixed(2)) + '</td>' +
      '</tr>';
    });
    body.innerHTML = html;
  }

  function updateBulkPreview() {
    const { mode, sign, value, includeDisabled } = getBulkFormValues();
    const errorEl      = $('bulk-form-error');
    const reviewBtn     = $('bulk-review-btn');
    const emptyEl       = $('bulk-preview-empty');
    const wrapperEl     = $('bulk-preview-wrapper');
    const excludedNote  = $('bulk-excluded-note');

    hide(errorEl);
    $('bulk-modal-count').textContent = selectedProducts.size;

    const { included, excludedDisabledCount } = getSelectedForOperation(includeDisabled);

    if (excludedNote) {
      if (excludedDisabledCount > 0) {
        excludedNote.textContent = excludedDisabledCount + ' producto(s) deshabilitado(s) de tu selección se omitirán de este ajuste.';
        show(excludedNote);
      } else {
        hide(excludedNote);
      }
    }

    const validationMsg = validateBulkValue(mode, sign, value);
    if (validationMsg) {
      hide(wrapperEl);
      show(emptyEl);
      emptyEl.textContent = 'Ingresa un valor válido para ver la vista previa de los cambios.';
      $('bulk-preview-affected-count').textContent = '0';
      reviewBtn.disabled = true;
      if ($('bulk-value').value !== '') {
        errorEl.textContent = validationMsg;
        show(errorEl);
      }
      return;
    }

    if (included.length === 0) {
      hide(wrapperEl);
      show(emptyEl);
      emptyEl.textContent = 'No hay productos habilitados en tu selección. Activa "Incluir productos deshabilitados" o cambia tu selección.';
      $('bulk-preview-affected-count').textContent = '0';
      reviewBtn.disabled = true;
      return;
    }

    let hasNegative = false;
    const rows = included.map(p => {
      const currentPrice = p.price || 0;
      const newPrice = roundCurrency(computeNewPrice(currentPrice, mode, sign, value));
      const negative = newPrice < 0;
      if (negative) hasNegative = true;

      let adjustmentLabel;
      if (mode === 'percent')      adjustmentLabel = (sign === 'decrease' ? '−' : '+') + value + '%';
      else if (mode === 'fixed')   adjustmentLabel = (sign === 'decrease' ? '−$' : '+$') + value.toFixed(2);
      else                         adjustmentLabel = '= $' + value.toFixed(2);

      return { id: p.id, name: p.name, disabled: p.status === 0, currentPrice, newPrice, negative, adjustmentLabel };
    });

    hide(emptyEl);
    show(wrapperEl);
    renderBulkPreviewRows(rows);
    $('bulk-preview-affected-count').textContent = rows.length;

    if (hasNegative) {
      errorEl.textContent = 'Algunos productos quedarían con precio negativo con este ajuste. Reduce el valor antes de continuar.';
      show(errorEl);
      reviewBtn.disabled = true;
    } else {
      reviewBtn.disabled = false;
    }
  }

  function setBulkFormDisabled(disabled) {
    document.querySelectorAll('input[name="bulk-mode"]').forEach(el => { el.disabled = disabled; });
    $('bulk-sign').disabled = disabled;
    $('bulk-value').disabled = disabled;
    $('bulk-include-disabled').disabled = disabled;
  }

  function setBulkMainActionsVisible(visible) {
    $('bulk-main-actions').style.display = visible ? 'flex' : 'none';
  }

  function resetBulkForm() {
    document.querySelector('input[name="bulk-mode"][value="percent"]').checked = true;
    $('bulk-sign').value = 'increase';
    $('bulk-value').value = '';
    $('bulk-include-disabled').checked = false;
    hide($('bulk-form-error'));
    hide($('bulk-excluded-note'));
    updateBulkModeUI();
    setBulkFormDisabled(false);
    hide($('bulk-confirm-banner'));
    setBulkMainActionsVisible(true);
    const applyBtn = $('bulk-confirm-apply-btn');
    if (applyBtn) { applyBtn.disabled = false; applyBtn.textContent = 'Sí, aplicar cambios'; }
    const cancelBtn = $('bulk-confirm-cancel-btn');
    if (cancelBtn) cancelBtn.disabled = false;
  }

  function openBulkPriceModal() {
    if (selectedProducts.size === 0) return;
    resetBulkForm();
    $('bulk-modal-count').textContent = selectedProducts.size;
    show($('bulk-price-modal'));
    $('bulk-price-modal').setAttribute('aria-hidden', 'false');
    updateBulkPreview();
    $('bulk-value').focus();
  }

  function closeBulkPriceModal() {
    hide($('bulk-price-modal'));
    $('bulk-price-modal').setAttribute('aria-hidden', 'true');
  }

  function showBulkConfirmStep() {
    const { mode, includeDisabled } = getBulkFormValues();
    const { included } = getSelectedForOperation(includeDisabled);
    if (included.length === 0) return;
    $('bulk-confirm-count').textContent = included.length;
    setBulkMainActionsVisible(false);
    setBulkFormDisabled(true);
    show($('bulk-confirm-banner'));
  }

  function hideBulkConfirmStep() {
    hide($('bulk-confirm-banner'));
    setBulkFormDisabled(false);
    setBulkMainActionsVisible(true);
  }

  /**
   * ======================================================================
   * CAPA DE INTEGRACIÓN — AJUSTE MASIVO DE PRECIOS (applyBulkPriceUpdate)
   * ======================================================================
   * Backend real conectado: POST /api/products/update_price_bulk
   * (requiere rol admin/root — ver @require_role en la ruta Flask).
   *
   * IMPORTANTE: el backend real NO calcula precios ni informa detalle por
   * producto. Solo aplica el `new_price` que se le manda y devuelve
   * {"message": "..."} en éxito o {"error": "..."} en falla. Por eso TODO
   * el cálculo (porcentaje/monto/exacto) y TODA la validación (negativos,
   * deshabilitados, etc.) tienen que resolverse en el cliente ANTES de
   * llamar a este endpoint — ver `handleBulkApply`, que arma cada item
   * como { id, new_price } ya con el precio final calculado.
   *
   * Request  POST /api/products/update_price_bulk
   *   { "products": [ { "id": number, "new_price": number }, ... ] }
   *
   * Response 200
   *   { "message": "Precios actualizados exitosamente" }
   *
   * Response 400/401/403/500
   *   { "error": "..." }
   * ======================================================================
   */
  async function applyBulkPriceUpdate(items) {
    const response = await fetch('/api/products/update_price_bulk', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        products: items.map(p => ({
          id: p.id,
          new_price: p.newPrice
        }))
      })
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || 'Error al actualizar precios');
    }

    return result;
  }

  async function handleBulkApply() {
    const applyBtn  = $('bulk-confirm-apply-btn');
    const cancelBtn = $('bulk-confirm-cancel-btn');
    const { mode, sign, value, includeDisabled } = getBulkFormValues();
    const { included } = getSelectedForOperation(includeDisabled);

    if (included.length === 0) return;

    // El backend real solo aplica el precio final que le mandamos — todo el
    // cálculo (porcentaje / monto / exacto) vive acá, del lado del cliente.
    // Si algún producto quedaría con precio negativo lo excluimos por las
    // dudas (la vista previa ya bloquea llegar hasta acá en ese caso, esto
    // es solo una segunda barrera defensiva).
    const computedItems = [];
    const skippedNegative = [];
    included.forEach(p => {
      const currentPrice = p.price || 0;
      const newPrice = roundCurrency(computeNewPrice(currentPrice, mode, sign, value));
      if (newPrice < 0) {
        skippedNegative.push(p);
        return;
      }
      computedItems.push({ id: p.id, newPrice });
    });

    if (computedItems.length === 0) {
      if (typeof Notify !== 'undefined') Notify.error('No hay productos válidos para actualizar.');
      return;
    }

    applyBtn.disabled = true;
    cancelBtn.disabled = true;
    const originalLabel = applyBtn.textContent;
    applyBtn.innerHTML = '<span style="display:inline-block;width:12px;height:12px;border:2px solid rgba(255,255,255,0.4);border-top-color:#fff;border-radius:50%;vertical-align:-1px;margin-right:0.4rem;animation:spin 0.7s linear infinite;"></span>Aplicando...';

    try {
      await applyBulkPriceUpdate(computedItems);

      // El backend no devuelve detalle por producto, así que reflejamos en
      // la UI los precios que nosotros mismos calculamos y enviamos.
      computedItems.forEach(u => {
        const p = pageProducts.find(pp => pp.id === u.id);
        if (p) p.price = u.newPrice;
        if (selectedProducts.has(u.id)) selectedProducts.get(u.id).price = u.newPrice;
      });

      closeBulkPriceModal();
      clearSelection();
      renderTable(pageProducts, lastRenderTotal, lastRenderPages);

      if (typeof Notify !== 'undefined') {
        Notify.success(computedItems.length + ' producto(s) actualizados correctamente.');
        if (skippedNegative.length > 0) {
          Notify.error(skippedNegative.length + ' producto(s) se omitieron por quedar con precio negativo.');
        }
      }
    } catch (error) {
      console.error('Error aplicando ajuste masivo de precios:', error);
      if (typeof Notify !== 'undefined') Notify.error(error.message || 'Error al aplicar el ajuste masivo de precios.');
      applyBtn.disabled = false;
      cancelBtn.disabled = false;
      applyBtn.textContent = originalLabel;
    }
  }

  function handleTableClick(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.getAttribute('data-action');
    const id     = parseInt(btn.getAttribute('data-id'));
    if      (action === 'edit')       redirectToEditPage(id);
    else if (action === 'delete')     openDeleteModal(id);
    else if (action === 'stock')      openStockModal(id);
    else if (action === 'reactivate') openReactivateModal(id);
  }

  function init() {
    const searchInput = $('search');
    if (searchInput) {
      searchInput.addEventListener('input', debounce(applyFilters, 400));
    }

    const filterStock = $('filter-stock');
    if (filterStock) {
      filterStock.addEventListener('change', applyFilters);
    }

    const sortBy = $('sort-by');
    if (sortBy) {
      sortBy.addEventListener('change', applyFilters);
    }

    const pageSize_el = $('page-size');
    if (pageSize_el) {
      pageSize_el.addEventListener('change', function() {
        pageSize = parseInt(this.value);
        fetchPage(1);
      });
    }

    const editForm = $('edit-form');
    if (editForm) {
      editForm.addEventListener('submit', handleEditSubmit);
    }

    const newAttrForm = $('new-attribute-form');
    if (newAttrForm) {
      newAttrForm.addEventListener('submit', handleNewAttributeSubmit);
    }

    const addAttrBtn = $('add-attribute-btn');
    if (addAttrBtn) {
      addAttrBtn.addEventListener('click', (e) => {
        e.preventDefault();
        openNewAttributeModal();
      });
    }

    const tableBody = $('products-table-body');
    if (tableBody) {
      tableBody.addEventListener('click', handleTableClick);
      tableBody.addEventListener('change', handleTableChange);
    }

    const selectAllCb = $('select-all-checkbox');
    if (selectAllCb) {
      selectAllCb.addEventListener('change', toggleSelectAllOnPage);
    }

    const bulkClearBtn = $('bulk-clear-btn');
    if (bulkClearBtn) {
      bulkClearBtn.addEventListener('click', clearSelection);
    }

    const bulkPriceBtn = $('bulk-price-btn');
    if (bulkPriceBtn) {
      bulkPriceBtn.addEventListener('click', openBulkPriceModal);
    }

    const bulkPriceCloseBtn = $('bulk-price-close-btn');
    if (bulkPriceCloseBtn) {
      bulkPriceCloseBtn.addEventListener('click', closeBulkPriceModal);
    }

    const bulkPriceOverlay = $('bulk-price-overlay');
    if (bulkPriceOverlay) {
      bulkPriceOverlay.addEventListener('click', closeBulkPriceModal);
    }

    const bulkCancelBtn = $('bulk-cancel-btn');
    if (bulkCancelBtn) {
      bulkCancelBtn.addEventListener('click', closeBulkPriceModal);
    }

    document.querySelectorAll('input[name="bulk-mode"]').forEach(el => {
      el.addEventListener('change', function() {
        updateBulkModeUI();
        updateBulkPreview();
      });
    });

    const bulkSign = $('bulk-sign');
    if (bulkSign) {
      bulkSign.addEventListener('change', updateBulkPreview);
    }

    const bulkValue = $('bulk-value');
    if (bulkValue) {
      bulkValue.addEventListener('input', debounce(updateBulkPreview, 200));
    }

    const bulkIncludeDisabled = $('bulk-include-disabled');
    if (bulkIncludeDisabled) {
      bulkIncludeDisabled.addEventListener('change', updateBulkPreview);
    }

    const bulkReviewBtn = $('bulk-review-btn');
    if (bulkReviewBtn) {
      bulkReviewBtn.addEventListener('click', showBulkConfirmStep);
    }

    const bulkConfirmCancelBtn = $('bulk-confirm-cancel-btn');
    if (bulkConfirmCancelBtn) {
      bulkConfirmCancelBtn.addEventListener('click', hideBulkConfirmStep);
    }

    const bulkConfirmApplyBtn = $('bulk-confirm-apply-btn');
    if (bulkConfirmApplyBtn) {
      bulkConfirmApplyBtn.addEventListener('click', handleBulkApply);
    }

    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        closeEditModal();
        closeDeleteModal();
        closeStockModal();
        closeNewAttributeModal();
        closeDeleteAttributeModal();
        closeReactivateModal();
        closeBulkPriceModal();
      }
    });

    new CalendarPicker('input[name="expiration_date"]', {
      minYear: 2020,
      maxYear: 2030
    });

    fetchPage(1);
  }

  window.loadProducts            = loadProducts;
  window.closeEditModal          = closeEditModal;
  window.closeDeleteModal        = closeDeleteModal;
  window.closeStockModal         = closeStockModal;
  window.closeNewAttributeModal  = closeNewAttributeModal;
  window.closeDeleteAttributeModal = closeDeleteAttributeModal;
  window.closeReactivateModal    = closeReactivateModal;
  window.confirmDelete           = confirmDelete;
  window.confirmDeleteAttribute  = confirmDeleteAttribute;
  window.confirmReactivate       = confirmReactivate;
  window.saveStockAdjustment     = saveStockAdjustment;
  window.goToPage                = goToPage;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();