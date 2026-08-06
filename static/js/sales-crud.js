/**
 * Sales CRUD - Gestión de carrito y ventas POS
 * Maneja toda la lógica de carrito, búsqueda y procesamiento de ventas
 */

// ===== ESTADO GLOBAL =====
const cart = new Map();
let searchTimer;
let changeCalcOpen = false;
let selectedPaymentMethod = 'Efectivo';

// ===== ESTADO DE CUENTA CORRIENTE (fiado) =====
let selectedCustomerId = null;
let selectedCustomerName = null;
let selectedCustomerBalance = 0;
let selectedCustomerLimit = null; // null = sin limite configurado
let customerSearchTimer;
let pendingForceCredit = false; // se activa tras un rechazo por limite, para el reintento

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

async function searchCustomers(term) {
  if (!term) return [];
  const res = await fetch('/api/customers?q=' + encodeURIComponent(term));
  if (!res.ok) return [];
  const json = await res.json();
  return json.data || [];
}

async function fetchCustomerBalance(customerId) {
  const res = await fetch('/api/customers/' + customerId + '/balance');
  if (!res.ok) return null;
  return res.json();
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

function isCreditMethod(method) {
  return method === 'Fiado' || method === 'Mixto';
}

function currentUserIsAdmin() {
  const el = document.getElementById('userRole');
  if (!el) return false;
  return el.value === 'admin' || el.value === 'root';
}

// ===== PARSER DE TERMINOS =====
function parseTerm(raw) {
  const t = raw.trim();
  const m = t.match(/^(.*?)(?:[*xX\-]\s*(\d+))$/);
  if (m) return { code: m[1].trim(), qty: parseInt(m[2], 10) };
  return { code: t, qty: 1 };
}

// ===== SUGERENCIAS DE PRODUCTOS =====
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
      const contentSpanName = document.getElementById('lastAdded').textContent;
      const productName = contentSpanName.substring(0, contentSpanName.lastIndexOf(" x")).trim();

      if (productName === row.name.trim()){
        document.getElementById('lastAdded').style.display = 'none';
      }
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
  updateProjectedBalance();
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

// ===== BUSQUEDA DE PRODUCTOS =====
function focusSearch() {
  const s = document.getElementById('search');
  s.focus();
  s.select();
}

function clearSearch() {
  document.getElementById('search').value = '';
  hideSuggestions();
}

// ===== CUENTA CORRIENTE (FIADO) =====

function resetCreditState() {
  selectedCustomerId = null;
  selectedCustomerName = null;
  selectedCustomerBalance = 0;
  selectedCustomerLimit = null;
  pendingForceCredit = false;

  const customerInput = document.getElementById('customerInput');
  const customerIdInput = document.getElementById('customerIdInput');
  const amountPaidInput = document.getElementById('amountPaidInput');
  if (customerInput) customerInput.value = '';
  if (customerIdInput) customerIdInput.value = '';
  if (amountPaidInput) amountPaidInput.value = '';

  const balanceInfo = document.getElementById('customerBalanceInfo');
  const warning = document.getElementById('creditLimitWarning');
  if (balanceInfo) balanceInfo.style.display = 'none';
  if (warning) warning.style.display = 'none';
}

function updateCreditSectionVisibility() {
  const creditSection = document.getElementById('creditSection');
  const amountPaidWrapper = document.getElementById('amountPaidWrapper');
  if (!creditSection) return;

  const isCredit = isCreditMethod(selectedPaymentMethod);
  creditSection.style.display = isCredit ? 'block' : 'none';

  if (amountPaidWrapper) {
    amountPaidWrapper.style.display = selectedPaymentMethod === 'Mixto' ? 'block' : 'none';
  }

  if (!isCredit) {
    resetCreditState();
  }

  updateProjectedBalance();
}

function updateProjectedBalance() {
  if (!isCreditMethod(selectedPaymentMethod) || !selectedCustomerId) return;

  const total = getCartTotal();
  let amountPaidNow = 0;

  if (selectedPaymentMethod === 'Mixto') {
    const input = document.getElementById('amountPaidInput');
    amountPaidNow = parseFloat(input && input.value) || 0;
  }

  const pending = Math.max(0, total - amountPaidNow);
  const projected = selectedCustomerBalance + pending;

  const projectedEl = document.getElementById('customerProjectedBalance');
  if (projectedEl) projectedEl.textContent = '$' + projected.toFixed(2);

  const warning = document.getElementById('creditLimitWarning');
  const warningText = document.getElementById('creditLimitWarningText');
  const forceBtn = document.getElementById('forceCreditBtn');

  if (selectedCustomerLimit !== null && projected > selectedCustomerLimit) {
    warning.style.display = 'block';
    warningText.textContent = 'Esta venta supera el límite de crédito del cliente ($' + selectedCustomerLimit.toFixed(2) + ').';
    forceBtn.style.display = currentUserIsAdmin() ? 'inline-block' : 'none';
  } else {
    warning.style.display = 'none';
  }
}

async function selectCustomer(customer) {
  selectedCustomerId = customer.id;
  selectedCustomerName = customer.name;
  pendingForceCredit = false;

  document.getElementById('customerInput').value = customer.name;
  document.getElementById('customerIdInput').value = customer.id;
  hideCustomerSuggestions();

  const balanceData = await fetchCustomerBalance(customer.id);
  if (balanceData) {
    selectedCustomerBalance = balanceData.balance || 0;
    selectedCustomerLimit = (balanceData.credit_limit === null || balanceData.credit_limit === undefined)
      ? null
      : balanceData.credit_limit;
  } else {
    selectedCustomerBalance = 0;
    selectedCustomerLimit = null;
  }

  const balanceInfo = document.getElementById('customerBalanceInfo');
  const limitRow = document.getElementById('customerLimitRow');
  document.getElementById('customerCurrentBalance').textContent = '$' + selectedCustomerBalance.toFixed(2);

  if (selectedCustomerLimit !== null) {
    limitRow.style.display = 'flex';
    document.getElementById('customerCreditLimit').textContent = '$' + selectedCustomerLimit.toFixed(2);
  } else {
    limitRow.style.display = 'none';
  }

  balanceInfo.style.display = 'block';
  updateProjectedBalance();
}

function hideCustomerSuggestions() {
  const dropdown = document.getElementById('customerSuggestionsDropdown');
  if (dropdown) dropdown.style.display = 'none';
}

function renderCustomerSuggestions(customers) {
  const dropdown = document.getElementById('customerSuggestionsDropdown');
  const container = document.getElementById('customerSuggestionsContainer');
  if (!dropdown || !container) return;

  if (!customers.length) {
    container.innerHTML = '<div style="padding: 10px 12px; color: var(--text-muted); font-size: 0.85rem;">Sin resultados</div>';
    dropdown.style.display = 'block';
    return;
  }

  container.innerHTML = '';
  customers.forEach(function(c) {
    const div = document.createElement('div');
    div.className = 'customer-suggestion';
    div.textContent = c.name + (c.phone ? ' — ' + c.phone : '');
    div.addEventListener('click', function() {
      selectCustomer(c);
    });
    container.appendChild(div);
  });
  dropdown.style.display = 'block';
}

function validateCreditRequirements() {
  if (!isCreditMethod(selectedPaymentMethod)) return true;

  if (!selectedCustomerId) {
    Notify.error('Selecciona un cliente para la venta fiada');
    return false;
  }

  if (selectedPaymentMethod === 'Mixto') {
    const total = getCartTotal();
    const amountPaid = parseFloat(document.getElementById('amountPaidInput').value);
    if (isNaN(amountPaid) || amountPaid <= 0) {
      Notify.error('Ingresa el monto abonado');
      return false;
    }
    if (amountPaid >= total) {
      Notify.error('El monto abonado debe ser menor al total (usa Efectivo si paga todo)');
      return false;
    }
  }

  return true;
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
  updateCreditSectionVisibility();
}

// ===== ULTIMO TICKET =====
function showLastTicket(cartData, total, paymentMethod, pending) {
  const container = document.getElementById('lastTicketContent');
  const items = [];
  cartData.forEach(function(row) {
    items.push(row.name + ' x' + row.quantity);
  });

  let pendingBadge = '';
  if (pending && pending > 0) {
    pendingBadge = '<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;font-size:0.75rem;font-weight:600;background:color-mix(in srgb,var(--warning) 14%,transparent);color:var(--warning);white-space:nowrap;flex-shrink:0;">Pendiente $' + pending.toFixed(2) + '</span>';
  }

  container.innerHTML =
    '<div style="font-size:0.88rem;flex:1;min-width:0;">' +
      '<span style="color:var(--text-muted);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + items.join(' · ') + '</span>' +
    '</div>' +
    '<span style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;font-size:0.75rem;font-weight:600;background:color-mix(in srgb,var(--brand) 12%,transparent);color:var(--brand);white-space:nowrap;flex-shrink:0;">' + (paymentMethod || 'Efectivo') + '</span>' +
    pendingBadge +
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

  // Búsqueda de productos
  const searchEl = document.getElementById('search');
  if (searchEl) {

    // ── SCANNER: Anti-doble-disparo (CR+LF) ──────────────────────────────
    let lastEnterTime = 0;
    searchEl.addEventListener('keydown', function(e) {
      if (e.key !== 'Enter') return;
      const now = Date.now();
      if (now - lastEnterTime < 50) {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }
      lastEnterTime = now;
    }, true);

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

  // ── Búsqueda de cliente (fiado) ──────────────────────────────────────
  const customerInputEl = document.getElementById('customerInput');
  if (customerInputEl) {
    customerInputEl.addEventListener('input', function(e) {
      const val = e.target.value.trim();

      // Si el usuario edita el texto manualmente, invalida la seleccion previa
      if (val !== selectedCustomerName) {
        selectedCustomerId = null;
        document.getElementById('customerIdInput').value = '';
        document.getElementById('customerBalanceInfo').style.display = 'none';
      }

      clearTimeout(customerSearchTimer);
      if (!val) {
        hideCustomerSuggestions();
        return;
      }
      customerSearchTimer = setTimeout(async function() {
        renderCustomerSuggestions(await searchCustomers(val));
      }, 220);
    });

    document.addEventListener('click', function(e) {
      if (!e.target.closest('#customerInput') && !e.target.closest('#customerSuggestionsDropdown')) {
        hideCustomerSuggestions();
      }
    });
  }

  // Monto abonado (Mixto) recalcula saldo proyectado en vivo
  const amountPaidInputEl = document.getElementById('amountPaidInput');
  if (amountPaidInputEl) {
    amountPaidInputEl.addEventListener('input', updateProjectedBalance);
  }

  // Boton "Forzar" tras superar el limite de credito
  const forceCreditBtn = document.getElementById('forceCreditBtn');
  if (forceCreditBtn) {
    forceCreditBtn.addEventListener('click', function() {
      pendingForceCredit = true;
      Notify.warning('Se forzará el límite de crédito al procesar la venta');
      document.getElementById('creditLimitWarning').style.display = 'none';
    });
  }

  // ── SCANNER: Focus trap global ────────────────────────────────────────
  document.addEventListener('keydown', function(e) {
    const tag = document.activeElement && document.activeElement.tagName;
    const isEditable = (
      tag === 'INPUT' || tag === 'TEXTAREA' ||
      (document.activeElement && document.activeElement.isContentEditable)
    );
    const modalOpen = document.getElementById('confirmModal').style.display !== 'none';
    if (isEditable || modalOpen) return;

    if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
      searchEl.focus();
    }
  });

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
      updateCreditSectionVisibility();
    });
  }

  // Modal confirm button
  const modalConfirmBtn = document.getElementById('modalConfirm');
  if (modalConfirmBtn) {
    modalConfirmBtn.addEventListener('click', async function() {
      if (!validateCreditRequirements()) return;

      const modal = document.getElementById('confirmModal');
      const btn = this;
      btn.disabled = true;
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 1s linear infinite;display:inline-block;vertical-align:middle;margin-right:6px;"><circle cx="12" cy="12" r="10" opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>Procesando...';

      const payload = Array.from(cart.values()).map(function(r) {
        return { item_id: r.id, quantity: r.quantity };
      });

      const requestBody = {
        items: payload,
        payment_method: selectedPaymentMethod
      };

      if (isCreditMethod(selectedPaymentMethod)) {
        requestBody.customer_id = selectedCustomerId;
        if (selectedPaymentMethod === 'Mixto') {
          requestBody.amount_paid = parseFloat(document.getElementById('amountPaidInput').value);
        }
        if (pendingForceCredit) {
          requestBody.force_credit = true;
        }
      }

      const result = await submitSale(requestBody);

      if (result.response.ok) {
        const total = getCartTotal();
        let paidNow = total;
        if (selectedPaymentMethod === 'Fiado') paidNow = 0;
        if (selectedPaymentMethod === 'Mixto') paidNow = parseFloat(document.getElementById('amountPaidInput').value) || 0;
        const pending = Math.max(0, total - paidNow);

        showLastTicket(cart, total, selectedPaymentMethod, pending);

        selectedPaymentMethod = 'Efectivo';
        document.querySelectorAll('.payment-method-btn').forEach(function(b) {
          b.classList.toggle('active', b.dataset.method === 'Efectivo');
        });
        resetCreditState();
        updateCreditSectionVisibility();

        updateTodaySalesCount();
        document.getElementById('lastAdded').style.display = 'none';
        document.getElementById('cashReceived').value = '';
        focusSearch();
        clearCart();
        clearSearch();
        Notify.success('Venta registrada exitosamente');
      } else if (result.data.code === 'credit_limit_exceeded') {
        Notify.error(result.data.error || 'El cliente supera el límite de crédito');
        const warning = document.getElementById('creditLimitWarning');
        const warningText = document.getElementById('creditLimitWarningText');
        const forceBtn = document.getElementById('forceCreditBtn');
        if (warning && warningText) {
          warning.style.display = 'block';
          warningText.textContent = result.data.error || 'El cliente supera el límite de crédito';
          if (forceBtn) forceBtn.style.display = currentUserIsAdmin() ? 'inline-block' : 'none';
        }
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
    const modalOpen = document.getElementById('confirmModal').style.display !== 'none';

    // ── Alt+F: foco al buscador ──────────────────────────────────────────
    if (e.altKey && e.key === 'f') {
      e.preventDefault();
      focusSearch();
    }

    // ── Alt+V: abre modal de confirmación (si hay items) ────────────────
    if (e.altKey && e.key === 'v') {
      e.preventDefault();
      if (!modalOpen && cart.size) showConfirmModal();
    }

    // ── Alt+C: toggle calculadora de cambio ──────────────────────────────
    if (e.altKey && e.key === 'c') {
      e.preventDefault();
      document.getElementById('toggleChangeCalc').click();
      if (changeCalcOpen) {
        setTimeout(function() {
          document.getElementById('cashReceived').focus();
        }, 100);
      }
    }

    // ── Ctrl+Supr: vacia el carrito ────────────────────────────────────────
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

    // ── Escape: cierra modal / sugerencias ───────────────────────────────
    if (e.key === 'Escape') {
      if (modalOpen) {
        document.getElementById('confirmModal').style.display = 'none';
        focusSearch();
      } else {
        hideSuggestions();
      }
    }

    // ── Atajos exclusivos del modal de confirmación ──────────────────────
    if (modalOpen) {

      // Enter: procesa venta (salvo foco en Cancelar, cliente o monto)
      const activeId = document.activeElement && document.activeElement.id;
      const isTypingField = activeId === 'customerInput' || activeId === 'amountPaidInput';
      if (e.key === 'Enter' && document.activeElement !== document.getElementById('modalCancel') && !isTypingField) {
        e.preventDefault();
        const confirmBtn = document.getElementById('modalConfirm');
        if (confirmBtn && !confirmBtn.disabled) confirmBtn.click();
      }

      // Alt+E / Alt+T / Alt+R: Efectivo / Tarjeta / Transferencia
      // Alt+O / Alt+M: Fiado ("dObe") / Mixto
      if (e.altKey && (e.key === 'e' || e.key === 't' || e.key === 'r' || e.key === 'o' || e.key === 'm')) {
        e.preventDefault();
        const map = { e: 'Efectivo', t: 'Tarjeta', r: 'Transferencia', o: 'Fiado', m: 'Mixto' };
        const btn = document.querySelector('.payment-method-btn[data-method="' + map[e.key] + '"]');
        if (btn) btn.click();
      }

      // Tab / Shift+Tab: cicla los métodos de pago (solo si el foco no está en un campo de texto del modal)
      if (e.key === 'Tab' && !e.ctrlKey && !e.altKey && !isTypingField) {
        const methods = Array.from(document.querySelectorAll('.payment-method-btn'));
        const activeIdx = methods.findIndex(function(b) { return b.classList.contains('active'); });
        if (activeIdx !== -1) {
          e.preventDefault();
          const next = e.shiftKey
            ? (activeIdx - 1 + methods.length) % methods.length
            : (activeIdx + 1) % methods.length;
          methods[next].click();
        }
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