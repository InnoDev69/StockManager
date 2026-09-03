/**
 * product-export.js — Página de exportación de productos.
 * templates/product_export.html
 *
 * Flujo: el usuario arma filtros -> se consulta GET /api/products con
 * esos filtros (limit=1) solo para leer "total" y mostrar una vista
 * previa de cuántos productos van a exportarse -> al confirmar, se
 * hace POST /api/products/export (guarda los filtros en sesión) y
 * después se navega a GET /api/products/export, que devuelve el CSV
 * como attachment y dispara la descarga nativa del navegador/webview.
 */
(function () {
  "use strict";

  const SEARCH_ENDPOINT = "/api/products";
  const EXPORT_ENDPOINT = "/api/products/export";
  const PREVIEW_DEBOUNCE_MS = 350;

  const searchInput = document.getElementById("export-search");
  if (!searchInput) return; // esta página no está cargada

  const viewModeSelect = document.getElementById("export-view-mode");
  const sortSelect = document.getElementById("export-sort");
  const orderSelect = document.getElementById("export-order");

  const previewCount = document.getElementById("export-preview-count");
  const previewLabel = document.getElementById("export-preview-label");
  const previewTableBody = document.getElementById("export-preview-table-body");
  const previewTableEmpty = document.getElementById("export-preview-table-empty");
  const previewMore = document.getElementById("export-preview-more");

  const PREVIEW_ROWS = 8;

  const errorBox = document.getElementById("export-error");
  const successBox = document.getElementById("export-success");

  const confirmBtn = document.getElementById("export-confirm-btn");
  const resetBtn = document.getElementById("export-reset-btn");

  let previewTimer = null;
  let previewRequestId = 0;

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function formatPrice(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "—";
    return num.toLocaleString("es-AR", { style: "currency", currency: "ARS" });
  }

  function renderPreviewRows(products, total) {
    previewTableBody.querySelectorAll("tr:not(#export-preview-table-empty)").forEach((r) => r.remove());

    if (!products.length) {
      previewTableEmpty.hidden = false;
      previewMore.hidden = true;
      return;
    }

    previewTableEmpty.hidden = true;

    products.forEach((product) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="export-cell-code">${escapeHtml(product.barcode || "—")}</td>
        <td class="export-cell-name">${escapeHtml(product.name || "—")}</td>
        <td class="export-cell-stock">${product.stock ?? "—"}</td>
        <td class="export-cell-price">${formatPrice(product.price)}</td>
      `;
      previewTableBody.appendChild(row);
    });

    const remaining = total - products.length;
    if (remaining > 0) {
      previewMore.textContent = `…y ${remaining} producto${remaining === 1 ? "" : "s"} más en el CSV.`;
      previewMore.hidden = false;
    } else {
      previewMore.hidden = true;
    }
  }

  function currentFilters() {
    return {
      search: searchInput.value.trim(),
      view_mode: viewModeSelect.value,
      sort: sortSelect.value,
      order: orderSelect.value,
    };
  }

  function hideMessages() {
    errorBox.hidden = true;
    successBox.hidden = true;
  }

  function showError(message) {
    successBox.hidden = true;
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function showSuccess(message) {
    errorBox.hidden = true;
    successBox.textContent = message;
    successBox.hidden = false;
  }

  function buildQuery(filters, extra) {
    const params = new URLSearchParams({ ...filters, ...extra });
    // No mandamos "search" vacío para no ensuciar la query.
    if (!filters.search) params.delete("search");
    return params.toString();
  }

  async function refreshPreview() {
    const filters = currentFilters();
    const requestId = ++previewRequestId;

    previewCount.textContent = "…";
    previewLabel.textContent = "Calculando productos que coinciden con los filtros…";

    try {
      const query = buildQuery(filters, { limit: String(PREVIEW_ROWS), page: "1" });
      const res = await fetch(`${SEARCH_ENDPOINT}?${query}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // Si mientras esperábamos la respuesta el usuario cambió otro
      // filtro y disparó una consulta más nueva, esta ya es vieja.
      if (requestId !== previewRequestId) return;

      const total = typeof data.total === "number" ? data.total : 0;
      const products = Array.isArray(data.data) ? data.data : [];

      previewCount.textContent = String(total);
      previewLabel.textContent =
        total === 1
          ? "producto coincide con los filtros elegidos"
          : "productos coinciden con los filtros elegidos";
      confirmBtn.disabled = total === 0;

      renderPreviewRows(products, total);
    } catch (err) {
      if (requestId !== previewRequestId) return;
      console.warn("[product-export] no se pudo calcular la vista previa:", err);
      previewCount.textContent = "—";
      previewLabel.textContent = "No se pudo calcular cuántos productos coinciden. Igual podés intentar exportar.";
      renderPreviewRows([], 0);
    }
  }

  function scheduleRefreshPreview() {
    hideMessages();
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(refreshPreview, PREVIEW_DEBOUNCE_MS);
  }

  async function handleExport() {
    confirmBtn.disabled = true;
    const originalHtml = confirmBtn.innerHTML;
    confirmBtn.textContent = "Preparando descarga…";
    hideMessages();

    try {
      const res = await fetch(EXPORT_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentFilters()),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.error || `HTTP ${res.status}`);
      }

      // Dispara el diálogo nativo de "guardar como" del navegador/webview.
      window.location.href = EXPORT_ENDPOINT;

      showSuccess("Descarga iniciada. Revisá el diálogo de tu navegador para elegir dónde guardar el archivo.");
    } catch (err) {
      console.warn("[product-export] error al exportar:", err);
      showError("No se pudo generar la exportación. Intentá de nuevo en unos segundos.");
    } finally {
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = originalHtml;
    }
  }

  function resetFilters() {
    searchInput.value = "";
    viewModeSelect.value = "all";
    sortSelect.value = "name";
    orderSelect.value = "asc";
    hideMessages();
    refreshPreview();
    searchInput.focus();
  }

  [searchInput].forEach((el) => el.addEventListener("input", scheduleRefreshPreview));
  [viewModeSelect, sortSelect, orderSelect].forEach((el) =>
    el.addEventListener("change", scheduleRefreshPreview)
  );

  confirmBtn.addEventListener("click", handleExport);
  resetBtn.addEventListener("click", resetFilters);

  refreshPreview();
})();