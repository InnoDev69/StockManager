/**
 * settings.js
 * Gestiona el panel de ajustes: tabs, configuraciones dinámicas y formularios de usuario.
 */

// ─────────────────────────────────────────────────────────────────────────────
// LISTA DE CONFIGURACIONES EXCLUIDAS
// Agregá aquí las claves que NO querés mostrar en el panel de Sistema.
// Soporta notación de puntos para excluir sub-claves, ej. "backup.destination_path"
// o "roles.root" para excluir un rol entero de la matriz.
// ─────────────────────────────────────────────────────────────────────────────
const EXCLUDED_SETTINGS = [
  // "secret_key",
  // "db_url",
  // "internal_token",
];

// Sufijos de clave que indican "esto es una ruta de archivo/carpeta" → se les
// agrega un botón "Explorar…" que abre el selector nativo del SO vía pywebview.
const PATH_KEY_REGEX = /(^|_)(path|dir|directory|folder)$/i;

// ─────────────────────────────────────────────────────────────────────────────
// API HELPERS
// ─────────────────────────────────────────────────────────────────────────────
const API_BASE = "/api/settings/actual";

async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const getAllSettings = () => apiFetch(API_BASE);
const updateSetting = (key, value) =>
  apiFetch(`${API_BASE}/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  });

// ─────────────────────────────────────────────────────────────────────────────
// TOAST
// ─────────────────────────────────────────────────────────────────────────────
function showToast(msg, isError = false) {
  const toast = document.getElementById("toast");
  const toastMsg = document.getElementById("toastMsg");
  if (!toast || !toastMsg) return;
  toastMsg.textContent = msg;
  toast.classList.remove("hidden", "toast--error");
  if (isError) toast.classList.add("toast--error");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.add("hidden"), 3500);
}

// ─────────────────────────────────────────────────────────────────────────────
// TABS
// ─────────────────────────────────────────────────────────────────────────────
function initTabs() {
  const tabs = document.querySelectorAll(".s-nav__tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));

      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      const panel = document.getElementById(`tab-${tab.dataset.tab}`);
      if (panel) panel.classList.add("active");
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// DETECCIÓN DE TIPO DE VALOR (para campos escalares finales)
// ─────────────────────────────────────────────────────────────────────────────
function detectType(value) {
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "number") return "number";
  if (typeof value === "string") {
    const lower = value.toLowerCase();
    if (lower === "true" || lower === "false") return "boolean-string";
    if (!isNaN(value) && value.trim() !== "") return "number-string";
  }
  return "string";
}

function isPathField(name) {
  return PATH_KEY_REGEX.test(name);
}

// ─────────────────────────────────────────────────────────────────────────────
// FORMATEO DE CLAVE → ETIQUETA LEGIBLE
// ─────────────────────────────────────────────────────────────────────────────
function keyToLabel(key) {
  return key
    .replace(/[_\-\.]/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ─────────────────────────────────────────────────────────────────────────────
// ÁRBOL DE CONFIGURACIONES
// ─────────────────────────────────────────────────────────────────────────────
function isPlainObject(val) {
  return val !== null && typeof val === "object" && !Array.isArray(val);
}

function deepClone(val) {
  return val === undefined ? val : JSON.parse(JSON.stringify(val));
}

/**
 * Clasifica un valor de nivel superior:
 * - "scalar": string/number/boolean/array → va a la tarjeta "General"
 * - "flat":   objeto cuyas propiedades son todas escalares (o vacío) → tarjeta normal de campos
 * - "nested": objeto que contiene al menos una propiedad que es a su vez un objeto
 *             (ej. "roles": { admin: {...}, root: {...} }) → tarjeta de matriz
 */
function classifyValue(val) {
  if (!isPlainObject(val)) return "scalar";
  const entries = Object.entries(val);
  if (!entries.length) return "flat";
  const hasNestedObject = entries.some(([, v]) => isPlainObject(v));
  return hasNestedObject ? "nested" : "flat";
}

/**
 * Convierte el JSON de la API en una lista de grupos:
 *   groups[name] = { type: "fields", fields: [{ topKey, path, value }] }
 *   groups[name] = { type: "sections", sections: { subName: [{ topKey, path, value }] } }
 *
 * "topKey" es siempre la clave de primer nivel (la que acepta el endpoint PUT).
 * "path" es la ruta de claves dentro de ese objeto hasta llegar al valor editable,
 * ej. path=["frequency_days"] para backup.frequency_days,
 *     path=["admin", "barcode.manage"] para roles.admin["barcode.manage"].
 *
 * Cualquier clave de primer nivel que empiece con "_" se considera metadata
 * interna (ej. "_version") y se descarta automáticamente.
 */
function buildConfigTree(settingsObj) {
  const groups = {};

  for (const [topKey, topValue] of Object.entries(settingsObj)) {
    if (topKey.startsWith("_")) continue;
    if (EXCLUDED_SETTINGS.includes(topKey)) continue;

    const kind = classifyValue(topValue);

    if (kind === "scalar") {
      if (!groups.general) groups.general = { type: "fields", fields: [] };
      groups.general.fields.push({ topKey, path: [], value: topValue });
      continue;
    }

    if (kind === "flat") {
      const fields = Object.entries(topValue)
        .filter(([subKey]) => !EXCLUDED_SETTINGS.includes(`${topKey}.${subKey}`))
        .map(([subKey, subValue]) => ({ topKey, path: [subKey], value: subValue }));
      if (fields.length) groups[topKey] = { type: "fields", fields };
      continue;
    }

    // kind === "nested" → tarjeta de matriz (ej. roles)
    const sections = {};
    for (const [midKey, midValue] of Object.entries(topValue)) {
      if (EXCLUDED_SETTINGS.includes(`${topKey}.${midKey}`)) continue;

      if (isPlainObject(midValue)) {
        sections[midKey] = Object.entries(midValue).map(([leafKey, leafValue]) => ({
          topKey,
          path: [midKey, leafKey],
          value: leafValue,
        }));
      } else {
        // valor escalar mezclado al mismo nivel que las sub-secciones: lo agrupamos aparte
        if (!sections.__general) sections.__general = [];
        sections.__general.push({ topKey, path: [midKey], value: midValue });
      }
    }
    groups[topKey] = { type: "sections", sections };
  }

  return groups;
}

// ─────────────────────────────────────────────────────────────────────────────
// ÍCONOS SVG POR GRUPO
// ─────────────────────────────────────────────────────────────────────────────
const SVG_NS = "http://www.w3.org/2000/svg";

const GROUP_ICONS = {
  general: {
    viewBox: "0 0 24 24",
    elements: [
      { tag: "circle", attrs: { cx: "12", cy: "12", r: "3" } },
      { tag: "path", attrs: { d: "M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" } },
    ],
  },
  mail: {
    viewBox: "0 0 24 24",
    elements: [
      { tag: "rect", attrs: { width: "20", height: "16", x: "2", y: "4", rx: "2" } },
      { tag: "path", attrs: { d: "m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" } },
    ],
  },
  smtp: {
    viewBox: "0 0 24 24",
    elements: [
      { tag: "rect", attrs: { width: "20", height: "16", x: "2", y: "4", rx: "2" } },
      { tag: "path", attrs: { d: "m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" } },
    ],
  },
  auth: {
    viewBox: "0 0 24 24",
    elements: [
      { tag: "rect", attrs: { width: "18", height: "11", x: "3", y: "11", rx: "2" } },
      { tag: "path", attrs: { d: "M7 11V7a5 5 0 0 1 10 0v4" } },
    ],
  },
  app: {
    viewBox: "0 0 24 24",
    elements: [
      { tag: "rect", attrs: { width: "20", height: "14", x: "2", y: "3", rx: "2" } },
      { tag: "path", attrs: { d: "M8 21h8M12 17v4" } },
    ],
  },
  db: {
    viewBox: "0 0 24 24",
    elements: [
      { tag: "ellipse", attrs: { cx: "12", cy: "5", rx: "9", ry: "3" } },
      { tag: "path", attrs: { d: "M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" } },
      { tag: "path", attrs: { d: "M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" } },
    ],
  },
  log: {
    viewBox: "0 0 24 24",
    elements: [
      { tag: "path", attrs: { d: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" } },
      { tag: "polyline", attrs: { points: "14 2 14 8 20 8" } },
      { tag: "line", attrs: { x1: "16", y1: "13", x2: "8", y2: "13" } },
      { tag: "line", attrs: { x1: "16", y1: "17", x2: "8", y2: "17" } },
    ],
  },
  backup: {
    viewBox: "0 0 24 24",
    elements: [
      { tag: "path", attrs: { d: "M21 12a9 9 0 1 1-2.64-6.36" } },
      { tag: "polyline", attrs: { points: "21 3 21 9 15 9" } },
    ],
  },
};
GROUP_ICONS.roles = GROUP_ICONS.auth;
GROUP_ICONS.experimental_features = GROUP_ICONS.app;

function createSvgElement(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([key, value]) => {
    el.setAttribute(key, value);
  });
  return el;
}

function getGroupIcon(groupName) {
  const icon = GROUP_ICONS[groupName.toLowerCase()] || GROUP_ICONS.general;
  const svg = createSvgElement("svg", {
    width: "14",
    height: "14",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    viewBox: icon.viewBox,
  });
  icon.elements.forEach((item) => svg.appendChild(createSvgElement(item.tag, item.attrs)));
  return svg;
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER DE UN CAMPO INDIVIDUAL (usado en tarjetas de tipo "fields")
// ─────────────────────────────────────────────────────────────────────────────
function renderField({ topKey, path, value }) {
  const type = detectType(value);
  const leafName = path.length ? path[path.length - 1] : topKey;
  const label = keyToLabel(leafName);
  const fieldId = `cfg-${topKey}-${path.join("-")}`;
  const field = document.createElement("div");
  field.className = "config-field";
  field.dataset.topkey = topKey;
  field.dataset.path = JSON.stringify(path);
  field.dataset.type = type;

  if (type === "boolean" || type === "boolean-string") {
    const checked = value === true || value === "true";
    const toggleRow = document.createElement("div");
    toggleRow.className = "config-field__toggle-row";

    const toggleLabel = document.createElement("span");
    toggleLabel.className = "config-field__toggle-label";
    toggleLabel.textContent = label;

    const toggle = document.createElement("label");
    toggle.className = "toggle";
    toggle.title = `Activar/desactivar ${label}`;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = fieldId;
    checkbox.checked = checked;

    const rail = document.createElement("span");
    rail.className = "toggle__rail";

    toggle.append(checkbox, rail);
    toggleRow.append(toggleLabel, toggle);
    field.append(toggleRow);
    return field;
  }

  const inputType = type === "number" || type === "number-string" ? "number" : "text";
  const badgeId = `badge-${topKey}-${path.join("-")}`;

  const labelEl = document.createElement("label");
  labelEl.className = "config-field__label";
  labelEl.htmlFor = fieldId;
  labelEl.textContent = label;

  const row = document.createElement("div");
  row.className = "config-field__row";

  const input = document.createElement("input");
  input.type = inputType;
  input.id = fieldId;
  input.value = String(value);
  input.dataset.original = String(value);
  input.autocomplete = "off";
  input.spellcheck = false;

  const button = document.createElement("button");
  button.className = "btn btn--primary btn-xs config-save-btn";
  button.setAttribute("aria-label", `Guardar ${label}`);
  button.textContent = "Guardar";

  const badge = document.createElement("span");
  badge.className = "saved-badge";
  badge.id = badgeId;
  badge.textContent = "✓";

  const rowChildren = [input];

  if (isPathField(leafName)) {
    input.readOnly = true;
    const browseBtn = document.createElement("button");
    browseBtn.type = "button";
    browseBtn.className = "btn btn--ghost btn-xs config-browse-btn";
    browseBtn.textContent = "Explorar…";
    browseBtn.addEventListener("click", async () => {
      if (!window.pywebview?.api?.select_folder) {
        showToast("El selector de carpetas no está disponible en este entorno.", true);
        return;
      }
      browseBtn.disabled = true;
      try {
        const folder = await window.pywebview.api.select_folder();
        if (folder) {
          input.value = folder;
          button.click(); // reutiliza el flujo de guardado normal
        }
      } catch (err) {
        showToast(`No se pudo abrir el explorador: ${err.message}`, true);
      } finally {
        browseBtn.disabled = false;
      }
    });
    rowChildren.push(browseBtn);
  }

  rowChildren.push(button, badge);
  row.append(...rowChildren);
  field.append(labelEl, row);
  return field;
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER DE UNA TARJETA DE CAMPOS PLANOS
// ─────────────────────────────────────────────────────────────────────────────
function renderCard(groupName, fields) {
  const title = keyToLabel(groupName);
  const icon = getGroupIcon(groupName);
  const card = document.createElement("div");
  card.className = "card config-card";

  const header = document.createElement("div");
  header.className = "config-card__header";

  const iconSpan = document.createElement("span");
  iconSpan.className = "config-card__icon";
  iconSpan.appendChild(icon);

  const titleEl = document.createElement("h3");
  titleEl.className = "config-card__title";
  titleEl.textContent = title;

  const body = document.createElement("div");
  body.className = "config-card__body";
  body.append(...fields.map(renderField));

  header.append(iconSpan, titleEl);
  card.append(header, body);
  return card;
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER DE UNA TARJETA DE MATRIZ (grupos anidados, ej. roles → permisos)
// ─────────────────────────────────────────────────────────────────────────────
function renderMatrixCard(topKey, sections) {
  const title = keyToLabel(topKey);
  const icon = getGroupIcon(topKey);
  const card = document.createElement("div");
  card.className = "card config-card config-card--matrix";

  const header = document.createElement("div");
  header.className = "config-card__header";
  const iconSpan = document.createElement("span");
  iconSpan.className = "config-card__icon";
  iconSpan.appendChild(icon);
  const titleEl = document.createElement("h3");
  titleEl.className = "config-card__title";
  titleEl.textContent = title;
  header.append(iconSpan, titleEl);

  const body = document.createElement("div");
  body.className = "config-card__body config-matrix-wrap";

  // Campos escalares sueltos al mismo nivel que las sub-secciones (poco común, pero por las dudas)
  if (sections.__general?.length) {
    body.append(...sections.__general.map(renderField));
  }

  const sectionNames = Object.keys(sections).filter((n) => n !== "__general");
  const permKeys = [
    ...new Set(sectionNames.flatMap((name) => sections[name].map((f) => f.path[f.path.length - 1]))),
  ];

  if (!sectionNames.length || !permKeys.length) {
    if (!sections.__general?.length) {
      const empty = document.createElement("p");
      empty.className = "config-matrix-empty";
      empty.textContent = "No hay datos para mostrar.";
      body.append(empty);
    }
    card.append(header, body);
    return card;
  }

  const table = document.createElement("table");
  table.className = "config-matrix";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headRow.appendChild(document.createElement("th"));
  sectionNames.forEach((name) => {
    const th = document.createElement("th");
    th.textContent = keyToLabel(name);
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  permKeys.forEach((permKey) => {
    const row = document.createElement("tr");
    const rowLabel = document.createElement("th");
    rowLabel.className = "config-matrix__row-label";
    rowLabel.textContent = keyToLabel(permKey);
    row.appendChild(rowLabel);

    sectionNames.forEach((name) => {
      const td = document.createElement("td");
      const existing = sections[name].find((f) => f.path[f.path.length - 1] === permKey);
      const value = existing ? existing.value : false;

      const toggle = document.createElement("label");
      toggle.className = "toggle toggle--sm";
      toggle.title = `${keyToLabel(name)}: ${keyToLabel(permKey)}`;

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = value === true || value === "true";
      checkbox.dataset.topkey = topKey;
      checkbox.dataset.path = JSON.stringify([name, permKey]);

      const rail = document.createElement("span");
      rail.className = "toggle__rail";

      toggle.append(checkbox, rail);
      td.appendChild(toggle);
      row.appendChild(td);
    });

    tbody.appendChild(row);
  });

  table.append(thead, tbody);
  body.appendChild(table);
  card.append(header, body);
  return card;
}

// ─────────────────────────────────────────────────────────────────────────────
// SECCIÓN DE CONFIGURACIÓN PRINCIPAL
// ─────────────────────────────────────────────────────────────────────────────
const ConfigSection = {
  container: null,
  data: {}, // copia local del JSON completo de settings, para reconstruir objetos anidados al guardar

  async init() {
    this.container = document.getElementById("configSettingsContainer");
    if (!this.container) return;
    this.renderLoading();
    try {
      const data = await getAllSettings();
      this.data = data;
      this.renderSettings(data);
      this.bindEvents();
    } catch (err) {
      this.renderError(err.message);
    }
  },

  renderLoading() {
    const loading = document.createElement("div");
    loading.className = "config-loading";

    const spinner = document.createElement("span");
    spinner.className = "spinner";

    loading.append(spinner, document.createTextNode("Cargando configuraciones…"));
    this.container.replaceChildren(loading);
  },

  renderError(msg) {
    const card = document.createElement("div");
    card.className = "card";
    card.style.padding = "2rem 1.5rem";
    card.style.textAlign = "center";
    card.style.color = "var(--danger, #e53e3e)";

    const icon = document.createElement("svg");
    icon.width = "24";
    icon.height = "24";
    icon.fill = "none";
    icon.stroke = "currentColor";
    icon.setAttribute("stroke-width", "2");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.style.margin = "0 auto 0.75rem";
    icon.style.display = "block";
    icon.style.opacity = ".7";
    icon.append(
      createSvgElement("circle", { cx: "12", cy: "12", r: "10" }),
      createSvgElement("line", { x1: "12", y1: "8", x2: "12", y2: "12" }),
      createSvgElement("line", { x1: "12", y1: "16", x2: "12.01", y2: "16" }),
    );

    const title = document.createElement("strong");
    title.textContent = "No se pudieron cargar las configuraciones";

    const message = document.createElement("p");
    message.style.fontSize = "0.85rem";
    message.style.margin = "0.5rem 0 1rem";
    message.style.color = "var(--text-muted)";
    message.textContent = msg;

    const retryButton = document.createElement("button");
    retryButton.className = "btn btn--ghost";
    retryButton.id = "configRetryBtn";
    retryButton.textContent = "Reintentar";
    retryButton.addEventListener("click", () => this.init());

    card.append(icon, title, message, retryButton);
    this.container.replaceChildren(card);
  },

  renderSettings(data) {
    const groups = buildConfigTree(data);

    if (!Object.keys(groups).length) {
      const emptyState = document.createElement("div");
      emptyState.className = "card";
      emptyState.style.padding = "2.5rem";
      emptyState.style.textAlign = "center";
      emptyState.style.color = "var(--text-muted)";
      emptyState.textContent = "No hay configuraciones disponibles.";
      this.container.replaceChildren(emptyState);
      return;
    }

    const grid = document.createElement("div");
    grid.className = "config-grid";
    grid.append(
      ...Object.entries(groups).map(([name, group]) =>
        group.type === "sections" ? renderMatrixCard(name, group.sections) : renderCard(name, group.fields),
      ),
    );
    this.container.replaceChildren(grid);
  },

  bindEvents() {
    if (!this.container) return;

    // Botones "Guardar" en campos de texto/número
    this.container.addEventListener("click", async (e) => {
      const btn = e.target.closest(".config-save-btn");
      if (!btn) return;

      const field = btn.closest(".config-field");
      const input = field?.querySelector("input");
      if (!input || !field) return;

      const topKey = field.dataset.topkey;
      const path = JSON.parse(field.dataset.path);
      const type = field.dataset.type;
      let rawValue = input.value;

      if (type === "number") rawValue = Number(rawValue);
      else if (type === "number-string") rawValue = String(rawValue);

      const valueToSend = this.buildValueToSend(topKey, path, rawValue);

      btn.disabled = true;
      btn.textContent = "…";

      try {
        await updateSetting(topKey, valueToSend);
        this.updateLocalData(topKey, path, rawValue);
        input.dataset.original = input.value;
        this.flashBadge(field);
      } catch (err) {
        showToast(`Error al guardar "${path[path.length - 1] || topKey}": ${err.message}`, true);
        throw err; 
      } finally {
        btn.disabled = false;
        btn.textContent = "Guardar";
      }
    });

    // Checkboxes: toggles de campos simples Y celdas de la matriz (guardado automático)
    this.container.addEventListener("change", async (e) => {
      const checkbox = e.target.closest('input[type="checkbox"]');
      if (!checkbox) return;

      // Caso 1: celda dentro de una tarjeta de matriz (ej. roles)
      const matrixTable = checkbox.closest(".config-matrix");
      if (matrixTable) {
        const topKey = checkbox.dataset.topkey;
        const path = JSON.parse(checkbox.dataset.path);
        const rawValue = checkbox.checked;
        const valueToSend = this.buildValueToSend(topKey, path, rawValue);

        checkbox.disabled = true;
        try {
          await updateSetting(topKey, valueToSend);
          this.updateLocalData(topKey, path, rawValue);
        } catch (err) {
          showToast(`Error al guardar "${path.join(" → ")}": ${err.message}`, true);
          checkbox.checked = !checkbox.checked;
          throw err;
        } finally {
          checkbox.disabled = false;
        }
        return;
      }

      // Caso 2: toggle booleano de un campo simple
      const field = checkbox.closest(".config-field");
      if (!field) return;

      const topKey = field.dataset.topkey;
      const path = JSON.parse(field.dataset.path);
      const type = field.dataset.type;
      const rawValue = type === "boolean-string" ? String(checkbox.checked) : checkbox.checked;

      const valueToSend = this.buildValueToSend(topKey, path, rawValue);

      checkbox.disabled = true;
      try {
        await updateSetting(topKey, valueToSend);
        this.updateLocalData(topKey, path, rawValue);
        this.flashBadge(field);
      } catch (err) {
        showToast(`Error al guardar "${path[path.length - 1] || topKey}": ${err.message}`, true);
        checkbox.checked = !checkbox.checked; // revertir
      } finally {
        checkbox.disabled = false;
      }
    });

    // Guardar con Enter en inputs de texto/número
    this.container.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      const input = e.target.closest('.config-field input[type="text"], .config-field input[type="number"]');
      if (!input) return;
      const btn = input.closest(".config-field__row")?.querySelector(".config-save-btn");
      btn?.click();
    });
  },

  /**
   * Construye el valor a enviar en el PUT. La API solo permite actualizar por
   * clave de primer nivel (topKey), así que si el campo vive en una ruta más
   * profunda (path), hay que reconstruir el objeto completo de topKey con esa
   * ruta actualizada, preservando todo lo demás.
   */
  buildValueToSend(topKey, path, rawValue) {
    if (!path.length) return rawValue;

    const cloned = isPlainObject(this.data[topKey]) ? deepClone(this.data[topKey]) : {};
    let cursor = cloned;
    for (let i = 0; i < path.length - 1; i++) {
      const segment = path[i];
      if (!isPlainObject(cursor[segment])) cursor[segment] = {};
      cursor = cursor[segment];
    }
    cursor[path[path.length - 1]] = rawValue;
    return cloned;
  },

  /** Refleja el valor recién guardado en la copia local this.data */
  updateLocalData(topKey, path, rawValue) {
    if (!path.length) {
      this.data[topKey] = rawValue;
      return;
    }
    if (!isPlainObject(this.data[topKey])) this.data[topKey] = {};
    let cursor = this.data[topKey];
    for (let i = 0; i < path.length - 1; i++) {
      const segment = path[i];
      if (!isPlainObject(cursor[segment])) cursor[segment] = {};
      cursor = cursor[segment];
    }
    cursor[path[path.length - 1]] = rawValue;
  },

  flashBadge(field) {
    const badge = field.querySelector(".saved-badge");
    if (!badge) return;
    badge.classList.add("visible");
    setTimeout(() => badge.classList.remove("visible"), 2200);
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// FORMULARIO PERFIL
// ─────────────────────────────────────────────────────────────────────────────
function initProfileForm() {
  const form = document.getElementById("profileForm");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = form.querySelector('[name="email"]')?.value?.trim();
    if (!email) return showToast("El correo es requerido.", true);

    const btn = form.querySelector('[type="submit"]');
    btn.disabled = true;

    try {
      const res = await fetch("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error desconocido");

      const badge = document.getElementById("profileSavedBadge");
      badge?.classList.add("visible");
      setTimeout(() => badge?.classList.remove("visible"), 2500);
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btn.disabled = false;
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// FORMULARIO CONTRASEÑA
// ─────────────────────────────────────────────────────────────────────────────
function initPasswordForm() {
  const form = document.getElementById("passwordForm");
  if (!form) return;

  const newPass = form.querySelector("#newPass");
  const confirmPass = form.querySelector("#confirmPass");
  const matchMsg = document.getElementById("passMatchMsg");

  function checkMatch() {
    if (!confirmPass.value) {
      matchMsg.style.display = "none";
      return true;
    }
    const match = newPass.value === confirmPass.value;
    matchMsg.style.display = "block";
    matchMsg.textContent = match ? "✓ Las contraseñas coinciden" : "✗ Las contraseñas no coinciden";
    matchMsg.style.color = match ? "var(--success, #38a169)" : "var(--danger, #e53e3e)";
    return match;
  }

  newPass?.addEventListener("input", checkMatch);
  confirmPass?.addEventListener("input", checkMatch);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!checkMatch()) return showToast("Las contraseñas no coinciden.", true);

    const payload = {
      current_password: form.querySelector('[name="current_password"]')?.value,
      new_password: newPass?.value,
    };

    const btn = form.querySelector('[type="submit"]');
    btn.disabled = true;

    try {
      const res = await fetch("/api/profile/password", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error al actualizar");

      form.reset();
      matchMsg.style.display = "none";
      const badge = document.getElementById("passwordSavedBadge");
      badge?.classList.add("visible");
      setTimeout(() => badge?.classList.remove("visible"), 2500);
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btn.disabled = false;
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// BOOTSTRAP
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initProfileForm();
  initPasswordForm();
  ConfigSection.init();
});