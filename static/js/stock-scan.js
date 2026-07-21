/**
 * stock-scan.js — Reposición de stock por escáner.
 * Página dedicada (no modal): templates/stock_scan.html.
 *
 * Flujo: input siempre enfocado -> Enter (el scanner manda CR al final
 * del código) -> busca el producto -> lo agrega/incrementa en una lista
 * local -> el usuario puede ajustar cantidades a mano -> confirmar hace
 * UN solo POST a /api/products/stock_update_bulk con todo el lote.
 *
 * Backend usado (ya existente, sin cambios):
 *   GET  /api/products?search=<code>&limit=5   -> buscar por barcode
 *   POST /api/products/stock_update_bulk       -> aplicar stock + auditoría
 *        body: { products: [{ id, new_stock }, ...] }
 */
(function () {
  "use strict";

  const SEARCH_ENDPOINT = (code) =>
    `/api/products?search=${encodeURIComponent(code)}&limit=5&view_mode=all`;
  const BULK_UPDATE_ENDPOINT = "/api/products/stock_update_bulk";

  // Ignora un segundo Enter si llega antes de este tiempo desde el
  // anterior (algunos lectores mandan CR+LF, dos "Enter" seguidos por
  // el mismo escaneo).
  const SCAN_DEBOUNCE_MS = 150;

  const input = document.getElementById("scan-barcode-input");
  if (!input) return; // esta página no está cargada

  const errorBox = document.getElementById("scan-error");
  const tableBody = document.getElementById("scan-table-body");
  const emptyRow = document.getElementById("scan-table-empty");
  const summaryCount = document.getElementById("scan-summary-count");
  const summaryTotal = document.getElementById("scan-summary-total");
  const confirmBtn = document.getElementById("scan-confirm-btn");

  /** @type {Map<string, {id:number, barcode:string, name:string, currentStock:number, qty:number}>} */
  const items = new Map(); // key: barcode

  let lastScanAt = 0;
  let searching = false;

  // ---------- helpers ----------

  function focusInput() {
    setTimeout(() => input.focus({ preventScroll: true }), 0);
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  function updateSummary() {
    let distinct = 0;
    let totalUnits = 0;
    items.forEach((it) => {
      distinct += 1;
      totalUnits += it.qty;
    });
    summaryCount.textContent = String(distinct);
    summaryTotal.textContent = String(totalUnits);
    confirmBtn.disabled = distinct === 0;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function getQty(barcode) {
    const item = items.get(barcode);
    return item ? item.qty : 0;
  }

  function setQty(barcode, qty) {
    const item = items.get(barcode);
    if (!item) return;
    item.qty = Math.max(1, Math.floor(qty) || 1);
    renderRow(item);
    updateSummary();
  }

  function removeItem(barcode) {
    items.delete(barcode);
    const row = tableBody.querySelector(`tr[data-barcode="${CSS.escape(barcode)}"]`);
    if (row) row.remove();
    emptyRow.hidden = items.size > 0;
    updateSummary();
  }

  function renderRow(item) {
    let row = tableBody.querySelector(`tr[data-barcode="${CSS.escape(item.barcode)}"]`);
    if (!row) {
      row = document.createElement("tr");
      row.dataset.barcode = item.barcode;
      row.innerHTML = `
        <td class="scan-cell-code">${escapeHtml(item.barcode)}</td>
        <td class="scan-cell-name">${escapeHtml(item.name)}</td>
        <td class="scan-cell-stock">${item.currentStock}</td>
        <td>
          <div class="scan-qty-controls">
            <button type="button" class="btn-ghost scan-qty-btn" data-action="dec" aria-label="Bajar cantidad">−</button>
            <input type="number" min="1" step="1" class="scan-qty-input" value="${item.qty}" />
            <button type="button" class="btn-ghost scan-qty-btn" data-action="inc" aria-label="Subir cantidad">+</button>
          </div>
        </td>
        <td class="scan-cell-result">${item.currentStock + item.qty}</td>
        <td>
          <button type="button" class="close-btn scan-remove-btn" aria-label="Quitar de la lista">✕</button>
        </td>
      `;
      tableBody.appendChild(row);

      const qtyInput = row.querySelector(".scan-qty-input");
      qtyInput.addEventListener("change", () => {
        const parsed = parseInt(qtyInput.value, 10);
        setQty(item.barcode, Number.isFinite(parsed) ? parsed : 1);
      });

      row.querySelector('[data-action="inc"]').addEventListener("click", () => {
        setQty(item.barcode, getQty(item.barcode) + 1);
      });
      row.querySelector('[data-action="dec"]').addEventListener("click", () => {
        setQty(item.barcode, getQty(item.barcode) - 1);
      });
      row.querySelector(".scan-remove-btn").addEventListener("click", () => {
        removeItem(item.barcode);
      });
    } else {
      row.querySelector(".scan-qty-input").value = item.qty;
      row.querySelector(".scan-cell-result").textContent = item.currentStock + item.qty;
    }

    emptyRow.hidden = items.size > 0;
  }

  function flashRow(barcode) {
    const row = tableBody.querySelector(`tr[data-barcode="${CSS.escape(barcode)}"]`);
    if (!row) return;
    row.classList.remove("scan-row-flash");
    // Forzar reflow para poder re-disparar la animación en escaneos
    // consecutivos del mismo producto.
    void row.offsetWidth;
    row.classList.add("scan-row-flash");
  }

  function addOrIncrement(product) {
    const existing = items.get(product.barcode);
    if (existing) {
      existing.qty += 1;
      existing.currentStock = product.stock; // por si cambió mientras tanto
      renderRow(existing);
    } else {
      const item = {
        id: product.id,
        barcode: product.barcode,
        name: product.name,
        currentStock: product.stock,
        qty: 1,
      };
      items.set(product.barcode, item);
      renderRow(item);
    }
    flashRow(product.barcode);
    updateSummary();
  }

  function resetAll() {
    items.clear();
    tableBody.querySelectorAll("tr:not(#scan-table-empty)").forEach((r) => r.remove());
    emptyRow.hidden = false;
    updateSummary();
  }

  // ---------- búsqueda por barcode ----------

  async function lookupBarcode(code) {
    searching = true;
    try {
      const res = await fetch(SEARCH_ENDPOINT(code));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const results = Array.isArray(data.data) ? data.data : [];
      // "search" hace LIKE por nombre o barcode: nos quedamos solo con
      // el match exacto de código para no traer el producto equivocado.
      const exact = results.find((p) => p.barcode === code);

      if (!exact) {
        showError(`No se encontró ningún producto con el código "${code}".`);
        return;
      }

      clearError();
      addOrIncrement(exact);
    } catch (err) {
      console.warn("[stock-scan] error al buscar producto:", err);
      showError("No se pudo buscar el producto. Revisá tu conexión e intentá de nuevo.");
    } finally {
      searching = false;
    }
  }

  // ---------- confirmar ----------

  async function confirmRestock() {
    if (items.size === 0) return;

    confirmBtn.disabled = true;
    confirmBtn.textContent = "Guardando…";

    const products = Array.from(items.values()).map((it) => ({
      id: it.id,
      new_stock: it.currentStock + it.qty,
    }));

    try {
      const res = await fetch(BULK_UPDATE_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ products }),
      });
      const payload = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(payload.error || `HTTP ${res.status}`);
      }

      resetAll();

      NotificationManager.success("Stock actualizado correctamente.");

    } catch (err) {
      console.warn("[stock-scan] error al confirmar reposición:", err);
      showError("No se pudo guardar la reposición. Los productos siguen en la lista, podés reintentar.");
    } finally {
      confirmBtn.disabled = items.size === 0;
      confirmBtn.textContent = "Confirmar reposición";
      focusInput();
    }
  }

  // ---------- eventos ----------

  input.addEventListener("keydown", (evt) => {
    if (evt.key !== "Enter") return;
    evt.preventDefault();

    const now = Date.now();
    if (now - lastScanAt < SCAN_DEBOUNCE_MS) {
      input.value = "";
      return; // CR+LF duplicado del mismo escaneo
    }
    lastScanAt = now;

    const code = input.value.trim();
    input.value = "";
    if (!code || searching) {
      focusInput();
      return;
    }

    lookupBarcode(code).finally(focusInput);
  });

  confirmBtn.addEventListener("click", confirmRestock);

  updateSummary();
  focusInput();
})();