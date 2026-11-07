/* Pestaña "Licencia". Solo usa textContent (el nombre del cliente viene de la
 * licencia y nunca se inserta como HTML).
 * Si la pestaña se carga por AJAX, los <script> del fragmento no se ejecutan:
 * cargá este archivo en la página de configuración y llamá
 * window.StocklyLicenseTab.init() después de insertar el fragmento. */
(function () {
  'use strict';

  var STATE_LABELS = {
    LICENSED: 'Licencia activa',
    TRIAL: 'Período de prueba',
    TRIAL_EXPIRED: 'Prueba terminada',
    INVALID: 'Licencia no válida'
  };
  var FEATURE_LABELS = {
    multicaja: 'Multicaja LAN',
    marca_blanca: 'Marca blanca',
    backup_nube: 'Backup en la nube',
    bot: 'StocklyBot'
  };

  function formatDate(iso) {
    if (!iso) { return 'sin límite'; }
    var p = iso.split('-');
    return p[2] + '/' + p[1] + '/' + p[0];
  }

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
    root = root || document.getElementById('license-tab');
    if (!root || root.dataset.licenseReady === '1') { return; }
    root.dataset.licenseReady = '1';

    var api = root.dataset.api;
    var el = function (role) { return root.querySelector('[data-role="' + role + '"]'); };
    var feedback = el('feedback');

    function say(text, isError) {
      feedback.textContent = text || '';
      feedback.dataset.kind = isError ? 'error' : 'ok';
    }

    function render(s) {
      el('state-label').textContent = STATE_LABELS[s.state] || s.state;
      el('message').textContent = s.message || '';
      el('machine-id').textContent = s.machine_id;

      var details = el('details');
      details.hidden = !s.customer;
      if (s.customer) {
        el('customer').textContent = s.customer;
        el('plan').textContent = s.plan || '-';
        el('updates-until').textContent = formatDate(s.updates_until);
        var list = el('features');
        list.replaceChildren();
        Object.keys(s.features || {}).forEach(function (name) {
          var value = s.features[name];
          if (value === false || value === 0 || value === '') { return; }
          var label = FEATURE_LABELS[name] || name;
          var li = document.createElement('li');
          li.textContent = (value === true) ? label : label + ': ' + value;
          list.appendChild(li);
        });
        if (!list.children.length) {
          var none = document.createElement('li');
          none.textContent = 'Programa completo';
          list.appendChild(none);
        }
      }
      el('deactivate').hidden = !(s.state === 'LICENSED' || s.state === 'INVALID');
    }

    async function refresh() {
      try { render(await request(api)); }
      catch (err) { say(err.message, true); }
    }

    el('activate').addEventListener('click', async function () {
      var token = el('token').value.trim();
      if (!token) { say('Pegá primero la licencia.', true); return; }
      try {
        render(await request(api + '/activate', { method: 'POST', body: JSON.stringify({ token: token }) }));
        el('token').value = '';
        say('Licencia activada correctamente.', false);
      } catch (err) { say(err.message, true); }
    });

    el('deactivate').addEventListener('click', async function () {
      if (!window.confirm('¿Quitar la licencia de este equipo?')) { return; }
      try {
        render(await request(api + '/deactivate', { method: 'POST' }));
        say('Licencia quitada de este equipo.', false);
      } catch (err) { say(err.message, true); }
    });

    el('copy-machine').addEventListener('click', async function () {
      var code = el('machine-id').textContent;
      try { await navigator.clipboard.writeText(code); say('Código copiado.', false); }
      catch (e) { say('No se pudo copiar. Seleccionalo y copialo a mano.', true); }
    });

    refresh();
  }

  window.StocklyLicenseTab = { init: init };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(); });
  } else {
    init();
  }
})();
