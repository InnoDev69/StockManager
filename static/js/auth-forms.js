// ════════════════════════════════════════════════════
// Auth Forms Module - Login/Register con AJAX
// ════════════════════════════════════════════════════

function toggleForms() {
  document.getElementById('loginForm').classList.toggle('hidden');
  document.getElementById('registerForm').classList.toggle('hidden');
}

window.addEventListener('DOMContentLoaded', function() {
  if (new URLSearchParams(window.location.search).get('register') === 'true') {
    toggleForms();
  }
  
  const loginForm = document.querySelector('form[action="/login"]');
  if (loginForm) {
    loginForm.addEventListener('submit', handleLoginSubmit);
  }
  
  const registerForm = document.querySelector('form[action="/register"]');
  if (registerForm) {
    registerForm.addEventListener('submit', handleRegisterSubmit);
  }
});

async function handleLoginSubmit(e) {
  e.preventDefault();
  
  const username = document.getElementById('login-user').value.trim();
  const password = document.getElementById('login-password').value;
  
  if (!username || !password) {
    showAuthError('Por favor completa todos los campos');
    return;
  }
  
  const btn = e.target.querySelector('button[type="submit"]');
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = '<span style="display:inline-block; width:14px; height:14px; border:2px solid #544ee8; border-top-color:transparent; border-radius:50%; animation:spin .6s linear infinite;"></span>';
  
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username,
        password: password
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showAuthSuccess('¡Bienvenido! Redirigiendo...');
      setTimeout(() => {
        window.location.href = '/';
      }, 1500);
    } else {
      showAuthError(data.error || 'Error en las credenciales');
      btn.disabled = false;
      btn.textContent = originalText;
    }
  } catch (error) {
    console.error('Error:', error);
    showAuthError('Error de conexión. Intenta nuevamente.');
    btn.disabled = false;
    btn.textContent = originalText;
  }
}


function validateEmailFormat(email) {
    const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return pattern.test(email);
}
// ════════════════════════════════════════════════════
// REGISTER - AJAX Handler
// ════════════════════════════════════════════════════

async function handleRegisterSubmit(e) {
  e.preventDefault();
  
  const username = document.getElementById('register-name').value.trim();
  const email = document.getElementById('register-email').value.trim();
  const password = document.getElementById('register-password').value;
  const confirmPassword = document.getElementById('register-confirm').value;
  
  if (password !== confirmPassword) {
    showAuthError('Las contraseñas no coinciden');
    return;
  }
  
  if (password.length < 6) {
    showAuthError('La contraseña debe tener mínimo 6 caracteres');
    return;
  }
  
  if (!username || !email || !password) {
    showAuthError('Por favor completa todos los campos');
    return;
  }

  if (!validateEmailFormat(email)) {
    showAuthError('Formato de email inválido');
    return;
  }
  
  // Mostrar loading
  const btn = e.target.querySelector('button[type="submit"]');
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = '<span style="display:inline-block; width:14px; height:14px; border:2px solid #544ee8; border-top-color:transparent; border-radius:50%; animation:spin .6s linear infinite;"></span>';
  
  try {
    const response = await fetch('/api/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username,
        email: email,
        password: password
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showAuthSuccess('¡Cuenta creada! Tu solicitud está en revisión. Redirigiendo...');
      setTimeout(() => {
        window.location.href = '/login';
      }, 2000);
    } else {
      showAuthError(data.error || 'Error al crear la cuenta');
      btn.disabled = false;
      btn.textContent = originalText;
    }
  } catch (error) {
    console.error('Error:', error);
    showAuthError('Error de conexión. Intenta nuevamente.');
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

// ════════════════════════════════════════════════════
// Utilidades - Mostrar Mensajes
// ════════════════════════════════════════════════════

function showAuthError(message) {
  removeExistingAlert();
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  const form = loginForm.classList.contains('hidden') ? registerForm : loginForm;
  
  const alert = document.createElement('div');
  alert.className = 'alert alert-error';
  alert.style.marginBottom = '1rem';
  alert.textContent = message;
  
  const formElement = form.querySelector('form');
  form.insertBefore(alert, formElement);
  
  setTimeout(() => alert.remove(), 6000);
}

function showAuthSuccess(message) {
  removeExistingAlert();
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  const form = loginForm.classList.contains('hidden') ? registerForm : loginForm;
  
  const alert = document.createElement('div');
  alert.className = 'alert alert-success';
  alert.style.marginBottom = '1rem';
  alert.textContent = message;
  
  const formElement = form.querySelector('form');
  form.insertBefore(alert, formElement);
}

function removeExistingAlert() {
  const existingAlert = document.querySelector('.alert');
  if (existingAlert) {
    existingAlert.remove();
  }
}

// ════════════════════════════════════════════════════
// Password visibility toggle (mantener como antes)
// ════════════════════════════════════════════════════

function togglePasswordVisibility(fieldId) {
  const field = document.getElementById(fieldId);
  const button = event.target.closest('.password-toggle');
  
  if (field.type === 'password') {
    field.type = 'text';
    button.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
  } else {
    field.type = 'password';
    button.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';
  }
}

function validatePasswordMatch() {
  const password = document.getElementById('register-password');
  const confirm = document.getElementById('register-confirm');
  const error = document.getElementById('password-error');

  if (password.value && confirm.value) {
    if (password.value === confirm.value) {
      error.classList.remove('show');
      confirm.style.borderColor = 'rgba(255,255,255,0.07)';
    } else {
      error.classList.add('show');
      confirm.style.borderColor = 'rgba(255, 107, 107, 0.35)';
    }
  } else {
    if(error) error.classList.remove('show');
    confirm.style.borderColor = 'rgba(255,255,255,0.07)';
  }
}
