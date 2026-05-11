// ════════════════════════════════════════════════════
// Users Management Module
// ════════════════════════════════════════════════════

// ── Estado global ───────────────────────────────────────
let currentPage    = 1;
let searchTimer    = null;
let deleteUserId   = null;
let activityUserId = null;
let activityPage   = 1;

// ── Modal helpers ───────────────────────────────────────
function openModal(id) {
  const el = document.getElementById(id);
  el.style.display = "flex";
  requestAnimationFrame(() => el.classList.add("open"));
  document.body.style.overflow = "hidden";
}
function closeModal(id) {
  const el = document.getElementById(id);
  el.classList.remove("open");
  el.addEventListener("transitionend", () => {
    el.style.display = "none";
    document.body.style.overflow = "";
  }, { once: true });
}
function overlayClose(e, id) {
  if (e.target.id === id) closeModal(id);
}

// ── Carga de usuarios ───────────────────────────────────
async function loadUsers(page = 1) {
  currentPage = page;
  const search = document.getElementById("searchInput").value.trim();
  const status = document.getElementById("statusFilter").value;
  showTableLoading();

  const params = new URLSearchParams({ page, limit: 10 });
  if (search) params.append("search", search);

  try {
    const res  = await fetch(`/api/users?${params}`);
    if (!res.ok) throw new Error();
    const data = await res.json();

    let users = data.data;
    if (status !== "") users = users.filter(u => String(u.status) === status);

    renderTable(users);
    renderPagination(data.page, data.pages);
    document.getElementById("totalCount").textContent =
      `${data.total} usuario${data.total !== 1 ? "s" : ""}`;
    document.getElementById("pageInfo").textContent =
      users.length ? `Página ${data.page} de ${data.pages}` : "";
  } catch {
    showTableError("No se pudo cargar la lista de usuarios");
  }
}

function showTableLoading() {
  document.getElementById("usersTableBody").innerHTML = `
    <tr><td colspan="7" style="text-align:center; padding:3rem; color:var(--text-muted);">
      <div class="spinner" style="margin:0 auto .75rem;"></div>Cargando...
    </td></tr>`;
}

function renderTable(users) {
  const tbody = document.getElementById("usersTableBody");
  if (!users.length) {
    tbody.innerHTML = `
      <tr><td colspan="7" style="text-align:center; padding:3rem; color:var(--text-muted);">
        <svg width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5"
             viewBox="0 0 24 24" style="display:block; margin:0 auto .75rem; opacity:.35;">
          <path d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"/>
        </svg>Sin resultados
      </td></tr>`;
    return;
  }

  const ROW_BORDER = "border-bottom:1px solid var(--border);";

  tbody.innerHTML = users.map(u => {
    const initial = escHtml(u.username.charAt(0).toUpperCase());
    const hue     = [...u.username].reduce((a,c)=>a+c.charCodeAt(0),0) % 360;
    const roleBadge = getRoleBadge(u.role);

    const statusBadge = u.status
      ? `<span style="display:inline-flex; align-items:center; gap:.3rem; padding:.2rem .6rem;
                      border-radius:99px; font-size:.75rem; font-weight:600;
                      background:color-mix(in srgb,var(--success) 15%,transparent);
                      color:var(--success); border:1px solid color-mix(in srgb,var(--success) 30%,transparent);">
           <span style="width:6px;height:6px;border-radius:50%;
                        background:var(--success);display:inline-block;"></span>Activo
         </span>`
      : `<span style="display:inline-flex; align-items:center; gap:.3rem; padding:.2rem .6rem;
                      border-radius:99px; font-size:.75rem; font-weight:600;
                      background:color-mix(in srgb,var(--danger) 15%,transparent);
                      color:var(--danger); border:1px solid color-mix(in srgb,var(--danger) 30%,transparent);">
           <span style="width:6px;height:6px;border-radius:50%;
                        background:var(--danger);display:inline-block;"></span>Inactivo
         </span>`;

    const toggleBtn = u.status
      ? `<button class="icon-btn danger" title="Dar de baja"
                 onclick="openDeleteModal(${u.id},'${escHtml(u.username)}')">
           <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"
                viewBox="0 0 24 24">
             <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
             <circle cx="9" cy="7" r="4"/>
             <line x1="17" y1="8" x2="23" y2="14"/>
             <line x1="23" y1="8" x2="17" y2="14"/>
           </svg>
         </button>`
      : `<button class="icon-btn success" title="Reactivar"
                 onclick="reactivateUser(${u.id})">
           <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"
                viewBox="0 0 24 24">
             <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
             <circle cx="9" cy="7" r="4"/>
             <polyline points="16 11 18 13 22 9"/>
           </svg>
         </button>`;

    return `
      <tr style="${ROW_BORDER} transition:background .12s ease;"
          onmouseover="this.style.background='var(--panel-2)'"
          onmouseout="this.style.background=''">
        <td style="padding:.75rem 1rem; color:var(--text-muted); font-size:.82rem;">${u.id}</td>
        <td style="padding:.75rem .75rem;">
          <div style="display:flex; align-items:center; gap:.65rem;">
            <div style="width:34px; height:34px; border-radius:50%; flex-shrink:0;
                        background:hsl(${hue},55%,45%); display:flex; align-items:center;
                        justify-content:center; font-weight:700; font-size:.85rem; color:#fff;
                        box-shadow:0 2px 6px rgba(0,0,0,.25);">${initial}</div>
            <span style="font-weight:600;">${escHtml(u.username)}</span>
          </div>
        </td>
        <td style="padding:.75rem .75rem; color:var(--text-muted); font-size:.875rem;">
          ${escHtml(u.email)}
        </td>
        <td style="padding:.75rem .75rem;">${roleBadge}</td>
        <td style="padding:.75rem .75rem;">${statusBadge}</td>
        <td style="padding:.75rem .75rem; color:var(--text-muted); font-size:.82rem;">
          ${formatDate(u.created_at)}
        </td>
        <td style="padding:.75rem 1rem; text-align:center;">
          <div style="display:flex; justify-content:center; gap:.35rem;">
            <button class="icon-btn info" title="Ver actividad"
                    onclick="openActivity(${u.id},'${escHtml(u.username)}')">
              <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"
                   viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
            </button>
            <button class="icon-btn primary" title="Editar"
                    onclick="openEditModal(${u.id})">
              <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"
                   viewBox="0 0 24 24">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            ${toggleBtn}
          </div>
        </td>
      </tr>`;
  }).join("");
}

function renderPagination(current, total) {
  const container = document.getElementById("pagination");
  container.innerHTML = "";
  if (total <= 1) return;

  const btn = (label, page, disabled, active) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.disabled    = disabled;
    b.style.cssText = `
      padding:.35rem .65rem; border-radius:8px; border:1px solid var(--border);
      background:${active ? "var(--brand)" : "var(--panel-2)"}; cursor:pointer;
      color:${active ? "#fff" : "var(--text)"}; font-size:.82rem;
      opacity:${disabled ? ".4" : "1"}; font-weight:${active ? "600" : "400"};`;
    if (!disabled) b.onclick = () => loadUsers(page);
    return b;
  };

  container.appendChild(btn("‹", current - 1, current === 1, false));
  for (let i = 1; i <= total; i++)
    container.appendChild(btn(i, i, false, i === current));
  container.appendChild(btn("›", current + 1, current === total, false));
}

function showTableError(msg) {
  document.getElementById("usersTableBody").innerHTML = `
    <tr><td colspan="7" style="text-align:center; padding:3rem; color:var(--danger);">
      <svg width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5"
           viewBox="0 0 24 24" style="display:block; margin:0 auto .75rem; opacity:.7;">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>${msg}
    </td></tr>`;
}

// ── Debounce ────────────────────────────────────────────
function debounceSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadUsers(1), 350);
}

// ── Modal crear ─────────────────────────────────────────
function openCreateModal() {
  document.getElementById("userModalTitle").textContent = "Nuevo Usuario";
  document.getElementById("fieldUsername").value = "";
  document.getElementById("fieldEmail").value    = "";
  document.getElementById("fieldPassword").value = "";
  document.getElementById("fieldRole").value     = window.ROLES.VENDOR;
  document.getElementById("editUserId").value    = "";
  document.getElementById("statusField").style.display   = "none";
  document.getElementById("passwordRequired").style.display = "inline";
  document.getElementById("passwordHint").textContent    = "";
  openModal("userModal");
}

// ── Modal editar ────────────────────────────────────────
async function openEditModal(userId) {
  try {
    const res  = await fetch(`/api/users/${userId}`);
    if (!res.ok) throw new Error();
    const user = await res.json();

    document.getElementById("userModalTitle").textContent  = "Editar Usuario";
    document.getElementById("editUserId").value    = user.id;
    document.getElementById("fieldUsername").value = user.username;
    document.getElementById("fieldEmail").value    = user.email;
    document.getElementById("fieldRole").value     = user.role;
    document.getElementById("fieldStatus").value   = String(user.status);
    document.getElementById("fieldPassword").value = "";
    document.getElementById("passwordRequired").style.display = "none";
    document.getElementById("passwordHint").textContent = "Dejá en blanco para no cambiar";
    document.getElementById("statusField").style.display = "grid";

    if (user.email === window.CURRENT_USER) {
      document.getElementById("fieldStatus").disabled = true;
      document.getElementById("fieldRole").disabled = true;
      // TOMAKE: tal vez un tooltip que diga "No podés cambiar tu propio rol o estado"?
    } else {
      document.getElementById("fieldStatus").disabled = false;
      document.getElementById("fieldRole").disabled = false;
    }

    openModal("userModal");
  } catch (err) {
    console.error(err);
    showToast("No se pudo cargar el usuario", "danger");
  }
}

// ── Guardar usuario ─────────────────────────────────────
async function saveUser() {
  const id       = document.getElementById("editUserId").value;
  const username = document.getElementById("fieldUsername").value.trim();
  const email    = document.getElementById("fieldEmail").value.trim();
  const password = document.getElementById("fieldPassword").value;
  const role     = document.getElementById("fieldRole").value;
  const status   = document.getElementById("fieldStatus").value;

  if (!username || !email) { showToast("Completá los campos requeridos", "warning"); return; }
  if (!id && !password)    { showToast("La contraseña es obligatoria para nuevos usuarios", "warning"); return; }
  if (password && password.length < 6) { showToast("La contraseña debe tener al menos 6 caracteres", "warning"); return; }
  if (email === window.CURRENT_USER && status === "0") { showToast("No podés desactivar tu propio usuario", "warning"); return; }

  const btn = document.getElementById("saveBtn");
  btn.disabled    = true;
  btn.textContent = "Guardando...";

  const payload = { username, email, role };
  if (password) payload.password = password;
  if (id)       payload.status   = parseInt(status);

  try {
    const res  = await fetch(id ? `/api/users/${id}` : "/api/users", {
      method:  id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      closeModal("userModal");
      showToast(data.message, "success");
      loadUsers(currentPage);
    } else {
      showToast(data.error || "Error al guardar", "danger");
    }
  } catch {
    showToast("Error de conexión", "danger");
  } finally {
    btn.disabled    = false;
    btn.textContent = "Guardar";
  }
}

// ── Modal baja ──────────────────────────────────────────
function openDeleteModal(id, username) {
  deleteUserId = id;
  document.getElementById("deleteUsername").textContent = username;
  openModal("deleteModal");
}

async function confirmDelete() {
  try {
    const res  = await fetch(`/api/users/${deleteUserId}`, { method: "DELETE" });
    const data = await res.json();
    closeModal("deleteModal");
    showToast(res.ok ? data.message : data.error, res.ok ? "success" : "danger");
    if (res.ok) loadUsers(currentPage);
  } catch {
    showToast("Error de conexión", "danger");
  }
}

// ── Reactivar ───────────────────────────────────────────
async function reactivateUser(id) {
  try {
    const res  = await fetch(`/api/users/${id}`, {
      method:  "PUT",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ status: 1 })
    });
    const data = await res.json();
    showToast(res.ok ? "Usuario reactivado" : data.error, res.ok ? "success" : "danger");
    if (res.ok) loadUsers(currentPage);
  } catch {
    showToast("Error de conexión", "danger");
  }
}

// ── Actividad ───────────────────────────────────────────
async function openActivity(userId, username) {
  activityUserId = userId;
  activityPage   = 1;
  document.getElementById("activityUsername").textContent = username;
  document.getElementById("activityLoading").style.display = "block";
  document.getElementById("activityTable").style.display   = "none";
  document.getElementById("activityEmpty").style.display   = "none";
  document.getElementById("activityTableBody").innerHTML   = "";
  document.getElementById("activityPageInfo").textContent  = "";
  document.getElementById("activityPagination").innerHTML  = "";
  openModal("activityModal");
  await loadActivity(1);
}

async function loadActivity(page = 1) {
  activityPage = page;
  try {
    const res  = await fetch(`/api/users/${activityUserId}/activity?page=${page}&limit=10`);
    if (!res.ok) throw new Error();
    const data = await res.json();

    document.getElementById("activityLoading").style.display = "none";

    if (!data.data.length) {
      document.getElementById("activityEmpty").style.display = "block";
      document.getElementById("activityPageInfo").textContent = "Sin ventas registradas";
      return;
    }

    document.getElementById("activityTable").style.display = "table";
    document.getElementById("activityTableBody").innerHTML = data.data.map(r => `
      <tr style="border-bottom:1px solid var(--border);"
          onmouseover="this.style.background='var(--panel-2)'"
          onmouseout="this.style.background=''">
        <td style="padding:.65rem 1rem; color:var(--text-muted); font-size:.82rem;">
          #${r.sale_id}</td>
        <td style="padding:.65rem .75rem; font-size:.875rem;">${formatDate(r.date)}</td>
        <td style="padding:.65rem .75rem;">
          <span style="padding:.2rem .55rem; border-radius:6px; font-size:.78rem;
                       background:var(--panel-2); border:1px solid var(--border);">
            ${escHtml(r.payment_method)}
          </span>
        </td>
        <td style="padding:.65rem .75rem; text-align:center;">
          <span style="padding:.2rem .55rem; border-radius:6px; font-size:.78rem;
                       background:color-mix(in srgb,var(--brand) 12%,transparent);
                       color:var(--brand); border:1px solid color-mix(in srgb,var(--brand) 25%,transparent);">
            ${r.items}
          </span>
        </td>
        <td style="padding:.65rem 1rem; text-align:right; font-weight:600;">
          $${r.total.toFixed(2)}</td>
      </tr>`).join("");

    document.getElementById("activityPageInfo").textContent =
      `Página ${data.page} de ${data.pages} · ${data.total} venta${data.total !== 1 ? "s" : ""}`;

    const pag = document.getElementById("activityPagination");
    pag.innerHTML = "";
    if (data.pages > 1) {
      for (let i = 1; i <= data.pages; i++) {
        const b = document.createElement("button");
        b.textContent = i;
        b.style.cssText = `
          padding:.3rem .6rem; border-radius:7px; border:1px solid var(--border);
          background:${i === data.page ? "var(--brand)" : "var(--panel-2)"};
          color:${i === data.page ? "#fff" : "var(--text)"}; cursor:pointer; font-size:.8rem;`;
        b.onclick = () => loadActivity(i);
        pag.appendChild(b);
      }
    }
  } catch {
    document.getElementById("activityLoading").style.display = "none";
    document.getElementById("activityEmpty").style.display   = "block";
    document.getElementById("activityEmpty").innerHTML =
      '<svg width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" style="display:block;margin:0 auto .75rem;color:var(--danger);opacity:.7;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>' +
      '<span style="color:var(--danger)">Error al cargar actividad</span>';
  }
}

// ── Toggle password ─────────────────────────────────────
function togglePassword() {
  const input = document.getElementById("fieldPassword");
  const show  = input.type === "password";
  input.type  = show ? "text" : "password";
  document.getElementById("eyeIcon").innerHTML = show
    ? `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
       <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
       <line x1="1" y1="1" x2="23" y2="23"/>`
    : `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
       <circle cx="12" cy="12" r="3"/>`;
}

// ── Helpers ─────────────────────────────────────────────
function getRoleBadge(role) {
  const roleBadgeConfig = {
    [window.ROLES.ROOT]: {
      label: 'Root',
      color: '#ef4444',
      bgOpacity: '15%',
      borderOpacity: '30%'
    },
    [window.ROLES.ADMIN]: {
      label: 'Admin',
      color: '#f59e0b',
      bgOpacity: '18%',
      borderOpacity: '30%'
    },
    [window.ROLES.VENDOR]: {
      label: 'Vendedor',
      color: '#3b82f6',
      bgOpacity: '15%',
      borderOpacity: '30%'
    }
  };

  const config = roleBadgeConfig[role] || roleBadgeConfig[window.ROLES.VENDOR];

  return `<span style="display:inline-flex; align-items:center; gap:.3rem; padding:.2rem .6rem;
                      border-radius:99px; font-size:.75rem; font-weight:600;
                      background:color-mix(in srgb,${config.color} ${config.bgOpacity},transparent);
                      color:${config.color}; border:1px solid color-mix(in srgb,${config.color} ${config.borderOpacity},transparent);">
           ${config.label}
         </span>`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function formatDate(str) {
  if (!str) return `<span style="color:var(--text-muted)">—</span>`;
  const d = new Date(str);
  if (isNaN(d)) return escHtml(str);
  return d.toLocaleString("es-AR", {
    day:"2-digit", month:"2-digit", year:"numeric",
    hour:"2-digit", minute:"2-digit"
  });
}

function showToast(msg, type = "success") {
  if (type === "success"){
    NotificationManager.success(msg);
  }
  else if (type === "danger"){
    NotificationManager.error(msg);
  }
  else if (type === "warning"){
    NotificationManager.warning(msg);
  }
}

loadUsers();
