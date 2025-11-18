document.addEventListener('DOMContentLoaded', () => {
  fetch('/api/health')
    .then(r => r.json())
    .then(j => {
      const el = document.getElementById('health');
      if (el) el.textContent = j.status || 'unknown';
    })
    .catch(() => {
      const el = document.getElementById('health');
      if (el) el.textContent = 'error';
    });
});