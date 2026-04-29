/**
 * Sales CRUD - Gestión de carrito y ventas POS
 * Maneja toda la lógica de carrito, búsqueda y procesamiento de ventas
 */

// ===== ESTADO GLOBAL =====
const cart = new Map();
let searchTimer;
let changeCalcOpen = false;
let selectedPaymentMethod = 'Efectivo';

// ===== RELOJ =====
function updateClock() {
  document.getElementById('currentTime').textContent = new Date().toLocaleTimeString('es-ES', {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  });
}

// ===== API CALLS =====
async function searchItems(term) {
  if (!term) return [];
  const res = await fetch('/api/items?q=' + encodeURIComponent(term));
  return res.ok ? res.json() : [];
}

async function submitSale(payload) {
  const res = await fetch('/api/sales/bulk', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return { response: res, data: await res.json() };
}

async function fetchTodaysSalesCount() {
  const today = new Date().toISOString().split('T')[0];
  const res = await fetch('/api/sales?from=' + today + '&to=' + today);
  if (!res.ok) return 0;
  const json = await res.json();
  const data = Array.isArray(json) ? json : (json.data || []);
  return data.length;
}

// ===== PARSER DE TERMINOS =====
function parseTerm(raw) {
  const t = raw.trim();
  const m = t.match(/^(.*?)(?:[*xX\-]\s*(\d+))$/);
  if (m) return { code: m[1].trim(), qty: parseInt(m[2], 10) };
  return { code: t, qty: 1 };
}

// ===== SUGERENCIAS =====
function renderSuggestions(items) {
  const box = document.getElementById('suggestions');
  box.innerHTML = '';
  if (!items.length) {
    box.classList.add('hidden');
    return;
  }
  box.classList.remove('hidden');
  items.slice(0, 8).forEach(function(it) {
    const div = document.createElement('div');
    div.className = 'suggestion-item';
    const stockColor = it.stock > 0 ? 'var(--success)' : 'var(--danger)';
    const stockBg = it.stock > 0 ? 'color-mix(in srgb, var(--success) 12%, transparent)' : 'color-mix(in srgb, var(--danger) 12%, transparent)';
    const stockText = it.stock > 0 ? it.stock + ' disp.' : 'Agotado';
    div.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">' +
        '<div style="min-width:0;">' +
          '<div style="font-weight:600;font-size:0.9rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + it.name + '</div>' +
          '<div style="font-size:0.78rem;color:var(--text-muted);">' + (it.barrs_code || '') + '</div>' +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">' +
          '<span style="background:' + stockBg + ';color:' + stockColor + ';padding:2px 8px;border-radius:999px;font-size:0.72rem;font-weight:600;">' + stockText + '</span>' +
          '<span style="font-weight:700;font-size:0.95rem;">$' + it.price.toFixed(2) + '</span>' +
        '</div>' +
      '</div>';
    if (it.stock > 0) {
      div.addEventListener('click', function() {
        addToCart(it, 1);
        hideSuggestions();
        focusSearch();
      });
    } 
    box.appendChild(div);
  });
}

function hideSuggestions() {
  document.getElementById('suggestions').classList.add('hidden');
}

function cleanSearchInput() {
  const s = document.getElementById('search');
  s.value = '';
  hideSuggestions();
}

// ===== CARRITO =====
function addToCart(item, qty) {
  qty = qty || 1;
  const existing = cart.get(item.id);
  let newQty = existing ? existing.quantity + qty : qty;
  const maxStock = item.stock || 999;

  if (newQty > maxStock) {
    Notify.warning('Stock insuficiente. Disponible: ' + maxStock);
    newQty = maxStock;
  }

  cart.set(item.id, {
    id: item.id,
    name: item.name,
    unit_price: item.price,
    quantity: newQty,
    max_stock: maxStock
  });

  cleanSearchInput();
  showLastAdded(item.name, newQty, item.price);
  renderCart();
}

function showLastAdded(name, qty, price) {
  const bar = document.getElementById('lastAdded');
  const text = document.getElementById('lastAddedText');
  text.textContent = name + ' x' + qty + ' — $' + (qty * price).toFixed(2);
  bar.style.display = 'flex';
  bar.style.animation = 'none';
  bar.offsetHeight;
  bar.style.animation = 'fadeSlideIn .25s ease';
}

function clearCart() {
  cart.clear();
  document.getElementById('lastAdded').style.display = 'none';
  document.getElementById('cashReceived').value = '';
  renderCart();
  focusSearch();
}

function renderCart() {
  const container = document.getElementById('cartItems');
  container.innerHTML = '';
  let total = 0, itemCount = 0, typeCount = 0;

  if (!cart.size) {
    document.getElementById('emptyCart').style.display = 'block';
    document.getElementById('confirmSale').disabled = true;
    document.getElementById('cartSummaryLine').style.display = 'none';
    document.getElementById('changeCalcWrapper').style.display = 'none';
  } else {
    document.getElementById('emptyCart').style.display = 'none';
    document.getElementById('confirmSale').disabled = false;
    document.getElementById('cartSummaryLine').style.display = 'flex';
    document.getElementById('changeCalcWrapper').style.display = 'block';
  }

  cart.forEach(function(row) {
    const lineTotal = row.quantity * row.unit_price;
    total += lineTotal;
    itemCount += row.quantity;
    typeCount++;

    const div = document.createElement('div');
    div.className = 'cart-item';
    div.dataset.itemId = row.id;
    div.dataset.quantity = row.quantity;
    div.innerHTML =
      '<div class="cart-item-info">' +
        '<div class="cart-item-name" title="' + row.name + '">' + row.name + '</div>' +
        '<div class="cart-item-price">$' + row.unit_price.toFixed(2) + ' c/u</div>' +
      '</div>' +
      '<div class="qty-controls">' +
        '<button type="button" class="qty-btn qty-dec" data-id="' + row.id + '">-</button>' +
        '<input type="number" class="qty-value" value="' + row.quantity + '" min="1" max="' + row.max_stock + '" data-id="' + row.id + '">' +
        '<button type="button" class="qty-btn qty-inc" data-id="' + row.id + '">+</button>' +
      '</div>' +
      '<div class="cart-item-subtotal">$' + lineTotal.toFixed(2) + '</div>' +
      '<button type="button" class="cart-remove-btn" data-id="' + row.id + '" title="Quitar">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
      '</button>';

    div.querySelector('.qty-dec').addEventListener('click', function() {
      if (row.quantity > 1) {
        row.quantity--;
        renderCart();
      }
    });
    div.querySelector('.qty-inc').addEventListener('click', function() {
      if (row.quantity < row.max_stock) {
        row.quantity++;
        renderCart();
      } else {
        Notify.warning('Stock maximo alcanzado: ' + row.max_stock);
      }
    });
    div.querySelector('.qty-value').addEventListener('change', function(e) {
      const v = parseInt(e.target.value, 10);
      if (v > 0 && v <= row.max_stock) {
        row.quantity = v;
        renderCart();
      } else if (v > row.max_stock) {
        row.quantity = row.max_stock;
        renderCart();
        Notify.warning('Stock maximo: ' + row.max_stock);
      }
    });
    div.querySelector('.cart-remove-btn').addEventListener('click', function() {
      cart.delete(row.id);
      renderCart();
      focusSearch();
    });

    container.appendChild(div);
  });

  document.getElementById('cartCount').textContent = itemCount;
  document.getElementById('cartItemTypes').textContent = typeCount;
  document.getElementById('cartTotalUnits').textContent = itemCount;
  document.getElementById('cartGrandDisplay').textContent = '$' + total.toFixed(2);

  updateChangeCalc();
  generateQuickCashButtons(total);
}

// ===== CALCULADORA DE CAMBIO =====
function updateChangeCalc() {
  const cash = parseFloat(document.getElementById('cashReceived').value);
  const total = getCartTotal();
  const resultDiv = document.getElementById('changeResult');

  if (isNaN(cash) || cash === 0 || total === 0) {
    resultDiv.style.display = 'none';
    return;
  }

  resultDiv.style.display = 'flex';
  const change = cash - total;

  if (change >= 0) {
    resultDiv.className = 'change-result positive';
    document.getElementById('changeLabel').textContent = 'Cambio';
    document.getElementById('changeAmount').textContent = '$' + change.toFixed(2);
  } else {
    resultDiv.className = 'change-result negative';
    document.getElementById('changeLabel').textContent = 'Falta';
    document.getElementById('changeAmount').textContent = '$' + Math.abs(change).toFixed(2);
  }
}

function generateQuickCashButtons(total) {
  const container = document.getElementById('quickCashButtons');
  container.innerHTML = '';
  if (total <= 0) return;

  let amounts = [];
  const rounded = Math.ceil(total);
  amounts.push(rounded);
  [10, 50, 100, 200, 500].forEach(function(d) {
    const n = Math.ceil(total / d) * d;
    if (n > (amounts[amounts.length - 1] || 0) && amounts.length < 6) amounts.push(n);
  });
  amounts = amounts.filter(function(v, i, a) {
    return a.indexOf(v) === i;
  }).slice(0, 6);

  amounts.forEach(function(amt) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'quick-cash-btn';
    btn.textContent = '$' + amt;
    btn.addEventListener('click', function() {
      document.getElementById('cashReceived').value = amt;
      updateChangeCalc();
    });
    container.appendChild(btn);
  });

  const exactBtn = document.createElement('button');
  exactBtn.type = 'button';
  exactBtn.className = 'quick-cash-btn';
  exactBtn.style.cssText = 'border-color:color-mix(in srgb,var(--success) 40%,transparent);color:var(--success);';
  exactBtn.textContent = 'Exacto';
  exactBtn.addEventListener('click', function() {
    document.getElementById('cashReceived').value = total.toFixed(2);
    updateChangeCalc();
  });
  container.appendChild(exactBtn);
}

function getCartTotal() {
  let total = 0;
  cart.forEach(function(row) {
    total += row.quantity * row.unit_price;
  });
  return total;
}

// ===== BUSQUEDA =====
function focusSearch() {
  const s = document.getElementById('search');
  s.focus();
  s.select();
}

function clearSearch() {
  document.getElementById('search').value = '';
  hideSuggestions();
}

// ===== CONFIRMAR VENTA =====
function showConfirmModal() {
  const summary = document.getElementById('modalCartSummary');
  let total = 0;
  summary.innerHTML = '';
  cart.forEach(function(row) {
    const lineTotal = row.quantity * row.unit_price;
    total += lineTotal;
    const div = document.createElement('div');
    div.className = 'modal-summary-item';
    div.innerHTML =
      '<div style="min-width:0;"><span style="font-weight:600;">' + row.name + '</span><span style="color:var(--text-muted);margin-left:6px;">x' + row.quantity + '</span></div>' +
      '<span style="font-weight:600;flex-shrink:0;">$' + lineTotal.toFixed(2) + '</span>';
    summary.appendChild(div);
  });
  document.getElementById('modalTotal').textContent = '$' + total.toFixed(2);
  document.getElementById('confirmModal').style.display = 'flex';
}

// ===== ULTIMO TICKET =====
function showLastTicket(cartData, total, paymentMethod) {
  const container = document.getElementById('lastTicketContent');
  const items = [];
  cartData.forEach(function(row) {
    items.push(row.name + ' x' + row.quantity);
  });

  container.innerHTML =
    '<div style="font-size:0.88rem;flex:1;min-width:0;">' +
      '<span style="color:var(--text-muted);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + items.join(' · ') + '</span>' +
    '</div>' +
    '<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;font-size:0.75rem;font-weight:600;background:color-mix(in srgb,var(--brand) 12%,transparent);color:var(--brand);white-space:nowrap;flex-shrink:0;">' + (paymentMethod || 'Efectivo') + '</span>' +
    '<div style="font-weight:700;font-size:1.1rem;color:var(--success);flex-shrink:0;">$' + total.toFixed(2) + '</div>';

  document.getElementById('lastTicket').style.display = 'block';
}

// ===== INICIALIZACION =====
function initSalesForm() {
  // Reloj
  setInterval(updateClock, 1000);
  updateClock();

  // Contador de ventas hoy
  updateTodaySalesCount();

  // Búsqueda
  const searchEl = document.getElementById('search');
  if (searchEl) {
    searchEl.addEventListener('keydown', async function(e) {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      const raw = e.target.value;
      if (!raw.trim()) return;
      const parsed = parseTerm(raw);
      const results = await searchItems(parsed.code);
      if (!results.length) {
        e.target.value = '';
        hideSuggestions();
        return;
      }
      const exact = results.find(function(r) {
        return r.barrs_code === parsed.code;
      });
      if (exact) {
        addToCart(exact, parsed.qty);
        e.target.value = '';
        hideSuggestions();
        return;
      }
      if (results.length === 1) {
        addToCart(results[0], parsed.qty);
        e.target.value = '';
        hideSuggestions();
        return;
      }
      const sugBox = document.getElementById('suggestions');
      if (!sugBox.classList.contains('hidden')) {
        addToCart(results[0], parsed.qty);
        e.target.value = '';
        hideSuggestions();
      } else {
        renderSuggestions(results);
      }
    });

    searchEl.addEventListener('input', function(e) {
      clearTimeout(searchTimer);
      const val = e.target.value.trim();
      if (!val) {
        hideSuggestions();
        return;
      }
      searchTimer = setTimeout(async function() {
        renderSuggestions(await searchItems(parseTerm(val).code));
      }, 180);
    });
  }

  // Vaciar carrito
  const clearCartBtn = document.getElementById('clearCart');
  if (clearCartBtn) {
    clearCartBtn.addEventListener('click', function() {
      if (cart.size && confirm('Vaciar todo el carrito?')) {
        cart.clear();
        document.getElementById('lastAdded').style.display = 'none';
        document.getElementById('cashReceived').value = '';
        renderCart();
        focusSearch();
      }
    });
  }

  // Confirmar venta
  const confirmBtn = document.getElementById('confirmSale');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', function() {
      if (!cart.size) return;
      showConfirmModal();
    });
  }

  // Cancelar modal
  const modalCancelBtn = document.getElementById('modalCancel');
  if (modalCancelBtn) {
    modalCancelBtn.addEventListener('click', function() {
      document.getElementById('confirmModal').style.display = 'none';
      focusSearch();
    });
  }

  // Click en overlay cierra modal
  const confirmModal = document.getElementById('confirmModal');
  if (confirmModal) {
    confirmModal.addEventListener('click', function(e) {
      if (e.target === this) {
        this.style.display = 'none';
        focusSearch();
      }
    });
  }

  // Cash received input
  const cashInput = document.getElementById('cashReceived');
  if (cashInput) {
    cashInput.addEventListener('input', updateChangeCalc);
  }

  // Toggle calculadora
  const toggleBtn = document.getElementById('toggleChangeCalc');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function() {
      changeCalcOpen = !changeCalcOpen;
      document.getElementById('changeCalcBody').style.display = changeCalcOpen ? 'block' : 'none';
      document.getElementById('changeCalcArrow').style.transform = changeCalcOpen ? 'rotate(180deg)' : 'rotate(0)';
    });
  }

  // Payment method selection
  const paymentGroup = document.getElementById('paymentMethodGroup');
  if (paymentGroup) {
    paymentGroup.addEventListener('click', function(e) {
      const btn = e.target.closest('.payment-method-btn');
      if (!btn) return;
      selectedPaymentMethod = btn.dataset.method;
      document.querySelectorAll('.payment-method-btn').forEach(function(b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
    });
  }

  // Modal confirm button
  const modalConfirmBtn = document.getElementById('modalConfirm');
  if (modalConfirmBtn) {
    modalConfirmBtn.addEventListener('click', async function() {
      const modal = document.getElementById('confirmModal');
      const btn = this;
      btn.disabled = true;
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 1s linear infinite;display:inline-block;vertical-align:middle;margin-right:6px;"><circle cx="12" cy="12" r="10" opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>Procesando...';

      const payload = Array.from(cart.values()).map(function(r) {
        return { item_id: r.id, quantity: r.quantity };
      });

      const result = await submitSale({
        items: payload,
        payment_method: selectedPaymentMethod
      });

      if (result.response.ok) {
        showLastTicket(cart, getCartTotal(), selectedPaymentMethod);
        selectedPaymentMethod = 'Efectivo';
        document.querySelectorAll('.payment-method-btn').forEach(function(b) {
          b.classList.toggle('active', b.dataset.method === 'Efectivo');
        });
        updateTodaySalesCount();
        document.getElementById('lastAdded').style.display = 'none';
        document.getElementById('cashReceived').value = '';
        focusSearch();
        clearCart();
        clearSearch();
        Notify.success('Venta registrada exitosamente');
      } else {
        Notify.error(result.data.error || 'Error al registrar venta');
      }

      modal.style.display = 'none';
      btn.disabled = false;
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:6px;"><polyline points="20 6 9 17 4 12"/></svg>Procesar Venta';
    });
  }

  // Cerrar último ticket
  const closeLastTicketBtn = document.getElementById('closeLastTicket');
  if (closeLastTicketBtn) {
    closeLastTicketBtn.addEventListener('click', function() {
      document.getElementById('lastTicket').style.display = 'none';
    });
  }

  // Cerrar sugerencias al hacer click afuera
  document.addEventListener('click', function(e) {
    if (!e.target.closest('#search') && !e.target.closest('#suggestions')) {
      hideSuggestions();
    }
  });

  // Atajos de teclado
  document.addEventListener('keydown', function(e) {
    if (e.key === 'F2') {
      e.preventDefault();
      focusSearch();
    }
    if (e.ctrlKey && e.key === 'Delete') {
      e.preventDefault();
      if (cart.size && confirm('Vaciar todo el carrito?')) {
        cart.clear();
        document.getElementById('lastAdded').style.display = 'none';
        document.getElementById('cashReceived').value = '';
        renderCart();
        focusSearch();
      }
    }
    if (e.key === 'Escape') {
      document.getElementById('confirmModal').style.display = 'none';
      hideSuggestions();
    }
    if (e.key === 'F4') {
      e.preventDefault();
      document.getElementById('toggleChangeCalc').click();
      if (changeCalcOpen) {
        setTimeout(function() {
          document.getElementById('cashReceived').focus();
        }, 100);
      }
    }
  });

  // Inicial render
  focusSearch();
  renderCart();
}

// ===== ACTUALIZAR CONTADOR VENTAS HOY =====
async function updateTodaySalesCount() {
  const count = await fetchTodaysSalesCount();
  document.getElementById('todaySalesCount').textContent = count + ' venta' + (count !== 1 ? 's' : '') + ' hoy';
}

// ===== INICIAR AL CARGAR EL DOM =====
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSalesForm);
} else {
  initSalesForm();
}