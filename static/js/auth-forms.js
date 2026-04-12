// ════════════════════════════════════════════════════
// Auth Forms Module - Login/Register Toggle
// ════════════════════════════════════════════════════

function toggleForms() {
  document.getElementById('loginForm').classList.toggle('hidden');
  document.getElementById('registerForm').classList.toggle('hidden');
}

window.addEventListener('DOMContentLoaded', function() {
  if (new URLSearchParams(window.location.search).get('register') === 'true') {
    toggleForms();
  }
});
