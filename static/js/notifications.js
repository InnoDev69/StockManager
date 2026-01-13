/**
 * Sistema de Notificaciones Centralizado para Stock Manager
 * Tipos: toast, alert (inline), modal/popup
 */

const NotificationManager = (function() {
  // Configuración por defecto
  const defaults = {
    toast: {
      duration: 4000,
      position: 'bottom-right', // bottom-right, bottom-left, top-right, top-left, top-center, bottom-center
      maxVisible: 5
    },
    modal: {
      closeOnOverlay: true,
      closeOnEscape: true
    }
  };

  // Contenedor de toasts
  let toastContainer = null;
  let activeToasts = [];

  // Inicializar contenedores
  function init() {
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.className = 'notification-toast-container';
      toastContainer.setAttribute('data-position', defaults.toast.position);
      document.body.appendChild(toastContainer);
    }
    
    // Escuchar tecla Escape para modales
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && defaults.modal.closeOnEscape) {
        closeAllModals();
      }
    });
  }

  // ==================== TOASTS ====================
  
  /**
   * Mostrar notificación toast
   * @param {string} message - Mensaje a mostrar
   * @param {Object} options - Opciones de configuración
   * @param {string} options.type - Tipo: 'success', 'error', 'warning', 'info'
   * @param {number} options.duration - Duración en ms (0 = permanente)
   * @param {string} options.title - Título opcional
   * @param {boolean} options.dismissible - Si se puede cerrar manualmente
   * @param {string} options.icon - Icono personalizado (emoji o SVG)
   * @param {Function} options.onClick - Callback al hacer click
   * @param {Array} options.actions - Botones de acción [{label, onClick, style}]
   */
  function toast(message, options = {}) {
    init();
    
    const config = {
      type: options.type || 'info',
      duration: options.duration !== undefined ? options.duration : defaults.toast.duration,
      title: options.title || null,
      dismissible: options.dismissible !== false,
      icon: options.icon || null,
      onClick: options.onClick || null,
      actions: options.actions || []
    };

    // Limitar número de toasts visibles
    while (activeToasts.length >= defaults.toast.maxVisible) {
      dismissToast(activeToasts[0]);
    }

    const toastEl = document.createElement('div');
    toastEl.className = `notification-toast notification-toast--${config.type}`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', config.type === 'error' ? 'assertive' : 'polite');

    // Icono por defecto según tipo
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };

    const icon = config.icon || icons[config.type];

    toastEl.innerHTML = `
      <div class="notification-toast__icon">${icon}</div>
      <div class="notification-toast__content">
        ${config.title ? `<div class="notification-toast__title">${config.title}</div>` : ''}
        <div class="notification-toast__message">${message}</div>
        ${config.actions.length ? `
          <div class="notification-toast__actions">
            ${config.actions.map((action, i) => `
              <button class="notification-toast__action ${action.style || ''}" data-action-index="${i}">
                ${action.label}
              </button>
            `).join('')}
          </div>
        ` : ''}
      </div>
      ${config.dismissible ? '<button class="notification-toast__close" aria-label="Cerrar">✕</button>' : ''}
    `;

    // Event listeners
    if (config.dismissible) {
      toastEl.querySelector('.notification-toast__close').addEventListener('click', (e) => {
        e.stopPropagation();
        dismissToast(toastEl);
      });
    }

    if (config.onClick) {
      toastEl.style.cursor = 'pointer';
      toastEl.addEventListener('click', config.onClick);
    }

    config.actions.forEach((action, index) => {
      const btn = toastEl.querySelector(`[data-action-index="${index}"]`);
      if (btn && action.onClick) {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          action.onClick();
          if (action.dismissOnClick !== false) {
            dismissToast(toastEl);
          }
        });
      }
    });

    toastContainer.appendChild(toastEl);
    activeToasts.push(toastEl);

    // Animar entrada
    requestAnimationFrame(() => {
      toastEl.classList.add('notification-toast--visible');
    });

    // Auto-dismiss
    if (config.duration > 0) {
      toastEl._timeout = setTimeout(() => dismissToast(toastEl), config.duration);
    }

    return toastEl;
  }

  function dismissToast(toastEl) {
    if (!toastEl || !toastEl.parentNode) return;
    
    clearTimeout(toastEl._timeout);
    toastEl.classList.remove('notification-toast--visible');
    toastEl.classList.add('notification-toast--leaving');
    
    setTimeout(() => {
      toastEl.remove();
      activeToasts = activeToasts.filter(t => t !== toastEl);
    }, 300);
  }

  // Atajos para tipos de toast
  const success = (msg, opts = {}) => toast(msg, { ...opts, type: 'success' });
  const error = (msg, opts = {}) => toast(msg, { ...opts, type: 'error' });
  const warning = (msg, opts = {}) => toast(msg, { ...opts, type: 'warning' });
  const info = (msg, opts = {}) => toast(msg, { ...opts, type: 'info' });

  // ==================== MODALES / POPUP ====================

  /**
   * Mostrar modal/popup de notificación
   * @param {Object} options - Opciones de configuración
   */
  function modal(options = {}) {
    const config = {
      title: options.title || '',
      message: options.message || '',
      type: options.type || 'info', // success, error, warning, info, confirm
      icon: options.icon || null,
      confirmText: options.confirmText || 'Aceptar',
      cancelText: options.cancelText || 'Cancelar',
      showCancel: options.showCancel !== undefined ? options.showCancel : (options.type === 'confirm'),
      onConfirm: options.onConfirm || null,
      onCancel: options.onCancel || null,
      content: options.content || null, // HTML personalizado
      size: options.size || 'small' // small, medium, large
    };

    const icons = {
      success: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></svg>',
      error: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
      warning: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4M12 17h.01"/><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>',
      info: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
      confirm: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>'
    };

    const modalEl = document.createElement('div');
    modalEl.className = `notification-modal notification-modal--${config.type} notification-modal--${config.size}`;
    modalEl.setAttribute('role', 'dialog');
    modalEl.setAttribute('aria-modal', 'true');
    modalEl.setAttribute('aria-labelledby', 'notification-modal-title');

    modalEl.innerHTML = `
      <div class="notification-modal__overlay"></div>
      <div class="notification-modal__container">
        <div class="notification-modal__icon notification-modal__icon--${config.type}">
          ${config.icon || icons[config.type]}
        </div>
        ${config.title ? `<h3 class="notification-modal__title" id="notification-modal-title">${config.title}</h3>` : ''}
        ${config.message ? `<p class="notification-modal__message">${config.message}</p>` : ''}
        ${config.content ? `<div class="notification-modal__content">${config.content}</div>` : ''}
        <div class="notification-modal__actions">
          ${config.showCancel ? `
            <button class="notification-modal__btn notification-modal__btn--cancel">${config.cancelText}</button>
          ` : ''}
          <button class="notification-modal__btn notification-modal__btn--confirm notification-modal__btn--${config.type}">${config.confirmText}</button>
        </div>
      </div>
    `;

    // Event listeners
    const overlay = modalEl.querySelector('.notification-modal__overlay');
    const confirmBtn = modalEl.querySelector('.notification-modal__btn--confirm');
    const cancelBtn = modalEl.querySelector('.notification-modal__btn--cancel');

    const closeModal = (confirmed = false) => {
      modalEl.classList.add('notification-modal--leaving');
      setTimeout(() => {
        modalEl.remove();
        document.body.style.overflow = '';
      }, 200);
      
      if (confirmed && config.onConfirm) {
        config.onConfirm();
      } else if (!confirmed && config.onCancel) {
        config.onCancel();
      }
    };

    if (defaults.modal.closeOnOverlay) {
      overlay.addEventListener('click', () => closeModal(false));
    }

    confirmBtn.addEventListener('click', () => closeModal(true));
    
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => closeModal(false));
    }

    // Guardar referencia para cerrar con Escape
    modalEl._close = closeModal;

    document.body.appendChild(modalEl);
    document.body.style.overflow = 'hidden';

    // Animar entrada
    requestAnimationFrame(() => {
      modalEl.classList.add('notification-modal--visible');
    });

    // Focus en el botón de confirmar
    confirmBtn.focus();

    return {
      close: closeModal,
      element: modalEl
    };
  }

  function closeAllModals() {
    document.querySelectorAll('.notification-modal').forEach(m => {
      if (m._close) m._close(false);
    });
  }

  // Atajos para modales
  const alert = (message, title = '') => modal({ message, title, type: 'info' });
  
  const confirm = (message, options = {}) => {
    return new Promise((resolve) => {
      modal({
        ...options,
        message,
        type: 'confirm',
        showCancel: true,
        onConfirm: () => resolve(true),
        onCancel: () => resolve(false)
      });
    });
  };

  const successModal = (message, title = '¡Éxito!') => modal({ message, title, type: 'success' });
  const errorModal = (message, title = 'Error') => modal({ message, title, type: 'error' });
  const warningModal = (message, title = 'Advertencia') => modal({ message, title, type: 'warning' });

  // ==================== ALERTAS INLINE ====================

  /**
   * Crear alerta inline (para insertar en el DOM)
   * @param {string} message - Mensaje
   * @param {Object} options - Opciones
   */
  function createInlineAlert(message, options = {}) {
    const config = {
      type: options.type || 'info',
      dismissible: options.dismissible !== false,
      icon: options.icon || null
    };

    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };

    const alertEl = document.createElement('div');
    alertEl.className = `notification-inline notification-inline--${config.type}`;
    alertEl.setAttribute('role', 'alert');

    alertEl.innerHTML = `
      <span class="notification-inline__icon">${config.icon || icons[config.type]}</span>
      <span class="notification-inline__message">${message}</span>
      ${config.dismissible ? '<button class="notification-inline__close" aria-label="Cerrar">✕</button>' : ''}
    `;

    if (config.dismissible) {
      alertEl.querySelector('.notification-inline__close').addEventListener('click', () => {
        alertEl.classList.add('notification-inline--leaving');
        setTimeout(() => alertEl.remove(), 200);
      });
    }

    return alertEl;
  }

  // ==================== API PÚBLICA ====================

  return {
    // Toasts
    toast,
    success,
    error,
    warning,
    info,
    dismissToast,
    
    // Modales
    modal,
    alert,
    confirm,
    successModal,
    errorModal,
    warningModal,
    closeAllModals,
    
    // Inline alerts
    createInlineAlert,
    
    // Configuración
    configure: (opts) => Object.assign(defaults, opts)
  };
})();

// Alias global para compatibilidad
window.Notify = NotificationManager;

// Reemplazar el showToast existente para retrocompatibilidad
function showToast(message, isError = false) {
  if (isError) {
    NotificationManager.error(message);
  } else {
    NotificationManager.success(message);
  }
}