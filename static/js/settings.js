/**
 * settings.js
 * Gestiona el panel de ajustes: tabs, configuraciones dinámicas y formularios de usuario.
 */

// ─────────────────────────────────────────────────────────────────────────────
// LISTA DE CONFIGURACIONES EXCLUIDAS
// Agregá aquí las claves que NO querés mostrar en el panel de Sistema.
// ─────────────────────────────────────────────────────────────────────────────
const EXCLUDED_SETTINGS = [
  // "secret_key",
  // "db_url",
  // "internal_token",
];

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
// DETECCIÓN DE TIPO DE VALOR
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
// AGRUPADO DE CLAVES POR PREFIJO
// ─────────────────────────────────────────────────────────────────────────────
function isPlainObject(val) {
  return val !== null && typeof val === "object" && !Array.isArray(val);
}

/**
 * Convierte el JSON de la API (que puede tener objetos anidados, ej. "backup": {...})
 * en una lista de grupos: { groupName: [{ key, subKey, value }, ...] }
 *
 * - Si el valor de primer nivel es un objeto, sus propiedades se vuelven los campos
 *   del grupo, y el "key" para guardar es la clave padre (porque la API actualiza
 *   por clave de primer nivel: PUT /settings/actual/<key>).
 * - Si el valor de primer nivel es escalar, se agrupa solo bajo "General".
 * - Cualquier clave de primer nivel que empiece con "_" se considera metadata
 *   interna (ej. "_version") y se descarta automáticamente.
 */
function groupSettings(settingsObj) {
  const groups = {};

  for (const [topKey, topValue] of Object.entries(settingsObj)) {
    if (topKey.startsWith("_")) continue; // metadata interna, ej. _version
    if (EXCLUDED_SETTINGS.includes(topKey)) continue;

    if (isPlainObject(topValue)) {
      const fields = Object.entries(topValue)
        .filter(([subKey]) => !EXCLUDED_SETTINGS.includes(`${topKey}.${subKey}`))
        .map(([subKey, subValue]) => ({
          key: topKey,   // clave a usar en el PUT (nivel superior)
          subKey,         // clave real del campo dentro del objeto
          value: subValue,
        }));
      if (fields.length) {
        if (!groups[topKey]) groups[topKey] = [];
        groups[topKey].push(...fields);
      }
    } else {
      if (!groups.general) groups.general = [];
      groups.general.push({ key: topKey, subKey: null, value: topValue });
    }
  }

  return groups;
}

// ─────────────────────────────────────────────────────────────────────────────
// ÍCONOS SVG POR GRUPO
// ─────────────────────────────────────────────────────────────────────────────
const GROUP_ICONS = {
  general: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>`,
  mail: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>`,
  smtp: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>`,
  auth: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`,
  app: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8M12 17v4"/></svg>`,
  db: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>`,
  log: `<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
};

function getGroupIcon(groupName) {
  return GROUP_ICONS[groupName.toLowerCase()] || GROUP_ICONS.general;
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER DE UN CAMPO INDIVIDUAL
// ─────────────────────────────────────────────────────────────────────────────
function renderField({ key, subKey, value }) {
  const type = detectType(value);
  const label = keyToLabel(subKey || key);
  const fieldId = subKey ? `cfg-${key}-${subKey}` : `cfg-${key}`;
  const field = document.createElement("div");
  field.className = "config-field";
  field.dataset.key = key;
  field.dataset.type = type;
  if (subKey) field.dataset.subkey = subKey;

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
  const badgeId = subKey ? `badge-${key}-${subKey}` : `badge-${key}`;

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

  row.append(input, button, badge);
  field.append(labelEl, row);
  return field;
}

// ─────────────────────────────────────────────────────────────────────────────
// RENDER DE UNA TARJETA DE GRUPO
// ─────────────────────────────────────────────────────────────────────────────
function renderCard(groupName, fields) {
  const title =
    groupName === "general"
      ? "General"
      : groupName.charAt(0).toUpperCase() + groupName.slice(1);

  const icon = getGroupIcon(groupName);
  const card = document.createElement("div");
  card.className = "card config-card";

  const header = document.createElement("div");
  header.className = "config-card__header";

  const iconSpan = document.createElement("span");
  iconSpan.className = "config-card__icon";
  iconSpan.innerHTML = icon;

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
    this.container.innerHTML = `
      <div class="config-loading">
        <span class="spinner"></span>
        Cargando configuraciones…
      </div>`;
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
    icon.innerHTML = "<circle cx='12' cy='12' r='10'/><line x1='12' y1='8' x2='12' y2='12'/><line x1='12' y1='16' x2='12.01' y2='16'/>";

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
    const groups = groupSettings(data);

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
    grid.append(...Object.entries(groups).map(([name, fields]) => renderCard(name, fields)));
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

      const key = field.dataset.key;
      const subKey = field.dataset.subkey || null;
      const type = field.dataset.type;
      let rawValue = input.value;

      if (type === "number") rawValue = Number(rawValue);
      else if (type === "number-string") rawValue = String(rawValue);

      const valueToSend = this.buildValueToSend(key, subKey, rawValue);

      btn.disabled = true;
      btn.textContent = "…";

      try {
        await updateSetting(key, valueToSend);
        this.updateLocalData(key, subKey, rawValue);
        input.dataset.original = input.value;
        this.flashBadge(field);
      } catch (err) {
        showToast(`Error al guardar "${subKey || key}": ${err.message}`, true);
      } finally {
        btn.disabled = false;
        btn.textContent = "Guardar";
      }
    });

    // Toggles booleanos: guardado automático al cambiar
    this.container.addEventListener("change", async (e) => {
      const checkbox = e.target.closest('input[type="checkbox"]');
      if (!checkbox) return;

      const field = checkbox.closest(".config-field");
      if (!field) return;

      const key = field.dataset.key;
      const subKey = field.dataset.subkey || null;
      const type = field.dataset.type;
      const rawValue = type === "boolean-string" ? String(checkbox.checked) : checkbox.checked;

      const valueToSend = this.buildValueToSend(key, subKey, rawValue);

      checkbox.disabled = true;
      try {
        await updateSetting(key, valueToSend);
        this.updateLocalData(key, subKey, rawValue);
        this.flashBadge(field);
      } catch (err) {
        showToast(`Error al guardar "${subKey || key}": ${err.message}`, true);
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
   * Construye el valor a enviar en el PUT. Si el campo es parte de un objeto
   * anidado (ej. "backup.frequency_days"), hay que mandar el objeto "backup"
   * completo con esa sub-clave actualizada, porque la API actualiza por
   * clave de primer nivel únicamente.
   */
  buildValueToSend(key, subKey, rawValue) {
    if (!subKey) return rawValue;
    const currentGroup = isPlainObject(this.data[key]) ? this.data[key] : {};
    return { ...currentGroup, [subKey]: rawValue };
  },

  /** Refleja el valor recién guardado en la copia local this.data */
  updateLocalData(key, subKey, rawValue) {
    if (!subKey) {
      this.data[key] = rawValue;
    } else {
      if (!isPlainObject(this.data[key])) this.data[key] = {};
      this.data[key][subKey] = rawValue;
    }
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