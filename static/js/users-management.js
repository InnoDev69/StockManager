// ════════════════════════════════════════════════════
// Users Management Module
// ════════════════════════════════════════════════════

// ── Estado global ───────────────────────────────────────
let currentPage    = 1;
let searchTimer    = null;
let deleteUserId   = null;
let activityUserId = null;
let activityPage   = 1;

// ── Solicitudes de Registro ──────────────────────────
async function loadApplications() {
  try {
    const res = await fetch(`/api/applications?page=1&limit=100`);
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      console.warn('API Error al cargar solicitudes:', res.status, errorData);
      return;
    }
    const data = await res.json();

    const count = data.total;
    document.getElementById('pendingCount').textContent = count;

    const section = document.getElementById('applicationsSection');
    section.style.display = count > 0 ? 'block' : 'none';

    const list = document.getElementById('applicationsList');
    if (!data.data.length) {
      list.innerHTML = '<div style="text-align:center; color:var(--text-muted); padding:1rem;">No hay solicitudes pendientes</div>';
      return;
    }

    list.innerHTML = data.data.map(user => {
      const initial = escHtml(user.username.charAt(0).toUpperCase());
      const hue = [...user.username].reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
      return `
        <div style="display:flex; justify-content:space-between; align-items:center;
                    padding:1rem; border:1px solid var(--border); border-radius:8px; margin-bottom:.75rem;
                    background:linear-gradient(135deg, color-mix(in srgb, var(--brand) 5%, transparent), var(--card));
                    transition:all .2s ease;"
             onmouseover="this.style.boxShadow='var(--shadow-md)'; this.style.transform='translateY(-2px)'"
             onmouseout="this.style.boxShadow=''; this.style.transform=''">
          <div style="display:flex; align-items:center; gap:1rem; flex:1;">
            <div style="width:40px; height:40px; border-radius:50%; flex-shrink:0;
                        background:hsl(${hue},55%,45%); display:flex; align-items:center;
                        justify-content:center; font-weight:700; font-size:.9rem; color:#fff;
                        box-shadow:var(--shadow-md);">${initial}</div>
            <div>
              <p style="margin:0; font-weight:600; font-size:.95rem;">${escHtml(user.username)}</p>
              <p style="margin:.2rem 0 0; font-size:.82rem; color:var(--text-muted);">${escHtml(user.email)}</p>
              <p style="margin:.2rem 0 0; font-size:.75rem; color:var(--text-muted);">
                Solicitado hace ${getTimeAgo(user.created_at)}
              </p>
            </div>
          </div>
          <div style="display:flex; gap:.5rem; flex-shrink:0;">
            <button onclick="openApplicationModal(${user.id}, '${escHtml(user.username)}', '${escHtml(user.email)}', '${user.created_at}')"
                    style="background:var(--brand); border:none; padding:.5rem 1.2rem; border-radius:8px; cursor:pointer; color:#fff; font-weight:600; font-size:.85rem; display:flex; align-items:center; gap:.3rem; transition:all .2s ease; box-shadow:var(--shadow-sm);"
                    onmouseover="this.style.boxShadow='var(--shadow-md)'"
                    onmouseout="this.style.boxShadow='var(--shadow-sm)'">
              <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
              Revisar
            </button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error(err);
  }
}

function getTimeAgo(dateStr) {
  if (!dateStr) return "recientemente";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return "hace unos segundos";
  if (diffMins < 60) return `hace ${diffMins}m`;
  if (diffHours < 24) return `hace ${diffHours}h`;
  if (diffDays < 7) return `hace ${diffDays}d`;
  return date.toLocaleDateString("es-AR");
}

function openApplicationModal(userId, username, email, createdAt) {
  const modalHtml = `
    <div id="appModal" style="position:fixed; top:0; left:0; right:0; bottom:0;
                             background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center;
                             z-index:1000; animation:fadeIn .2s ease;">
      <div style="background:var(--card); border-radius:12px; box-shadow:var(--shadow-lg);
                  width:100%; max-width:400px; animation:slideDown .3s ease; border:1px solid var(--border);">
        <!-- Header -->
        <div style="display:flex; justify-content:space-between; align-items:center;
                    padding:1.25rem; border-bottom:1px solid var(--border); background:var(--panel);">
          <h3 style="margin:0; font-size:1.1rem; font-weight:700; color:var(--text);">Revisar Solicitud</h3>
          <button onclick="document.getElementById('appModal').remove()"
                  style="background:none; border:none; font-size:1.5rem; cursor:pointer; color:var(--text-muted); opacity:.6; transition:opacity .2s ease;"
                  onmouseover="this.style.opacity='.9'"
                  onmouseout="this.style.opacity='.6'">×</button>
        </div>

        <!-- Content -->
        <div style="padding:1.5rem;">
          <!-- User Info -->
          <div style="display:flex; gap:1rem; margin-bottom:1.5rem; padding:1rem; 
                      background:var(--panel-2); border-radius:8px; align-items:center; border:1px solid var(--border);">
            <div style="width:48px; height:48px; border-radius:50%; flex-shrink:0;
                        background:linear-gradient(135deg, hsl(${[...username].reduce((a,c)=>a+c.charCodeAt(0),0)%360},55%,45%), hsl(${[...username].reduce((a,c)=>a+c.charCodeAt(0),0)%360},55%,35%));
                        display:flex; align-items:center; justify-content:center;
                        font-weight:700; font-size:1.1rem; color:#fff; box-shadow:var(--shadow-md);">
              ${username.charAt(0).toUpperCase()}
            </div>
            <div>
              <p style="margin:0; font-weight:700; font-size:.95rem; color:var(--text);">${username}</p>
              <p style="margin:.3rem 0 0; font-size:.82rem; color:var(--text-muted);">${email}</p>
            </div>
          </div>

          <!-- Solicitation Date -->
          <div style="margin-bottom:1.5rem;">
            <label style="display:block; font-size:.75rem; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:.5px; margin-bottom:.5rem;">Fecha de Solicitud</label>
            <div style="padding:.75rem; background:var(--panel-2); border-radius:6px; font-size:.9rem; border:1px solid var(--border); color:var(--text);">
              ${formatDate(createdAt)} (hace ${getTimeAgo(createdAt)})
            </div>
          </div>

          <!-- Role Assignment -->
          <div style="margin-bottom:1.5rem;">
            <label style="display:block; font-size:.75rem; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:.5px; margin-bottom:.5rem;">Rol Asignado</label>
            <div style="display:inline-flex; align-items:center; gap:.4rem; padding:.3rem .8rem;
                        border-radius:6px; background:color-mix(in srgb, var(--brand) 15%, transparent);
                        color:var(--brand); border:1px solid color-mix(in srgb, var(--brand) 30%, transparent);
                        font-weight:600; font-size:.85rem;">
              <span style="width:8px; height:8px; border-radius:50%;
                           background:var(--brand); display:inline-block;"></span>
              Vendedor
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div style="display:flex; gap:.75rem; padding:1.25rem; border-top:1px solid var(--border);
                    background:var(--panel);">
          <button onclick="document.getElementById('appModal').remove()"
                  style="flex:1; padding:.65rem; border:1px solid var(--border); background:var(--panel-2);
                          border-radius:8px; cursor:pointer; font-weight:600; font-size:.9rem;
                          transition:all .2s ease; color:var(--text);"
                  onmouseover="this.style.background='color-mix(in srgb, var(--border) 50%, transparent)'"
                  onmouseout="this.style.background='var(--panel-2)'">
            Cancelar
          </button>
          <button onclick="confirmRejectApplication(${userId})"
                  data-action="reject"
                  style="flex:1; padding:.65rem; border:1px solid var(--danger); background:transparent;
                          border-radius:8px; cursor:pointer; font-weight:600; font-size:.9rem;
                          color:var(--danger); transition:all .2s ease;"
                  onmouseover="this.style.background='color-mix(in srgb, var(--danger) 10%, transparent)'"
                  onmouseout="this.style.background='transparent'">
            Rechazar
          </button>
          <button onclick="confirmApproveApplication(${userId})"
                  data-action="approve"
                  style="flex:1; padding:.65rem; border:none; background:var(--success);
                          border-radius:8px; cursor:pointer; font-weight:600; font-size:.9rem;
                          color:#fff; transition:all .2s ease; box-shadow:var(--shadow-sm);"
                  onmouseover="this.style.boxShadow='var(--shadow-md)'"
                  onmouseout="this.style.boxShadow='var(--shadow-sm)'">
            Aprobar
          </button>
        </div>
      </div>
    </div>
  `;

  // Remove existing modal if any
  const existing = document.getElementById('appModal');
  if (existing) existing.remove();

  // Create and insert modal
  const wrapper = document.createElement('div');
  wrapper.innerHTML = modalHtml;
  document.body.appendChild(wrapper.firstElementChild);

  // Close on overlay click
  document.getElementById('appModal').addEventListener('click', (e) => {
    if (e.target.id === 'appModal') e.target.remove();
  });
}

async function confirmApproveApplication(userId) {
  const modal = document.getElementById('appModal');
  const btn = modal.querySelector('button[data-action="approve"]');
  const origText = btn.textContent;
  
  btn.disabled = true;
  btn.style.opacity = '0.6';
  btn.innerHTML = '<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="margin-right:.5rem; display:inline; vertical-align:middle; animation: spin .7s linear infinite;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>Aprobando...';

  try {
    const res = await fetch(`/api/applications/${userId}/approve`, { method: 'POST' });
    if (res.ok) {
      modal.style.animation = 'fadeOut .2s ease forwards';
      setTimeout(() => {
        modal.remove();
        showToast('Solicitud aprobada correctamente', 'success');
        loadApplications();
        loadUsers(currentPage);
      }, 200);
    } else {
      const data = await res.json();
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.innerHTML = origText;
      showToast(data.error || 'Error al aprobar', 'danger');
    }
  } catch {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.innerHTML = origText;
    showToast('Error de conexión', 'danger');
  }
}

function showConfirmModal(title, message, confirmFn) {
  const confirmHtml = `
    <div id="confirmModal" style="position:fixed; top:0; left:0; right:0; bottom:0;
                                  background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center;
                                  z-index:1002; animation:fadeIn .2s ease;">
      <div style="background:var(--card); border-radius:12px; box-shadow:var(--shadow-lg);
                  width:100%; max-width:380px; animation:slideDown .3s ease; border:1px solid var(--border);">
        <!-- Header -->
        <div style="display:flex; justify-content:space-between; align-items:center;
                    padding:1.25rem; border-bottom:1px solid var(--border); background:var(--panel);">
          <h3 style="margin:0; font-size:1.1rem; font-weight:700; color:var(--text);">${title}</h3>
          <button onclick="document.getElementById('confirmModal').remove()"
                  style="background:none; border:none; font-size:1.5rem; cursor:pointer; color:var(--text-muted); opacity:.6; transition:opacity .2s ease;"
                  onmouseover="this.style.opacity='.9'"
                  onmouseout="this.style.opacity='.6'">×</button>
        </div>

        <!-- Message -->
        <div style="padding:1.5rem; color:var(--text); font-size:.95rem; line-height:1.6;">
          ${message}
        </div>

        <!-- Footer -->
        <div style="display:flex; gap:.75rem; padding:1.25rem; border-top:1px solid var(--border);
                    background:var(--panel);">
          <button onclick="document.getElementById('confirmModal').remove()"
                  style="flex:1; padding:.65rem; border:1px solid var(--border); background:var(--panel-2);
                          border-radius:8px; cursor:pointer; font-weight:600; font-size:.9rem;
                          transition:all .2s ease; color:var(--text);"
                  onmouseover="this.style.background='color-mix(in srgb, var(--border) 50%, transparent)'"
                  onmouseout="this.style.background='var(--panel-2)'">
            Cancelar
          </button>
          <button id="confirmBtn"
                  style="flex:1; padding:.65rem; border:none; background:var(--danger);
                          border-radius:8px; cursor:pointer; font-weight:600; font-size:.9rem;
                          color:#fff; transition:all .2s ease; box-shadow:var(--shadow-sm);"
                  onmouseover="this.style.boxShadow='var(--shadow-md)'"
                  onmouseout="this.style.boxShadow='var(--shadow-sm)'">
            Confirmar
          </button>
        </div>
      </div>
    </div>
  `;

  // Remove existing confirm modal if any
  const existing = document.getElementById('confirmModal');
  if (existing) existing.remove();

  // Create and insert modal
  const wrapper = document.createElement('div');
  wrapper.innerHTML = confirmHtml;
  document.body.appendChild(wrapper.firstElementChild);

  // Attach confirm handler
  document.getElementById('confirmBtn').addEventListener('click', () => {
    document.getElementById('confirmModal').remove();
    confirmFn();
  });

  // Close on overlay click
  document.getElementById('confirmModal').addEventListener('click', (e) => {
    if (e.target.id === 'confirmModal') e.target.remove();
  });
}

function proceedRejectApplication(userId) {
  const modal = document.getElementById('appModal');
  const btn = modal.querySelector('button[data-action="reject"]');
  const origText = btn.textContent;
  
  btn.disabled = true;
  btn.style.opacity = '0.6';
  btn.innerHTML = '<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="margin-right:.5rem; display:inline; vertical-align:middle; animation: spin .7s linear infinite;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>Rechazando...';

  fetch(`/api/applications/${userId}/reject`, { method: 'POST' })
    .then(res => {
      if (res.ok) {
        modal.style.animation = 'fadeOut .2s ease forwards';
        setTimeout(() => {
          modal.remove();
          showToast('✓ Solicitud rechazada correctamente', 'warning');
          loadApplications();
          loadUsers(currentPage);
        }, 200);
      } else {
        return res.json().then(data => {
          btn.disabled = false;
          btn.style.opacity = '1';
          btn.innerHTML = origText;
          showToast(data.error || 'Error al rechazar', 'danger');
        });
      }
    })
    .catch(() => {
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.innerHTML = origText;
      showToast('Error de conexión', 'danger');
    });
}

function confirmRejectApplication(userId) {
  showConfirmModal(
    '¿Rechazar solicitud?',
    '¿Estás seguro de que deseas rechazar esta solicitud de registro? Esta acción no se puede deshacer.',
    () => proceedRejectApplication(userId)
  );
}

// Agregar keyframes para animaciones
const style = document.createElement('style');
style.textContent = `
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes fadeOut {
    from { opacity: 1; }
    to { opacity: 0; }
  }
  @keyframes slideDown {
    from { opacity: 0; transform: translateY(-20px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;
document.head.appendChild(style);

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
                        box-shadow:var(--shadow-sm);">${initial}</div>
            <span style="font-weight:600; color:var(--text);">${escHtml(u.username)}</span>
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
  const limit = 10;
  const offset = (page - 1) * limit;
  
  try {
    const res = await fetch(`/api/user/${activityUserId}?limit=${limit}&offset=${offset}`);
    if (!res.ok) throw new Error();
    const data = await res.json();

    document.getElementById("activityLoading").style.display = "none";

    // La API de auditoría devuelve: { records: [...], total: N }
    const records = Array.isArray(data) ? data : (data.records || data.changes || data.data || []);
    
    if (!records.length) {
      document.getElementById("activityEmpty").style.display = "block";
      document.getElementById("activityPageInfo").textContent = "Sin registros de actividad";
      return;
    }

    document.getElementById("activityTable").style.display = "table";
    document.getElementById("activityTableBody").innerHTML = records.map(r => `
      <tr style="border-bottom:1px solid var(--border);"
          onmouseover="this.style.background='var(--panel-2)'"
          onmouseout="this.style.background=''">
        <td style="padding:.65rem 1rem; color:var(--text-muted); font-size:.82rem;">
          ${r.id || r.action || '—'}</td>
        <td style="padding:.65rem .75rem; font-size:.875rem;">${formatDate(r.timestamp || r.date || r.created_at)}</td>
        <td style="padding:.65rem .75rem;">
          <span style="padding:.2rem .55rem; border-radius:6px; font-size:.78rem;
                       background:var(--panel-2); border:1px solid var(--border); color:var(--text);">
            ${escHtml(r.action || r.type || '—')}
          </span>
        </td>
        <td style="padding:.65rem .75rem; text-align:center;">
          <span style="padding:.2rem .55rem; border-radius:6px; font-size:.78rem;
                       background:color-mix(in srgb,var(--brand) 12%,transparent);
                       color:var(--brand); border:1px solid color-mix(in srgb,var(--brand) 25%,transparent);">
            ${r.entity_type || r.details || '—'}
          </span>
        </td>
        <td style="padding:.65rem 1rem; text-align:right; font-weight:600; color:var(--text);">
          ${escHtml(r.description || r.status || '—')}</td>
      </tr>`).join("");

    // Renderizar paginación si aplica
    const totalRecords = data.total || records.length;
    const totalPages = Math.ceil(totalRecords / limit) || 1;
    const pageInfo = totalRecords ? 
      `Página ${page} · ${totalRecords} registro${totalRecords !== 1 ? "s" : ""}` :
      `Página ${page}`;
    
    document.getElementById("activityPageInfo").textContent = pageInfo;

    const pag = document.getElementById("activityPagination");
    pag.innerHTML = "";
    if (totalPages > 1) {
      for (let i = 1; i <= totalPages; i++) {
        const b = document.createElement("button");
        b.textContent = i;
        b.style.cssText = `
          padding:.3rem .6rem; border-radius:7px; border:1px solid var(--border);
          background:${i === page ? "var(--brand)" : "var(--panel-2)"};
          color:${i === page ? "#fff" : "var(--text)"}; cursor:pointer; font-size:.8rem;`;
        b.onclick = () => loadActivity(i);
        pag.appendChild(b);
      }
    }
  } catch (err) {
    console.error('Error cargando actividad:', err);
    document.getElementById("activityLoading").style.display = "none";
    document.getElementById("activityEmpty").style.display = "block";
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
  const typeConfig = {
    success: {
      icon: `<svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`,
      color: 'var(--success)',
      bgColor: 'color-mix(in srgb, var(--success) 12%, transparent)',
      borderColor: 'color-mix(in srgb, var(--success) 30%, transparent)'
    },
    danger: {
      icon: `<svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
      color: 'var(--danger)',
      bgColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
      borderColor: 'color-mix(in srgb, var(--danger) 30%, transparent)'
    },
    warning: {
      icon: `<svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3.05h16.94a2 2 0 0 0 1.71-3.05l-8.47-14.14a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
      color: 'var(--warning)',
      bgColor: 'color-mix(in srgb, var(--warning) 12%, transparent)',
      borderColor: 'color-mix(in srgb, var(--warning) 30%, transparent)'
    }
  };

  const config = typeConfig[type] || typeConfig.success;

  const modalHtml = `
    <div id="toastModal" style="position:fixed; top:0; left:0; right:0; bottom:0;
                              background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center;
                              z-index:1001; animation:fadeIn .2s ease;">
      <div style="background:var(--card); border-radius:12px; box-shadow:var(--shadow-lg);
                  width:100%; max-width:420px; animation:slideDown .3s ease; border:1px solid var(--border);
                  padding:0;">
        <!-- Header with color -->
        <div style="display:flex; align-items:center; gap:1rem; padding:1.5rem;
                    background:${config.bgColor}; border-bottom:2px solid ${config.borderColor};
                    border-radius:12px 12px 0 0;">
          <div style="width:48px; height:48px; border-radius:50%; flex-shrink:0;
                      background:${config.bgColor}; border:2px solid ${config.color};
                      display:flex; align-items:center; justify-content:center;
                      color:${config.color};">
            ${config.icon}
          </div>
          <div style="flex:1;">
            <h3 style="margin:0; font-size:1rem; font-weight:700; color:var(--text);">
              ${type === 'success' ? 'Éxito' : type === 'danger' ? 'Error' : 'Atención'}
            </h3>
          </div>
        </div>

        <!-- Message -->
        <div style="padding:1.5rem; color:var(--text); font-size:.95rem; line-height:1.5;">
          ${msg}
        </div>

        <!-- Footer -->
        <div style="display:flex; gap:.75rem; padding:1rem 1.5rem; border-top:1px solid var(--border);
                    background:var(--panel); border-radius:0 0 12px 12px;">
          <button onclick="document.getElementById('toastModal').remove()"
                  style="flex:1; padding:.65rem; border:none; background:${config.color};
                          border-radius:8px; cursor:pointer; font-weight:600; font-size:.9rem;
                          color:#fff; transition:all .2s ease; box-shadow:var(--shadow-sm);"
                  onmouseover="this.style.boxShadow='var(--shadow-md)'"
                  onmouseout="this.style.boxShadow='var(--shadow-sm)'">
            Aceptar
          </button>
        </div>
      </div>
    </div>
  `;

  // Remove existing modal if any
  const existing = document.getElementById('toastModal');
  if (existing) existing.remove();

  // Create and insert modal
  const wrapper = document.createElement('div');
  wrapper.innerHTML = modalHtml;
  document.body.appendChild(wrapper.firstElementChild);

  // Close on overlay click
  document.getElementById('toastModal').addEventListener('click', (e) => {
    if (e.target.id === 'toastModal') e.target.remove();
  });
}

// Cargar solicitudes si el usuario es ADMIN o ROOT
// Nota: La API validará los permisos, así que es seguro llamar siempre
loadApplications();

loadUsers();
