// ════════════════════════════════════════════════════
// Settings Module
// ════════════════════════════════════════════════════

(function(){
  'use strict';

  // Configuración
  const DARK_KEY = 'pref_dark';
  const LOW_STOCK_KEY = 'pref_low_stock';

  // Elementos DOM
  const darkSwitch = document.getElementById('prefDark');
  const lowInput = document.getElementById('prefLowStock');
  const savePrefsBtn = document.getElementById('savePrefs');
  const passwordForm = document.getElementById('passwordForm');
  const newPass = document.getElementById('newPass');
  const confirmPass = document.getElementById('confirmPass');
  const passMatchMsg = document.getElementById('passMatchMsg');
  const profileForm = document.getElementById('profileForm');
  const profileEmail = document.getElementById('profileEmail');

  // ===== PREFERENCIAS =====
  // Cargar preferencias guardadas
  function loadPreferences() {
    const isDark = localStorage.getItem(DARK_KEY) === '1';
    const lowStock = localStorage.getItem(LOW_STOCK_KEY) || '5';
    
    darkSwitch.checked = isDark;
    lowInput.value = lowStock;
    applyTheme();
  }

  // Aplicar tema
  function applyTheme() {
    if (darkSwitch.checked) {
      document.documentElement.classList.add('dark-theme');
    } else {
      document.documentElement.classList.remove('dark-theme');
    }
  }

  // Guardar preferencias
  function savePreferences() {
    const lowStock = parseInt(lowInput.value);
    
    // Validación
    if (isNaN(lowStock) || lowStock < 0) {
      showToast('El umbral debe ser un número válido mayor o igual a 0', 'error');
      return;
    }
    
    localStorage.setItem(DARK_KEY, darkSwitch.checked ? '1' : '0');
    localStorage.setItem(LOW_STOCK_KEY, lowStock.toString());
    
    showFeedback(savePrefsBtn, 'Preferencias guardadas', 'success');
  }

  // ===== VALIDACIÓN DE CONTRASEÑA =====
  function validatePasswordMatch() {
    const newPassword = newPass.value;
    const confirmPassword = confirmPass.value;
    
    if (confirmPassword.length === 0) {
      passMatchMsg.style.display = 'none';
      return true;
    }
    
    passMatchMsg.style.display = 'block';
    
    if (newPassword === confirmPassword) {
      passMatchMsg.textContent = '✓ Las contraseñas coinciden';
      passMatchMsg.style.color = 'var(--success)';
      return true;
    } else {
      passMatchMsg.textContent = '✗ Las contraseñas no coinciden';
      passMatchMsg.style.color = 'var(--danger)';
      return false;
    }
  }

  // ===== VALIDACIÓN DE EMAIL =====
  function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  }

  // ===== UI FEEDBACK =====
  function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toastMsg');
    
    // Configurar color del borde según tipo
    const borderColors = {
      success: 'var(--success)',
      error: 'var(--danger)',
      warning: 'var(--warning)',
      info: 'var(--brand)'
    };
    
    toast.style.borderLeftColor = borderColors[type] || borderColors.success;
    toastMsg.textContent = message;
    toast.classList.remove('hidden');
    
    setTimeout(() => {
      toast.classList.add('hidden');
    }, 3000);
  }

  function showFeedback(button, message, type = 'success') {
    const originalHTML = button.innerHTML;
    const originalDisabled = button.disabled;
    
    button.disabled = true;
    
    const icons = {
      success: '✓',
      error: '✗',
      warning: '⚠'
    };
    
    button.innerHTML = `<span>${icons[type] || icons.success} ${message}</span>`;
    
    setTimeout(() => {
      button.innerHTML = originalHTML;
      button.disabled = originalDisabled;
    }, 2000);
    
    showToast(message, type);
  }

  // ===== API CALLS =====
  async function saveProfile() {
    const email = profileEmail.value.trim();
    
    if (!validateEmail(email)) {
      showToast('Por favor, ingresa un email válido', 'error');
      profileEmail.focus();
      return false;
    }
    
    const btn = profileForm.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Guardando...';
    
    try {
      const res = await fetch('/api/settings/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      
      const data = await res.json();
      if (res.ok) {
        showToast(data.message, 'success');
      } else {
        showToast(data.error || 'Error al guardar', 'error');
      }
    } catch (e) {
      showToast('Error de conexión', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Guardar cambios';
    }
  }

  async function savePassword() {
    if (!validatePasswordMatch()) {
      showToast('Las contraseñas no coinciden', 'error');
      confirmPass.focus();
      return false;
    }
    
    if (newPass.value.length < 6) {
      showToast('La contraseña debe tener al menos 6 caracteres', 'error');
      newPass.focus();
      return false;
    }
    
    const btn = passwordForm.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Actualizando...';
    
    try {
      const res = await fetch('/api/settings/password', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: document.getElementById('currentPass').value,
          new_password: newPass.value,
          confirm_password: confirmPass.value
        })
      });
      
      const data = await res.json();
      if (res.ok) {
        showToast(data.message, 'success');
        passwordForm.reset();
        passMatchMsg.style.display = 'none';
      } else {
        showToast(data.error || 'Error al actualizar', 'error');
      }
    } catch (e) {
      showToast('Error de conexión', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Actualizar contraseña';
    }
  }

  // ===== EVENT LISTENERS =====
  
  // Tema en tiempo real
  darkSwitch.addEventListener('change', applyTheme);
  
  // Guardar preferencias
  savePrefsBtn.addEventListener('click', savePreferences);
  
  // Validación de contraseñas en tiempo real
  newPass.addEventListener('input', validatePasswordMatch);
  confirmPass.addEventListener('input', validatePasswordMatch);
  
  // Validación del formulario de contraseña antes de enviar
  passwordForm.addEventListener('submit', function(e) {
    e.preventDefault();
    savePassword();
  });
  
  // Validación del formulario de perfil
  profileForm.addEventListener('submit', function(e) {
    e.preventDefault();
    saveProfile();
  });
  
  // Validación de umbral de stock
  lowInput.addEventListener('input', function() {
    const value = parseInt(this.value);
    if (isNaN(value) || value < 0) {
      this.style.borderColor = 'var(--danger)';
    } else {
      this.style.borderColor = '';
    }
  });

  // ===== INICIALIZACIÓN =====
  loadPreferences();

})();
