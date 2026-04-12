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

  function $(id) { return document.getElementById(id); }
  function show(el) { if (el) el.style.display = ''; }
  function hide(el) { if (el) el.style.display = 'none'; }

  function debounce(func, wait) {
    let timeout;
    return function(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

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

    if (products.length === 0) {
      tableBody.innerHTML = '';
      show(emptyState);
      hide(paginationControls);
      hide(paginationInfoTop);
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

      html +=
        '<tr data-id="' + p.id + '">' +
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
              '<button class="action-btn delete" data-action="delete" data-id="' + p.id + '" title="Eliminar"><svg style="width:18px;height:18px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button>' +
            '</div>' +
          '</td>' +
        '</tr>';
    }
    tableBody.innerHTML = html;

    renderPaginationButtons(pages);
    show(paginationControls);
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
      if (!response.ok) { const err = await response.json(); throw new Error(err.error || 'Error al eliminar'); }
      closeDeleteModal();
      if (typeof Notify !== 'undefined') Notify.success('Producto eliminado correctamente');
      loadProducts();
    } catch (error) {
      if (typeof Notify !== 'undefined') Notify.error(error.message || 'Error al eliminar producto');
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

  function handleTableClick(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.getAttribute('data-action');
    const id     = parseInt(btn.getAttribute('data-id'));
    if      (action === 'edit')   openEditModal(id);
    else if (action === 'delete') openDeleteModal(id);
    else if (action === 'stock')  openStockModal(id);
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
    }

    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        closeEditModal();
        closeDeleteModal();
        closeStockModal();
        closeNewAttributeModal();
        closeDeleteAttributeModal();
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
  window.confirmDelete           = confirmDelete;
  window.confirmDeleteAttribute  = confirmDeleteAttribute;
  window.saveStockAdjustment     = saveStockAdjustment;
  window.goToPage                = goToPage;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
