/**
 * Shell del SOC: enrutado por hash, polling incremental y estado de captura.
 *
 * Todo vive en una sola página a propósito. Si cada destino fuera un documento, navegar
 * reiniciaría el polling y se perdería el hilo del vivo justo cuando se está explicando
 * algo — que es exactamente el momento en que no puede pasar.
 */
window.SOC = window.SOC || {};

(function () {
  'use strict';

  var api = window.SOC.api;
  var ui = window.SOC.ui;
  var views = window.SOC.views;

  var RUTAS = [
    { id: 'postura',      etiqueta: 'Postura' },
    { id: 'eventos',      etiqueta: 'Eventos' },
    { id: 'alertas',      etiqueta: 'Alertas' },
    { id: 'sesion',       etiqueta: 'Sesión' },
    { id: 'conocimiento', etiqueta: 'Conocimiento' },
    { id: 'playbook',     etiqueta: 'Playbooks' },
    { id: 'runs',         etiqueta: 'Corridas' }
  ];

  var INTERVALO_MS = 2000;

  var estado = {
    ruta: 'postura',
    params: new URLSearchParams(),
    cursor: 0,
    pausado: false,
    pendientes: 0,
    fallos: 0,
    timer: null,
    contadores: {}
  };

  // ---- navegación ----

  function pintarNav() {
    document.getElementById('nav').innerHTML = RUTAS.map(function (r) {
      var actual = r.id === estado.ruta;
      var n = estado.contadores[r.id];
      return '<a class="rail-link" href="#/' + r.id + '"' + (actual ? ' aria-current="page"' : '') + '>' +
        '<span>' + r.etiqueta + '</span>' +
        (n !== undefined && n !== null ? '<span class="rail-count">' + n + '</span>' : '') +
      '</a>';
    }).join('');
  }

  function parsearHash() {
    var h = (window.location.hash || '#/postura').replace(/^#\/?/, '');
    var partes = h.split('?');
    var id = partes[0] || 'postura';
    if (!views[id]) id = 'postura';
    return { ruta: id, params: new URLSearchParams(partes[1] || '') };
  }

  function navegar() {
    var r = parsearHash();
    estado.ruta = r.ruta;
    estado.params = r.params;
    pintarNav();

    var vista = views[estado.ruta];
    document.getElementById('page-title').textContent = vista.titulo;
    document.getElementById('page-sub').textContent = vista.subtitulo || '';
    var leyenda = document.getElementById('page-legend');
    leyenda.innerHTML = vista.leyenda || '';
    leyenda.hidden = !vista.leyenda;

    var el = document.getElementById('view');
    el.innerHTML = '';
    Promise.resolve(vista.render(el, estado.params))
      .catch(function (e) {
        el.innerHTML = ui.banner('error',
          'No se pudo cargar la vista: ' + ui.esc(e.message) +
          '. El backend puede estar caído — el SOC no forma parte del camino crítico del chat, ' +
          'así que esto no afecta a Clara.');
      });
  }

  // ---- captura en vivo ----

  function pintarCaptura() {
    var caja = document.getElementById('capture-state');
    var etiqueta = document.getElementById('capture-label');
    var detalle = document.getElementById('capture-detail');

    caja.classList.toggle('is-paused', estado.pausado);
    caja.classList.toggle('is-error', estado.fallos > 2);

    if (estado.fallos > 2) {
      etiqueta.textContent = 'Sin conexión';
      detalle.textContent = 'reintentando…';
      return;
    }
    if (estado.pausado) {
      etiqueta.textContent = 'Pausado';
      detalle.textContent = estado.pendientes
        ? estado.pendientes + ' turno(s) en espera'
        : 'sin turnos nuevos';
      return;
    }
    etiqueta.textContent = 'Capturando';
    detalle.textContent = 'cursor ' + estado.cursor;
  }

  function sondear() {
    if (estado.pausado) { pintarCaptura(); return; }

    api.turns({ since: estado.cursor, limit: 60 }).then(function (d) {
      // Recuperación tras un corte: si la vista actual se quedó con un banner de error,
      // vuelve a pintarse sola. Sin esto el panel seguía mostrando "backend caído"
      // minutos después de que el backend hubiera vuelto — que es justo el tipo de
      // mentira que un panel de vigilancia no se puede permitir.
      if (estado.fallos > 0) {
        estado.fallos = 0;
        if (document.querySelector('#view .banner.error')) navegar();
      }
      estado.fallos = 0;
      if (d.turnos.length) {
        estado.cursor = d.cursor;
        var vista = views[estado.ruta];
        if (vista && typeof vista.onTurns === 'function') vista.onTurns(d.turnos);
        else estado.pendientes += d.turnos.length;
        actualizarContadores();
      } else if (d.cursor > estado.cursor) {
        estado.cursor = d.cursor;
      }
      pintarCaptura();
    }).catch(function () {
      estado.fallos++;
      pintarCaptura();
    });
  }

  function actualizarContadores() {
    api.overview().then(function (d) {
      estado.contadores.eventos = d.totales.turnos;
      estado.contadores.alertas = (d.totales.alertas && d.totales.alertas.nueva) || 0;
      estado.contadores.runs = (d.runs || []).length;
      pintarNav();
    }).catch(function () { /* el contador es accesorio: si falla, no pasa nada */ });
  }

  // ---- API pública para las vistas ----

  window.SOC.app = {
    rerender: navegar,
    estaPausado: function () { return estado.pausado; },
    alternarPausa: function () {
      estado.pausado = !estado.pausado;
      if (!estado.pausado && estado.pendientes) {
        estado.pendientes = 0;
        navegar();   // al reanudar se recarga la vista para no perder lo acumulado
      }
      pintarCaptura();
      return estado.pausado;
    }
  };

  // ---- arranque ----

  window.addEventListener('hashchange', navegar);

  document.addEventListener('keydown', function (e) {
    // Pausar con espacio es lo que se necesita en una demostración: se para el
    // stream para explicar una traza sin tener que buscar el botón.
    if (e.code === 'Space' && e.target === document.body) {
      e.preventDefault();
      window.SOC.app.alternarPausa();
      var btn = document.getElementById('btn-pausa');
      if (btn) {
        var p = estado.pausado;
        btn.textContent = p ? 'Reanudar' : 'Pausar';
        btn.classList.toggle('is-active', p);
        btn.setAttribute('aria-pressed', String(p));
      }
    }
  });

  api.turns({ limit: 1 }).then(function (d) {
    estado.cursor = d.cursor;
  }).catch(function () { estado.fallos++; }).then(function () {
    navegar();
    actualizarContadores();
    pintarCaptura();
    estado.timer = setInterval(sondear, INTERVALO_MS);
  });
})();
