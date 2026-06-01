/**
 * ============================================================
 * UTILIDADES COMPARTIDAS - Stockly
 * Funciones comunes usadas en múltiples módulos
 * ============================================================
 */

/**
 * Escapa caracteres HTML para prevenir XSS
 * @param {string} text - Texto a escapar
 * @returns {string} Texto escapado
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Crea una función con debounce (retraso de ejecución)
 * @param {Function} func - Función a ejecutar
 * @param {number} wait - Milisegundos de espera
 * @returns {Function} Función debounceada
 */
function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

/**
 * Muestra notificación toast usando NotificationManager
 * Fallback a console si NotificationManager no disponible
 * @param {string} message - Mensaje a mostrar
 * @param {string|boolean} type - Tipo: 'success', 'error', 'warning', 'info'
 */
function showToast(message, type = 'success') {
  // Si type es boolean (legacy), convertir a string
  if (typeof type === 'boolean') {
    type = type ? 'error' : 'success';
  }

  // Preferir NotificationManager si está disponible
  if (typeof NotificationManager !== 'undefined') {
    if (type === 'error' || type === 'danger') {
      NotificationManager.error(message);
    } else if (type === 'warning') {
      NotificationManager.warning(message);
    } else if (type === 'info') {
      NotificationManager.info(message);
    } else {
      NotificationManager.success(message);
    }
  } else {
    // Fallback para páginas sin NotificationManager
    console.log(`[${type.toUpperCase()}] ${message}`);
  }
}

/**
 * Formatea una fecha ISO a formato local
 * @param {string} dateStr - Fecha en formato ISO
 * @returns {string} Fecha formateada o '—' si inválida
 */
function formatDate(dateStr) {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  if (isNaN(date)) return dateStr;
  return date.toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * Alias para escapeHtml (compatibilidad con código existente)
 * @param {string} str - Texto a escapar
 * @returns {string} Texto escapado
 */
function escHtml(str) {
  return escapeHtml(str);
}

/**
 * Valida formato de email
 * @param {string} email - Email a validar
 * @returns {boolean} True si es válido
 */
function validateEmail(email) {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return regex.test(email);
}

/**
 * Copia texto al portapapeles
 * @param {string} text - Texto a copiar
 * @returns {Promise<boolean>} True si tuvo éxito
 */
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    console.error('Error copiando al portapapeles:', err);
    return false;
  }
}

/**
 * Confirma una acción destructiva
 * @param {string} message - Mensaje de confirmación
 * @returns {boolean} True si confirmó
 */
function confirmAction(message = '¿Estás seguro?') {
  return confirm(message);
}

/**
 * Formatea número a formato de moneda
 * @param {number} value - Valor numérico
 * @param {string} currency - Código de moneda (default: 'ARS')
 * @returns {string} Formato moneda
 */
function formatCurrency(value, currency = 'ARS') {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: currency
  }).format(value);
}

// Exportar para módulos (si se usa con import)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    escapeHtml,
    escHtml,
    debounce,
    showToast,
    formatDate,
    validateEmail,
    copyToClipboard,
    confirmAction,
    formatCurrency
  };
}

function showToastModal(msg, type = "success") {
  /*
    * Tipos de toast: 
    - success: verde, check
    - danger: rojo, error
    - warning: amarillo, advertencia

    El modal se cierra al hacer click en "Aceptar" o al hacer click fuera del contenido. 
   */
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

  const existing = document.getElementById('toastModal');
  if (existing) existing.remove();

  const wrapper = document.createElement('div');
  wrapper.innerHTML = modalHtml;
  document.body.appendChild(wrapper.firstElementChild);

  document.getElementById('toastModal').addEventListener('click', (e) => {
    if (e.target.id === 'toastModal') e.target.remove();
  });
}