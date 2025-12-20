document.addEventListener('DOMContentLoaded', async () => {
  // Verificar salud de la API
  try {
    const healthRes = await fetch('/api/health');
    const healthData = await healthRes.json();
    const healthEl = document.getElementById('health');
    if (healthEl) healthEl.textContent = healthData.status || 'unknown';
  } catch (error) {
    const healthEl = document.getElementById('health');
    if (healthEl) healthEl.textContent = 'error';
  }

  // Cargar productos si estamos en dashboard
  if (document.getElementById('productsList')) {
    await loadProducts();
  }
});

// Función para cargar productos desde la API
async function loadProducts(filters = {}) {
  const container = document.getElementById('productsList');
  const loadingMsg = document.getElementById('loadingMessage');
  const emptyMsg = document.getElementById('emptyMessage');
  
  if (loadingMsg) loadingMsg.hidden = false;
  if (emptyMsg) emptyMsg.hidden = true;
  
  // Construir query string
  const params = new URLSearchParams();
  if (filters.search) params.append('search', filters.search);
  if (filters.category) params.append('category', filters.category);
  if (filters.view_mode) params.append('view_mode', filters.view_mode);
  
  try {
    const response = await fetch(`/api/products?${params}`);
    const products = await response.json();
    
    if (loadingMsg) loadingMsg.hidden = true;
    
    if (products.length === 0) {
      if (emptyMsg) emptyMsg.hidden = false;
      return;
    }
    
    renderProducts(products);
    
    // Actualizar contador
    const countDisplay = document.getElementById('products-count-display');
    if (countDisplay) countDisplay.textContent = products.length;
    
  } catch (error) {
    console.error('Error cargando productos:', error);
    if (loadingMsg) loadingMsg.hidden = true;
    if (emptyMsg) emptyMsg.hidden = false;
  }
}

// Renderizar productos usando el template
function renderProducts(products) {
  const container = document.getElementById('productsList');
  const template = document.getElementById('product-card-template');
  
  if (!container || !template) return;
  
  // Limpiar productos existentes (excepto mensajes)
  container.querySelectorAll('.product-card').forEach(el => el.remove());
  
  products.forEach(product => {
    const card = template.content.cloneNode(true);
    
    // Llenar datos
    card.querySelector('.sku').textContent = product.barcode;
    card.querySelector('.name').textContent = product.name;
    card.querySelector('.category').textContent = product.description || '';
    card.querySelector('.stock').textContent = product.stock;
    card.querySelector('.price').textContent = `$${product.price.toFixed(2)}`;
    
    // Badge de estado
    const badge = card.querySelector('.product-badge');
    if (product.stock === 0) {
      badge.textContent = 'Agotado';
      badge.style.background = 'rgba(239, 68, 68, 0.2)';
      badge.style.color = 'var(--danger)';
    } else if (product.stock <= product.min_stock) {
      badge.textContent = 'Bajo stock';
      badge.style.background = 'rgba(245, 158, 11, 0.2)';
      badge.style.color = 'var(--warning, #f59e0b)';
    } else {
      badge.textContent = 'Disponible';
      badge.style.background = 'rgba(16, 185, 129, 0.2)';
      badge.style.color = 'var(--success, #10b981)';
    }
    
    // Event listeners
    const viewBtn = card.querySelector('.btn-action.view');
    if (viewBtn) {
      viewBtn.onclick = () => viewProduct(product.id);
    }
    
    const editLink = card.querySelector('.btn-action.edit');
    if (editLink) {
      editLink.href = `/products/${product.id}/edit`;
    }
    
    const deleteBtn = card.querySelector('.btn-action.delete');
    if (deleteBtn) {
      deleteBtn.onclick = () => deleteProduct(product.id);
    }
    
    container.appendChild(card);
  });
}

// Funciones de acción
function openProductModal(product) {
  const modal = document.getElementById('product-modal');
  document.getElementById('pm-name').textContent = product.name;
  document.getElementById('pm-sku').textContent = product.barcode || '—';
  document.getElementById('pm-category').textContent = product.description || '—';
  document.getElementById('pm-stock').textContent = product.stock;
  document.getElementById('pm-price').textContent = `$${Number(product.price).toFixed(2)}`;
  const edit = document.getElementById('pm-edit');
  if (edit) edit.href = `/products/${product.id}/edit`;
  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('product-modal').classList.add('hidden');
  document.body.style.overflow = '';
}

document.getElementById('product-modal')?.addEventListener('click', (e) => {
  if (e.target.dataset.close === 'true') closeModal();
});
document.getElementById('pm-close')?.addEventListener('click', closeModal);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

async function viewProduct(id) {
  try {
    const response = await fetch(`/api/products/${id}`);
    if (!response.ok) throw new Error('No se pudo cargar el producto');
    const product = await response.json();
    openProductModal(product);
  } catch (error) {
    console.error('Error:', error);
    showToast('No se pudo cargar el producto', true);
  }
}

async function deleteProduct(id) {
  if (!confirm('¿Estás seguro de eliminar este producto?')) return;
  
  try {
    const response = await fetch(`/api/products/${id}`, { method: 'DELETE' });
    
    if (response.ok) {
      showToast('Producto eliminado exitosamente');
      loadProducts();
    } else {
      const error = await response.json();
      showToast(error.error || 'Error al eliminar', true);
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('Error al eliminar producto', true);
  }
}

function showToast(message, isError = false) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  
  toast.textContent = message;
  toast.style.background = isError ? 'var(--danger)' : 'var(--success, #10b981)';
  toast.classList.remove('hidden');
  
  setTimeout(() => toast.classList.add('hidden'), 3000);
}

// Event listeners para filtros
document.getElementById('search')?.addEventListener('input', debounce(applyFilters, 300));
document.getElementById('filter-category')?.addEventListener('change', applyFilters);
document.getElementById('view-mode')?.addEventListener('change', applyFilters);

function applyFilters() {
  const filters = {
    search: document.getElementById('search')?.value || '',
    category: document.getElementById('filter-category')?.value || '',
    view_mode: document.getElementById('view-mode')?.value || 'all'
  };
  
  loadProducts(filters);
}

// Utility: debounce
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}