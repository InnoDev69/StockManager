/**
 * product-export.js — Página de exportación de productos.
 * templates/product_export.html
 *
 * Flujo: el usuario arma filtros + elige columnas -> se consulta
 * GET /api/products (limit=8) para mostrar total y una muestra real
 * de los productos, ya recortada a las columnas elegidas -> al
 * confirmar, POST /api/products/export guarda filtros + columnas
 * excluidas en sesión, y GET /api/products/export descarga el CSV
 * respetando ambas cosas.
 *
 * OJO: los nombres de campo NO son iguales entre la API de búsqueda
 * (stock, min_stock) y el CSV real (quantity, min_quantity) — es la
 * misma columna con otro nombre en cada lado. FIELDS de acá abajo
 * mapea ambos. Si algún día se unifican los nombres en el backend,
 * este mapeo se puede simplificar a un solo campo por fila.
 */
(function () {
  "use strict";

  const SEARCH_ENDPOINT = "/api/products";
  const EXPORT_ENDPOINT = "/api/products/export";
  const PREVIEW_DEBOUNCE_MS = 350;
  const PREVIEW_ROWS = 8;

  // key: como viene en GET /api/products (data[i][key])
  // csvKey: como se llama esa misma columna en el CSV real
  // default: si arranca tildada o no
  const FIELDS = [
    { key: "barcode", csvKey: "barcode", label: "Código de barras", default: true },
    { key: "name", csvKey: "name", label: "Nombre", default: true },
    { key: "stock", csvKey: "quantity", label: "Stock", default: true },
    { key: "price", csvKey: "price", label: "Precio", default: true },
    { key: "min_stock", csvKey: "min_quantity", label: "Stock mínimo", default: false },
    { key: "description", csvKey: "description", label: "Descripción", default: false },
    { key: "expiration_date", csvKey: "expiration_date", label: "Vencimiento", default: false },
    { key: "status", csvKey: "status", label: "Estado", default: false },
    { key: "id", csvKey: "id", label: "ID interno", default: false },
    { key: "created_at", csvKey: "created_at", label: "Creado", default: false },
    { key: "updated_at", csvKey: "updated_at", label: "Actualizado", default: false },
  ];

  const searchInput = document.getElementById("export-search");
  if (!searchInput) return; // esta página no está cargada

  const viewModeSelect = document.getElementById("export-view-mode");
  const sortSelect = document.getElementById("export-sort");
  const orderSelect = document.getElementById("export-order");

  const columnsList = document.getElementById("export-columns-list");
  const columnsError = document.getElementById("export-columns-error");

  const previewCount = document.getElementById("export-preview-count");
  const previewLabel = document.getElementById("export-preview-label");
  const previewTableHead = document.getElementById("export-preview-table-head");
  const previewTableBody = document.getElementById("export-preview-table-body");
  const previewTableEmpty = document.getElementById("export-preview-table-empty");
  const previewMore = document.getElementById("export-preview-more");

  const errorBox = document.getElementById("export-error");
  const successBox = document.getElementById("export-success");

  const confirmBtn = document.getElementById("export-confirm-btn");
  const resetBtn = document.getElementById("export-reset-btn");

  let previewTimer = null;
  let previewRequestId = 0;

  // ---------- columnas ----------

  function buildColumnCheckboxes() {
    FIELDS.forEach((field) => {
      const label = document.createElement("label");
      label.className = "export-column-item";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = field.default;
      checkbox.dataset.fieldKey = field.key;

      checkbox.addEventListener("change", () => {
        columnsError.hidden = getSelectedFields().length > 0;
        renderPreviewTableHead();
        scheduleRefreshPreview();
      });

      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(field.label));
      columnsList.appendChild(label);
    });
  }

  function getSelectedFields() {
    const checked = new Set(
      Array.from(columnsList.querySelectorAll("input[type=checkbox]:checked")).map(
        (el) => el.dataset.fieldKey
      )
    );
    return FIELDS.filter((f) => checked.has(f.key));
  }

  function getExcludedCsvFields() {
    const selectedKeys = new Set(getSelectedFields().map((f) => f.key));
    return FIELDS.filter((f) => !selectedKeys.has(f.key)).map((f) => f.csvKey);
  }

  // ---------- helpers generales ----------

  function formatPrice(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "—";
    return num.toLocaleString("es-AR", { style: "currency", currency: "ARS" });
  }

  function formatCellValue(field, product) {
    const value = product[field.key];
    if (value === null || value === undefined || value === "") return "—";
    if (field.key === "price") return formatPrice(value);
    return escapeHtml(value);
  }

  function cellTitleAttr(field, product) {
    if (field.key !== "name" && field.key !== "description") return "";
    const value = product[field.key];
    if (!value) return "";
    return ` title="${escapeHtml(value)}"`;
  }

  function currentFilters() {
    return {
      search: searchInput.value.trim(),
      view_mode: viewModeSelect.value,
      sort: sortSelect.value,
      order: orderSelect.value,
      exclude_fields: getExcludedCsvFields(),
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
    const params = new URLSearchParams({
      search: filters.search,
      view_mode: filters.view_mode,
      sort: filters.sort,
      order: filters.order,
      ...extra,
    });
    if (!filters.search) params.delete("search");
    return params.toString();
  }

  // ---------- tabla de vista previa ----------

  function renderPreviewTableHead() {
    const fields = getSelectedFields();
    previewTableHead.innerHTML = fields.map((f) => `<th>${escapeHtml(f.label)}</th>`).join("");
    previewTableEmpty.querySelector("td").colSpan = Math.max(fields.length, 1);
  }

  function renderPreviewRows(products, total) {
    previewTableBody.querySelectorAll("tr:not(#export-preview-table-empty)").forEach((r) => r.remove());

    const fields = getSelectedFields();

    if (!fields.length || !products.length) {
      previewTableEmpty.hidden = false;
      previewMore.hidden = true;
      return;
    }

    previewTableEmpty.hidden = true;

    products.forEach((product) => {
      const row = document.createElement("tr");
      row.innerHTML = fields
        .map((f) => `<td class="export-cell-${f.key}"${cellTitleAttr(f, product)}>${formatCellValue(f, product)}</td>`)
        .join("");
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

  // ---------- vista previa (conteo + muestra) ----------

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

      if (requestId !== previewRequestId) return; // ya quedó vieja

      const total = typeof data.total === "number" ? data.total : 0;
      const products = Array.isArray(data.data) ? data.data : [];

      previewCount.textContent = String(total);
      previewLabel.textContent =
        total === 1
          ? "producto coincide con los filtros elegidos"
          : "productos coinciden con los filtros elegidos";
      confirmBtn.disabled = total === 0 || getSelectedFields().length === 0;

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

  // ---------- exportar ----------

  async function handleExport() {
    if (getSelectedFields().length === 0) {
      columnsError.hidden = false;
      return;
    }

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
    columnsList.querySelectorAll("input[type=checkbox]").forEach((el) => {
      const field = FIELDS.find((f) => f.key === el.dataset.fieldKey);
      el.checked = field ? field.default : true;
    });
    columnsError.hidden = true;
    hideMessages();
    renderPreviewTableHead();
    refreshPreview();
    searchInput.focus();
  }

  // ---------- init ----------

  buildColumnCheckboxes();
  renderPreviewTableHead();

  [searchInput].forEach((el) => el.addEventListener("input", scheduleRefreshPreview));
  [viewModeSelect, sortSelect, orderSelect].forEach((el) =>
    el.addEventListener("change", scheduleRefreshPreview)
  );

  confirmBtn.addEventListener("click", handleExport);
  resetBtn.addEventListener("click", resetFilters);

  refreshPreview();
})();
