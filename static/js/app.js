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
  
  const params = new URLSearchParams();
  if (filters.search)    params.append('search',    filters.search);
  if (filters.view_mode) params.append('view_mode', filters.view_mode);
  params.append('limit', filters.limit || 96);
  params.append('page',  filters.page  || 1);
  
  try {
    const response = await fetch(`/api/products?${params}`);
    // La API ahora devuelve { data, total, page, pages, limit }
    const json = await response.json();
    const products = json.data ?? json; // fallback por si algún endpoint aún devuelve array
    
    if (loadingMsg) loadingMsg.hidden = true;
    
    if (!Array.isArray(products) || products.length === 0) {
      if (emptyMsg) emptyMsg.hidden = false;
      return;
    }
    
    renderProducts(products);
    
    const countDisplay = document.getElementById('products-count-display');
    if (countDisplay) countDisplay.textContent = json.total ?? products.length;
    
  } catch (error) {
    console.error('Error cargando productos:', error);
    Notify.error('Error al cargar los productos.');
    if (loadingMsg) loadingMsg.hidden = true;
    if (emptyMsg) emptyMsg.hidden = false;
  }
}

function renderProducts(products) {
  const container = document.getElementById('productsList');
  const template = document.getElementById('product-card-template');
  
  if (!container || !template) return;
  
  container.querySelectorAll('.product-card').forEach(el => el.remove());
  
  products.forEach(product => {
    const card = template.content.cloneNode(true);
    const article = card.querySelector('article');
    
    card.querySelector('.sku').textContent = product.barcode || 'N/A';
    card.querySelector('.name').textContent = product.name;
    card.querySelector('.category').textContent = product.description || '';
    card.querySelector('.stock').textContent = product.stock;
    card.querySelector('.price').textContent = `$${(product.price || 0).toFixed(2)}`;
    card.querySelector('.expiration-date').textContent = product.expiration_date || '—';
    
    const badge = card.querySelector('.product-badge');
    const stock = product.stock || 0;
    const min = product.min_stock || 0;
    
    if (product.status === 0) {
      badge.textContent = 'Inactivo';
      badge.style.background = 'rgba(239,68,68,0.15)';
      badge.style.color = 'var(--danger, #ef4444)';
    } else if (stock === 0) {
      badge.textContent = 'Agotado';
      badge.style.background = 'rgba(239,68,68,0.15)';
      badge.style.color = 'var(--danger, #ef4444)';
    } else if (stock <= min) {
      badge.textContent = 'Stock bajo';
      badge.style.background = 'rgba(245,158,11,0.15)';
      badge.style.color = 'var(--warning, #f59e0b)';
    } else {
      badge.textContent = 'En stock';
      badge.style.background = 'rgba(16,185,129,0.15)';
      badge.style.color = 'var(--success, #10b981)';
    }
    
    // ✅ ADD EVENT LISTENER AL CLICK
    article.addEventListener('click', function() {
      window.location.href = '/products/' + product.id;
    });
    
    container.appendChild(card);
  });
}

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
    Notify.error('No se pudo cargar el producto');
  }
}

async function deleteProduct(id) {
  if (!confirm('¿Estás seguro de eliminar este producto?')) return;
  
  try {
    const response = await fetch(`/api/products/${id}`, { method: 'DELETE' });
    
    if (response.ok) {
      Notify.success('Producto eliminado exitosamente');
      loadProducts();
    } else {
      const error = await response.json();
      Notify.error(error.error || 'Error al eliminar');
    }
  } catch (error) {
    console.error('Error:', error);
    Notify.error('Error al eliminar producto');
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
    search:    document.getElementById('search')?.value    || '',
    view_mode: document.getElementById('view-mode')?.value || 'all',
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