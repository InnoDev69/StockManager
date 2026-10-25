// ════════════════════════════════════════════════════
// Auth Reset Password Module
// ════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {
  let lastEmail = '';
  let codeValue = '';

  const resetForm   = document.getElementById('reset-form');
  const codeForm    = document.getElementById('code-form');
  const newpassForm = document.getElementById('newpass-form');

  const submitBtn  = document.getElementById('submit-btn');
  const codeBtn    = document.getElementById('code-btn');
  const newpassBtn = document.getElementById('newpass-btn');

  const emailInput           = document.getElementById('reset-email');
  const codeInput            = document.getElementById('reset-code');
  const newPasswordInput     = document.getElementById('new-password');
  const confirmPasswordInput = document.getElementById('confirm-password');

  function showAlert(referenceEl, type, message) {
    document.querySelectorAll('.alert').forEach(a => a.remove());
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    referenceEl.parentNode.insertBefore(alert, referenceEl);
  }

  function setLoading(btn, loading, idleText) {
    btn.disabled = loading;
    btn.textContent = loading ? 'Cargando...' : idleText;
  }

  // Paso 1: enviar email
  resetForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    lastEmail = emailInput.value.trim();
    setLoading(submitBtn, true, 'Enviar codigo');

    try {
      const res  = await fetch('/api/users/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: lastEmail })
      });
      const data = await res.json();

      if (res.ok) {
        showAlert(resetForm, 'success', data.message);
        emailInput.value = '';
        resetForm.style.display = 'none';
        codeForm.style.display  = 'block';
      } else {
        showAlert(resetForm, 'error', data.error || 'Error al procesar la solicitud.');
      }
    } catch {
      showAlert(resetForm, 'error', 'Error de conexión. Intenta nuevamente.');
    } finally {
      setLoading(submitBtn, false, 'Enviar codigo');
    }
  });

  // Paso 2: validar código
  codeForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    codeValue = codeInput.value.trim();
    setLoading(codeBtn, true, 'Validar código');

    try {
      const res  = await fetch('/api/users/validate-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: lastEmail, code: codeValue })
      });
      const data = await res.json();

      if (res.ok) {
        showAlert(codeForm, 'success', 'Código validado. Ingresa tu nueva contraseña.');
        codeForm.style.display    = 'none';
        newpassForm.style.display = 'block';
      } else {
        showAlert(codeForm, 'error', data.error || 'Código inválido.');
      }
    } catch {
      showAlert(codeForm, 'error', 'Error de conexión. Intenta nuevamente.');
    } finally {
      setLoading(codeBtn, false, 'Validar código');
    }
  });

  // Paso 3: nueva contraseña
  newpassForm.addEventListener('submit', async function (e) {
    e.preventDefault();

    if (newPasswordInput.value !== confirmPasswordInput.value) {
      showAlert(newpassForm, 'error', 'Las contraseñas no coinciden.');
      return;
    }

    setLoading(newpassBtn, true, 'Cambiar contraseña');

    try {
      const res  = await fetch('/api/users/reset-password/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: lastEmail,
          code: codeValue,
          new_password: newPasswordInput.value
        })
      });
      const data = await res.json();

      if (res.ok) {
        showAlert(newpassForm, 'success', 'Contraseña cambiada correctamente. Ahora puedes iniciar sesión.');
        newpassForm.style.display = 'none';
        setTimeout(() => { window.location.href = '/login'; }, 2000);
      } else {
        showAlert(newpassForm, 'error', data.error || 'Error al cambiar la contraseña.');
      }
    } catch {
      showAlert(newpassForm, 'error', 'Error de conexión. Intenta nuevamente.');
    } finally {
      setLoading(newpassBtn, false, 'Cambiar contraseña');
    }
  });
});
