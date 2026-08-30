/** Cliente HTTP del SOC. Todo lectura salvo el estado de una alerta. */
window.SOC = window.SOC || {};

(function () {
  'use strict';

  var BASE = (function () {
    // Mismo criterio que js/config.js del Playground: el backend expone 8000 por
    // defecto y el frontend se sirve en 3000 desde el mismo host.
    var p = window.location.protocol === 'https:' ? 'https:' : 'http:';
    return p + '//' + window.location.hostname + ':8000/api/v1/soc';
  })();

  function qs(params) {
    var partes = [];
    Object.keys(params || {}).forEach(function (k) {
      var v = params[k];
      if (v === null || v === undefined || v === '') return;
      partes.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
    });
    return partes.length ? '?' + partes.join('&') : '';
  }

  function get(path, params) {
    return fetch(BASE + path + qs(params), { headers: { Accept: 'application/json' } })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status + ' en ' + path);
        return r.json();
      });
  }

  window.SOC.api = {
    base: BASE,
    overview: function (endpoint) { return get('/overview', { endpoint: endpoint }); },
    turns: function (params) { return get('/turns', params); },
    turn: function (id) { return get('/turns/' + id); },
    session: function (id) { return get('/sessions/' + encodeURIComponent(id)); },
    runs: function () { return get('/runs'); },
    compare: function (a, b) { return get('/runs/compare', { a: a, b: b }); },
    alerts: function (estado) { return get('/alerts', { estado: estado }); },
    kb: function () { return get('/kb'); },
    kbFor: function (cat, sub) { return get('/kb/for', { categoria: cat, subcategoria: sub }); },
    kbDoc: function (clave) { return get('/kb/doc', { clave: clave }); },
    updateAlert: function (id, body) {
      return fetch(BASE + '/alerts/' + id, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      });
    },
    deleteRun: function (runId) {
      return fetch(BASE + '/runs/' + encodeURIComponent(runId), { method: 'DELETE' })
        .then(function (r) { return r.json(); });
    }
  };
})();
