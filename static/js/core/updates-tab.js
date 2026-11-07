/* Sección "Actualizaciones" de Ajustes. Solo usa textContent (las notas del release
 * y los mensajes nunca se insertan como HTML). */
(function () {
  'use strict';

  async function request(url, options) {
    var res = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, options));
    var data = null;
    try { data = await res.json(); } catch (e) { /* sin cuerpo JSON */ }
    if (!res.ok) {
      throw new Error((data && data.message) || 'Error de comunicación (' + res.status + ').');
    }
    return data;
  }

  function init(root) {
    root = root || document.getElementById('updates-tab');
    if (!root || root.dataset.updatesReady === '1') { return; }
    root.dataset.updatesReady = '1';

    var api = root.dataset.api;
    var el = function (role) { return root.querySelector('[data-role="' + role + '"]'); };

    function say(text, isError) {
      var box = el('feedback');
      box.textContent = text || '';
      box.dataset.kind = isError ? 'error' : 'ok';
    }

    function render(info) {
      el('current').textContent = info.current_version;
      el('message').textContent = info.error || info.message || '';
      var box = el('update-box');
      box.hidden = !info.update_available;
      if (info.update_available) {
        el('latest').textContent = info.latest_version;
        el('notes').textContent = info.notes || '';
      }
      var apply = el('apply');
      apply.hidden = !(info.update_available && info.allowed);
      apply.disabled = !info.can_apply;
      apply.title = info.can_apply ? '' : 'Solo disponible en la versión instalada.';
    }

    async function load(path, options) {
      try { render(await request(api + path, options)); say(''); }
      catch (err) { say(err.message, true); }
    }

    el('check').addEventListener('click', async function () {
      var button = el('check');
      button.disabled = true;
      say('Buscando…', false);
      await load('/check', { method: 'POST', body: JSON.stringify({ force: true }) });
      button.disabled = false;
    });

    el('apply').addEventListener('click', async function () {
      if (!window.confirm('Stockly se cerrará, se actualizará y volverá a abrirse. ¿Continuar?')) { return; }
      el('apply').disabled = true;
      el('check').disabled = true;
      try {
        var data = await request(api + '/apply', { method: 'POST' });
        say(data.message, false);
      } catch (err) {
        say(err.message, true);
        el('apply').disabled = false;
        el('check').disabled = false;
      }
    });

    load('/status');
  }

  window.StocklyUpdatesTab = { init: init };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(); });
  } else {
    init();
  }
})();
