/**
 * Sistema de Notificaciones Centralizado para Stockly
 * Tipos: toast, alert (inline), modal/popup
 */

const NotificationManager = (function () {

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

  // FIX 3: listener de Escape registrado UNA sola vez, fuera de init()
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && defaults.modal.closeOnEscape) {
      closeAllModals();
    }
  });

  // Inicializar contenedor de toasts
  function init() {
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.className = 'notification-toast-container';
      toastContainer.setAttribute('data-position', defaults.toast.position);
      document.body.appendChild(toastContainer);
    }
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

    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };

    const icon = config.icon || icons[config.type];

    toastEl.innerHTML = `
      <div class="notification-toast__icon"></div>
      <div class="notification-toast__content">
        <div class="notification-toast__title"></div>
        <div class="notification-toast__message"></div>
        <div class="notification-toast__actions"></div>
      </div>
    `;

    //  Agregar icono
    toastEl.querySelector('.notification-toast__icon').textContent = icon;

    //  Agregar título si existe
    const titleEl = toastEl.querySelector('.notification-toast__title');
    if (config.title) {
      titleEl.textContent = config.title;
      titleEl.style.display = 'block';
    } else {
      titleEl.style.display = 'none';
    }

    toastEl.querySelector('.notification-toast__message').textContent = message;

    const actionsContainer = toastEl.querySelector('.notification-toast__actions');
    if (config.actions.length) {
      config.actions.forEach((action, index) => {
        const btn = document.createElement('button');
        btn.className = `notification-toast__action ${action.style || ''}`;
        btn.textContent = action.label;
        btn.dataset.actionIndex = index;
        actionsContainer.appendChild(btn);
      });
    }

    if (config.dismissible) {
      const closeBtn = document.createElement('button');
      closeBtn.className = 'notification-toast__close';
      closeBtn.setAttribute('aria-label', 'Cerrar');
      closeBtn.textContent = '✕';
      toastEl.appendChild(closeBtn);
    }

    // Event listeners para cerrar
    const closeBtn = toastEl.querySelector('.notification-toast__close');
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dismissToast(toastEl);
      });
    }

    if (config.onClick) {
      toastEl.style.cursor = 'pointer';
      toastEl.addEventListener('click', config.onClick);
    }

    // Event listeners para acciones
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
    // FIX 1 + 2: guard contra elemento inválido y contra doble ejecución
    if (!toastEl || toastEl._dismissing) return;
    toastEl._dismissing = true;

    // FIX 4: limpiar el array SINCRÓNICAMENTE para que el while loop
    // de maxVisible no itere infinito sobre el mismo elemento bloqueado
    activeToasts = activeToasts.filter(t => t !== toastEl);

    clearTimeout(toastEl._timeout);
    toastEl.classList.remove('notification-toast--visible');
    toastEl.classList.add('notification-toast--leaving');

    // Solo la animación del DOM va async
    setTimeout(() => {
      if (toastEl.parentNode) toastEl.remove();
    }, 300);
  }

  // Atajos para tipos de toast
  const success = (msg, opts = {}) => toast(msg, { ...opts, type: 'success' });
  const error   = (msg, opts = {}) => toast(msg, { ...opts, type: 'error' });
  const warning = (msg, opts = {}) => toast(msg, { ...opts, type: 'warning' });
  const info    = (msg, opts = {}) => toast(msg, { ...opts, type: 'info' });

  // ==================== MODALES / POPUP ====================

  /**
   * Mostrar modal/popup de notificación
   * @param {Object} options - Opciones de configuración
   */
  function modal(options = {}) {
    const config = {
      title:       options.title || '',
      message:     options.message || '',
      type:        options.type || 'info',
      icon:        options.icon || null,
      confirmText: options.confirmText || 'Aceptar',
      cancelText:  options.cancelText || 'Cancelar',
      showCancel:  options.showCancel !== undefined ? options.showCancel : (options.type === 'confirm'),
      onConfirm:   options.onConfirm || null,
      onCancel:    options.onCancel || null,
      content:     options.content || null,
      size:        options.size || 'small'
    };

    const icons = {
      success: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></svg>',
      error:   '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
      warning: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4M12 17h.01"/><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>',
      info:    '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
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
        <div class="notification-modal__icon notification-modal__icon--${config.type}"></div>
        <h3 class="notification-modal__title" id="notification-modal-title"></h3>
        <p class="notification-modal__message"></p>
        <div class="notification-modal__content"></div>
        <div class="notification-modal__actions">
          <button class="notification-modal__btn notification-modal__btn--cancel"></button>
          <button class="notification-modal__btn notification-modal__btn--confirm notification-modal__btn--${config.type}"></button>
        </div>
      </div>
    `;

    // Llenar datos de forma segura
    const iconEl = modalEl.querySelector('.notification-modal__icon');
    iconEl.innerHTML = config.icon || icons[config.type]; // Icons son confiables

    const titleEl = modalEl.querySelector('.notification-modal__title');
    titleEl.textContent = config.title;
    titleEl.style.display = config.title ? 'block' : 'none';

    const messageEl = modalEl.querySelector('.notification-modal__message');
    messageEl.textContent = config.message;
    messageEl.style.display = config.message ? 'block' : 'none';

    const contentEl = modalEl.querySelector('.notification-modal__content');
    if (config.content) {
      contentEl.innerHTML = config.content;
      contentEl.style.display = 'block';
    } else {
      contentEl.style.display = 'none';
    }

    const overlay    = modalEl.querySelector('.notification-modal__overlay');
    const confirmBtn = modalEl.querySelector('.notification-modal__btn--confirm');
    const cancelBtn  = modalEl.querySelector('.notification-modal__btn--cancel');

    confirmBtn.textContent = config.confirmText;
    cancelBtn.textContent = config.cancelText;
    if (!config.showCancel) {
      cancelBtn.style.display = 'none';
    }

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

    modalEl._close = closeModal;

    document.body.appendChild(modalEl);
    document.body.style.overflow = 'hidden';

    requestAnimationFrame(() => {
      modalEl.classList.add('notification-modal--visible');
    });

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
  const alert        = (message, title = '')          => modal({ message, title, type: 'info' });
  const successModal = (message, title = '¡Éxito!')   => modal({ message, title, type: 'success' });
  const errorModal   = (message, title = 'Error')     => modal({ message, title, type: 'error' });
  const warningModal = (message, title = 'Advertencia') => modal({ message, title, type: 'warning' });

  const confirm = (message, options = {}) => {
    return new Promise((resolve) => {
      modal({
        ...options,
        message,
        type: 'confirm',
        showCancel: true,
        onConfirm: () => resolve(true),
        onCancel:  () => resolve(false)
      });
    });
  };

  // ==================== ALERTAS INLINE ====================

  /**
   * Crear alerta inline (para insertar en el DOM)
   * @param {string} message - Mensaje
   * @param {Object} options - Opciones
   */
  function createInlineAlert(message, options = {}) {
    const config = {
      type:        options.type || 'info',
      dismissible: options.dismissible !== false,
      icon:        options.icon || null
    };

    const icons = {
      success: '✓',
      error:   '✕',
      warning: '⚠',
      info:    'ℹ'
    };

    const alertEl = document.createElement('div');
    alertEl.className = `notification-inline notification-inline--${config.type}`;
    alertEl.setAttribute('role', 'alert');

    alertEl.innerHTML = `
      <span class="notification-inline__icon"></span>
      <span class="notification-inline__message"></span>
    `;

    alertEl.querySelector('.notification-inline__icon').textContent = config.icon || icons[config.type];
    alertEl.querySelector('.notification-inline__message').textContent = message;

    if (config.dismissible) {
      const closeBtn = document.createElement('button');
      closeBtn.className = 'notification-inline__close';
      closeBtn.setAttribute('aria-label', 'Cerrar');
      closeBtn.textContent = '✕';
      closeBtn.addEventListener('click', () => {
        alertEl.classList.add('notification-inline--leaving');
        setTimeout(() => alertEl.remove(), 200);
      });
      alertEl.appendChild(closeBtn);
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

window.Notify = NotificationManager;

// Retrocompatibilidad con showToast existente
function showToast(message, isError = false) {
  if (isError) {
    NotificationManager.error(message);
  } else {
    NotificationManager.success(message);
  }
}