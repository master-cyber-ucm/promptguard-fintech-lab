/** Las pantallas del SOC. Cada vista expone render() y, si le interesa el vivo, onTurns(). */
window.SOC = window.SOC || {};

(function () {
  'use strict';

  var api = window.SOC.api;
  var ui = window.SOC.ui;
  var md = window.SOC.md;
  var esc = ui.esc;

  var V = {};

  // ======================================================================
  // Postura — la entrada. Qué se está vigilando y, sobre todo, qué no.
  // ======================================================================

  V.postura = {
    endpoint: '',
    titulo: 'Postura',
    subtitulo: 'Qué componentes han bloqueado cada vector y qué turnos siguieron adelante. ' +
               'Actividad observada — no evalúa si el proxy acertó: eso es el Analyze Pass.',
    render: function (el) {
      el.innerHTML = '<div class="stack">' + esqueleto() + '</div>';
      return api.overview(self.endpoint).then(function (d) {
        var t = d.totales;
        var partes = [];

        partes.push(filtroEndpointPostura(self.endpoint));

        if (!t.turnos) {
          partes.push(vacioGlobal());
        } else {
          partes.push(
            '<section class="panel"><div class="panel-head">' +
            '<h2>Actividad por componente</h2>' +
            '<span class="hint">' + t.eventos + ' eventos sobre ' + t.turnos +
            ' turnos · ' + t.sesiones + ' sesiones · latencia media ' + ui.ms(t.latencia_media_ms) + '</span>' +
            '</div><div class="panel-body flush">' + estaciones(d.componentes) + '</div></section>'
          );
        }

        partes.push(
          '<section class="panel"><div class="panel-head">' +
          '<h2>Bloqueos por vector</h2>' +
          '<span class="hint">Turnos observados y componente que los bloqueó; no mide eficacia ni atribuye causalidad exclusiva</span>' +
          '</div><div class="panel-body">' + cobertura(d.cobertura) + '</div></section>'
        );

        if (d.runs && d.runs.length) {
          partes.push(
            '<section class="panel"><div class="panel-head"><h2>Últimas corridas</h2>' +
            '<span class="hint"><a href="#/runs">comparar corridas →</a></span></div>' +
            '<div class="panel-body">' + tablaRuns(d.runs) + '</div></section>'
          );
        }

        el.innerHTML = '<div class="stack">' + partes.join('') + '</div>';
        var selector = el.querySelector('#postura-endpoint');
        selector.addEventListener('change', function () {
          self.endpoint = selector.value;
          window.SOC.app.rerender();
        });
      });
    }
  };

  function filtroEndpointPostura(seleccionado) {
    var endpoints = {
      'simple-prompt': 'Prompt simple',
      'complex-prompt': 'Prompt avanzado',
      'complex-with-context': 'Con contexto',
      'proxy': 'Proxy protegido',
      'complex-with-document': 'Documento adjunto'
    };
    var opciones = '<option value="">Todos los endpoints</option>' +
      Object.keys(endpoints).map(function (endpoint) {
        return '<option value="' + esc(endpoint) + '"' +
          (seleccionado === endpoint ? ' selected' : '') + '>' + esc(endpoints[endpoint]) + '</option>';
      }).join('');
    return '<section class="panel"><div class="filters">' +
      '<label for="postura-endpoint">Endpoint</label>' +
      '<select id="postura-endpoint">' + opciones + '</select>' +
      '</div></section>';
  }

  function vacioGlobal() {
    return '<section class="panel"><div class="panel-body">' + ui.vacio(
      'Sin tráfico capturado todavía',
      'El SOC registra lo que el proxy decide sobre cada prompt. En cuanto pase el primer turno, aparecerá aquí.',
      '<div>Ataca desde el <a href="playground.html">Playground</a>, o lanza la batería completa:</div>' +
      '<div><code>make suite</code></div>'
    ) + '</div></section>';
  }

  function estaciones(componentes) {
    var porNombre = {};
    (componentes || []).forEach(function (c) { porNombre[c.componente] = c; });

    return '<div class="stations">' + ui.COMPONENTES.map(function (nombre) {
      var c = porNombre[nombre] || { ALLOW: 0, SUSPICIOUS: 0, BLOCK: 0, total: 0, latencia_media_ms: 0 };
      var total = c.total || 0;
      var pct = function (n) { return total ? (n / total * 100) : 0; };
      var barra = total
        ? '<div class="bar">' +
            '<i class="allow" style="width:' + pct(c.ALLOW) + '%"></i>' +
            '<i class="susp"  style="width:' + pct(c.SUSPICIOUS) + '%"></i>' +
            '<i class="block" style="width:' + pct(c.BLOCK) + '%"></i>' +
          '</div>'
        : '<div class="bar is-empty" title="Este componente no ha evaluado nada todavía"></div>';

      return '<div class="station">' +
        '<div class="station-name' + (total ? '' : ' is-idle') + '">' + esc(nombre) + '</div>' +
        barra +
        '<div class="station-counts">' +
          '<span><b>' + c.ALLOW + '</b> allow</span>' +
          '<span><b>' + c.SUSPICIOUS + '</b> susp</span>' +
          '<span><b>' + c.BLOCK + '</b> block</span>' +
        '</div>' +
        '<div class="station-lat">' + (total ? ui.ms(c.latencia_media_ms) : '—') + '</div>' +
      '</div>';
    }).join('') + '</div>';
  }

  function cobertura(filas) {
    var componentes = ui.COMPONENTES;
    return '<div class="coverage-wrap">' +
      '<table class="coverage"><thead><tr>' +
        '<th>Vector</th><th style="text-align:right">Turnos</th>' +
        componentes.map(function (c) { return '<th style="text-align:right">' + esc(c) + '</th>'; }).join('') +
        '<th style="text-align:right">No bloqueado</th>' +
      '</tr></thead><tbody>' +
      (filas || []).map(function (f) {
        var docs = f.documentada
          ? '<a href="#/conocimiento?cat=' + encodeURIComponent(f.categoria) +
            '&sub=' + encodeURIComponent(f.subcategoria) + '">documentación</a>'
          : '<span class="mono" style="font-size:11px">sin documentación</span>';
        var bloqueos = f.bloqueos_por_componente || {};
        return '<tr>' +
          '<td class="vector">' + esc(ui.vector(f.categoria)) +
            '<span class="sub">' + esc(f.subcategoria) + ' · ' + docs + '</span></td>' +
          '<td class="num">' + f.turnos + '</td>' +
          componentes.map(function (c) { return '<td class="num">' + (bloqueos[c] || 0) + '</td>'; }).join('') +
          '<td class="num">' + f.no_bloqueados + '</td>' +
        '</tr>';
      }).join('') +
      '</tbody></table></div>';
  }

  // ======================================================================
  // Eventos — el stream cronológico en vivo.
  // ======================================================================

  V.eventos = {
    titulo: 'Eventos',
    subtitulo: 'Registro cronológico de los turnos procesados por el proxy. Cada fila permite revisar su contexto y resultado.',
    leyenda:
      '<section class="component-note" aria-label="Nota sobre la columna Componentes">' +
        '<strong class="component-note-title">Nota sobre la columna Componentes</strong>' +
        '<p>Resume, en el orden del pipeline, el estado con que cada defensa procesó el turno.</p>' +
        '<div class="legend-values"><span class="legend-label">Valores:</span>' +
          '<span class="legend-status"><i class="allow"></i>ALLOW · evaluó sin bloquear</span>' +
          '<span class="legend-status"><i class="susp"></i>SUSPICIOUS · requiere revisión</span>' +
          '<span class="legend-status"><i class="block"></i>BLOCK · detuvo el turno</span>' +
          '<span class="legend-status"><i class="absent"></i>no evaluó</span>' +
        '</div>' +
        '<ul class="legend-components">' +
          '<li><code>input_sanitizer</code> detecta inyección directa en el prompt de entrada.</li>' +
          '<li><code>pii_shield</code> redacta datos personales y financieros sensibles.</li>' +
          '<li><code>document_sanitizer</code> neutraliza instrucciones maliciosas dentro de documentos.</li>' +
          '<li><code>tool_gatekeeper</code> valida permisos y límites antes de ejecutar herramientas.</li>' +
          '<li><code>output_auditor</code> detecta filtraciones del prompt de sistema y de configuración.</li>' +
          '<li><code>leak_guard</code> bloquea IBANes ajenos y fugas de datos confidenciales.</li>' +
        '</ul>' +
      '</section>',
    filtros: {},
    filtrosAbiertos: false,
    pagina: 0,
    cursores: [null],
    render: function (el, params) {
      var self = this;
      // Una corrida no debe obligar a recordar y reintroducir su identificador en
      // el stream. El enlace desde Corridas llega aquí con el filtro ya aplicado;
      // la persona revisora puede abrir después cada Turn y su Session File.
      var runId = params && params.get('run_id');
      if (runId && self.filtros.run_id !== runId) {
        self.filtros = { run_id: runId };
        reiniciarPaginacion(self);
      }
      el.innerHTML =
        '<section class="panel">' +
          barraFiltros(self.filtros) +
          cabeceraTurnos() +
          '<div class="stream" id="stream">' + esqueleto() + '</div>' +
        '</section>';

      cablearFiltros(el, self);

      var consulta = Object.assign({ limit: PAGINA }, self.filtros);
      var before = self.cursores[self.pagina];
      if (before) consulta.before = before;

      return api.turns(consulta).then(function (d) {
        var stream = el.querySelector('#stream');
        if (!d.turnos.length) {
          stream.innerHTML = ui.vacio(
            'Nada que mostrar',
            Object.keys(self.filtros).length
              ? 'Ningún turno capturado casa con estos filtros.'
              : 'Todavía no ha pasado ningún turno por el proxy.',
            Object.keys(self.filtros).length
              ? '<button class="btn" id="limpiar-filtros">Quitar todos los filtros</button>'
              : '<div>Ataca desde el <a href="playground.html">Playground</a> o lanza <code>make suite</code></div>'
          );
          var limpiar = stream.querySelector('#limpiar-filtros');
          if (limpiar) limpiar.addEventListener('click', function () {
            self.filtros = {}; window.SOC.app.rerender();
          });
          return;
        }
        stream.innerHTML = d.turnos.map(function (t) { return filaTurno(t); }).join('');
        cablearTurnos(stream);
        pintarPaginacion(el, self, d.turnos, d.has_more);
      });
    },
    /** Inserción incremental solo en la primera página, que representa el vivo. */
    onTurns: function (nuevos) {
      var stream = document.querySelector('#stream');
      if (!stream || !nuevos.length || this.pagina !== 0) return;
      var vacia = stream.querySelector('.empty');
      if (vacia) stream.innerHTML = '';
      // Llegan de más reciente a más antiguo; se insertan arriba en orden inverso
      // para que el más nuevo acabe el primero.
      nuevos.slice().reverse().forEach(function (t) {
        var wrap = document.createElement('div');
        wrap.innerHTML = filaTurno(t, true);
        var nodo = wrap.firstElementChild;
        stream.insertBefore(nodo, stream.firstChild);
        cablearTurnos(nodo.parentNode, nodo);
      });
      // La primera página siempre contiene exactamente PAGINA filas como máximo.
      while (stream.children.length > PAGINA) stream.removeChild(stream.lastElementChild);
    }
  };

  var PAGINA = 60;

  /** Paginación por cursor: cada página reemplaza por completo la anterior. */
  function pintarPaginacion(el, vista, turnos, haySiguiente) {
    var stream = el.querySelector('#stream');
    if (!stream) return;
    var viejo = el.querySelector('#stream-paginacion');
    if (viejo) viejo.remove();

    var hayAnterior = vista.pagina > 0;
    if (haySiguiente === undefined) haySiguiente = turnos.length === PAGINA;
    var pie = document.createElement('nav');
    pie.id = 'stream-paginacion';
    pie.className = 'stream-pie';
    pie.setAttribute('aria-label', 'Paginación de eventos');
    pie.innerHTML =
      '<button class="btn" id="btn-anterior"' + (hayAnterior ? '' : ' disabled') + '>Anterior</button>' +
      '<span class="mono">Página ' + (vista.pagina + 1) + ' · ' + turnos.length + ' turnos</span>' +
      '<button class="btn" id="btn-siguiente"' + (haySiguiente ? '' : ' disabled') + '>Siguiente</button>';
    stream.parentNode.appendChild(pie);

    pie.querySelector('#btn-anterior').addEventListener('click', function () {
      vista.pagina--;
      window.SOC.app.rerender();
    });
    pie.querySelector('#btn-siguiente').addEventListener('click', function () {
      vista.cursores[vista.pagina + 1] = turnos[turnos.length - 1].id;
      vista.pagina++;
      window.SOC.app.rerender();
    });
  }

  function reiniciarPaginacion(vista) {
    vista.pagina = 0;
    vista.cursores = [null];
  }

  function etiquetaComponente(componente) {
    var etiquetas = {
      input_sanitizer: 'Filtro de entrada',
      pii_shield: 'Protección de datos',
      document_sanitizer: 'Filtro de documentos',
      tool_gatekeeper: 'Control de herramientas',
      output_auditor: 'Auditor de salida',
      leak_guard: 'Guardia de fugas'
    };
    return etiquetas[componente] || componente;
  }

  function etiquetaCanal(endpoint) {
    var etiquetas = {
      'simple-prompt': 'Prompt simple',
      'complex-prompt': 'Prompt avanzado',
      'complex-with-context': 'Con contexto',
      'proxy': 'Proxy protegido',
      'complex-with-document': 'Documento adjunto'
    };
    return etiquetas[endpoint] || endpoint || '—';
  }

  function barraFiltros(f) {
    var opt = function (v, txt, sel) {
      return '<option value="' + esc(v) + '"' + (sel === v ? ' selected' : '') + '>' + esc(txt) + '</option>';
    };
    var accion = function (valor, texto) {
      return '<button class="btn filter-quick' + (f.accion === valor ? ' is-active' : '') +
        '" data-accion="' + (valor || '') + '">' + texto + '</button>';
    };
    var endpoints = {
      'simple-prompt': 'Prompt simple',
      'complex-prompt': 'Prompt avanzado',
      'complex-with-context': 'Con contexto',
      'proxy': 'Proxy protegido',
      'complex-with-document': 'Documento adjunto'
    };
    var taxonomias = [
      'LLM01-prompt-injection', 'LLM02-sensitive-information-disclosure',
      'LLM06-excessive-agency', 'LLM07-system-prompt-leakage', '_extensiones'
    ];
    return '<div class="filters">' +
      '<input id="f-texto" type="search" placeholder="Buscar en prompt o respuesta…" value="' +
        esc(f.texto || '') + '" aria-label="Buscar texto" />' +
      '<div class="filter-quick-group" role="group" aria-label="Filtrar por decisión">' +
        accion('', 'Todos') + accion('BLOCK', 'Con bloqueos') + accion('SUSPICIOUS', 'Con sospechas') +
      '</div>' +
      '<div class="spacer"></div>' +
      '<button class="btn" id="btn-mas-filtros" aria-expanded="' + Boolean(V.eventos.filtrosAbiertos) + '">Más filtros</button>' +
      '<button class="btn" id="btn-pausa" aria-pressed="false">Pausar</button>' +
      (V.eventos.filtrosAbiertos
        ? '<div class="filters-advanced">' +
            '<label>Canal <select id="f-endpoint">' +
              opt('', 'Todos', f.endpoint) + Object.keys(endpoints).map(function (e) { return opt(e, endpoints[e], f.endpoint); }).join('') +
            '</select></label>' +
            '<label>Tipo de ejecución <select id="f-origen">' +
              opt('', 'Todos', f.origen) + opt('interactivo', 'Manual', f.origen) +
              opt('suite', 'Suite', f.origen) + opt('redteam-agent', 'Agente red-team', f.origen) +
            '</select></label>' +
            '<label>Taxonomía <select id="f-categoria">' +
              opt('', 'Todas', f.categoria) + taxonomias.map(function (c) { return opt(c, ui.vector(c), f.categoria); }).join('') +
            '</select></label>' +
            '<label>Defensa <select id="f-componente">' +
              opt('', 'Todas', f.componente) + ui.COMPONENTES.map(function (c) { return opt(c, etiquetaComponente(c), f.componente); }).join('') +
            '</select></label>' +
            '<label>Usuario <input id="f-user" value="' + esc(f.user_id || '') + '" placeholder="p. ej., usr_001" /></label>' +
            '<label>Corrida <input id="f-run" value="' + esc(f.run_id || '') + '" placeholder="ID de corrida" /></label>' +
            '<button class="btn subtle" id="btn-limpiar-filtros">Limpiar filtros</button>' +
          '</div>'
        : '') +
    '</div>';
  }

  function cablearFiltros(el, vista) {
    var mapa = { 'f-endpoint': 'endpoint', 'f-origen': 'origen', 'f-componente': 'componente',
                 'f-categoria': 'categoria', 'f-user': 'user_id', 'f-run': 'run_id' };
    Object.keys(mapa).forEach(function (id) {
      var nodo = el.querySelector('#' + id);
      if (!nodo) return;
      nodo.addEventListener('change', function () {
        var v = nodo.value.trim();
        if (v) vista.filtros[mapa[id]] = v; else delete vista.filtros[mapa[id]];
        reiniciarPaginacion(vista);
        window.SOC.app.rerender();
      });
    });
    var busqueda = el.querySelector('#f-texto');
    busqueda.addEventListener('input', function () {
      clearTimeout(vista.busquedaTimer);
      vista.busquedaTimer = setTimeout(function () {
        var v = busqueda.value.trim();
        if (v) vista.filtros.texto = v; else delete vista.filtros.texto;
        reiniciarPaginacion(vista);
        window.SOC.app.rerender();
      }, 300);
    });
    Array.prototype.forEach.call(el.querySelectorAll('[data-accion]'), function (boton) {
      boton.addEventListener('click', function () {
        var accion = boton.dataset.accion;
        if (accion) vista.filtros.accion = accion; else delete vista.filtros.accion;
        reiniciarPaginacion(vista);
        window.SOC.app.rerender();
      });
    });
    el.querySelector('#btn-mas-filtros').addEventListener('click', function () {
      vista.filtrosAbiertos = !vista.filtrosAbiertos;
      window.SOC.app.rerender();
    });
    var limpiar = el.querySelector('#btn-limpiar-filtros');
    if (limpiar) limpiar.addEventListener('click', function () {
      vista.filtros = {};
      reiniciarPaginacion(vista);
      window.SOC.app.rerender();
    });
    var pausa = el.querySelector('#btn-pausa');
    if (pausa) {
      var estado = window.SOC.app.estaPausado();
      pausa.textContent = estado ? 'Reanudar' : 'Pausar';
      pausa.classList.toggle('is-active', estado);
      pausa.setAttribute('aria-pressed', String(estado));
      pausa.addEventListener('click', function () {
        var nuevo = window.SOC.app.alternarPausa();
        pausa.textContent = nuevo ? 'Reanudar' : 'Pausar';
        pausa.classList.toggle('is-active', nuevo);
        pausa.setAttribute('aria-pressed', String(nuevo));
      });
    }
  }

  function filaTurno(t, nuevo) {
    var origen = origenTurno(t);
    var decision = decisionTurno(t.eventos);
    var canal = etiquetaCanal(t.endpoint);
    return '<details class="turn' + (nuevo ? ' is-new' : '') + '" data-id="' + t.id +
             '" data-session="' + esc(t.session_id) + '">' +
      '<summary class="turn-row">' +
        '<span class="turn-time">' + ui.hora(t.ts) + '</span>' +
        '<span class="turn-endpoint" title="' + esc(t.endpoint) + '">' + esc(canal) + '</span>' +
        '<span class="turn-origin" title="' + esc(origen) + '">' + esc(origen) + '</span>' +
        '<span class="turn-prompt">' +
          esc(ui.recorta(ui.mensajeReal(t.prompt).replace(/\s+/g, ' '), 150)) + '</span>' +
        '<span class="turn-decision">' + ui.tag(decision) + '</span>' +
        ui.chain(t.eventos) +
        '<span class="turn-lat">' + ui.ms(t.latencia_total_ms) + '</span>' +
        '<span class="turn-caret" aria-hidden="true">›</span>' +
      '</summary>' +
      '<div class="trace" data-cargado="0"></div>' +
    '</details>';
  }

  function decisionTurno(eventos) {
    var rango = { ALLOW: 1, SUSPICIOUS: 2, BLOCK: 3 };
    return (eventos || []).reduce(function (peor, evento) {
      return (rango[evento.accion] || 0) > (rango[peor] || 0) ? evento.accion : peor;
    }, 'SIN EVALUACIÓN');
  }

  function origenTurno(t) {
    if (t.fixture_id) {
      var prefijos = {
        'attack-prompts': 'fix',
        'legitimate-prompts': 'leg',
        'navi-prompts': 'navi'
      };
      var prefijo = prefijos[t.fixture_kind];
      if (!prefijo) {
        prefijo = /^leg_/i.test(t.fixture_id) ? 'leg' :
          (/^navi_/i.test(t.fixture_id) ? 'navi' : 'fix');
      }
      var taxonomia = [t.categoria, t.subcategoria].filter(Boolean).join('/');
      return prefijo + '/' + (taxonomia || t.fixture_id);
    }
    if (t.origen === 'redteam-agent') return 'redteam/' + (t.run_id || 'agent');
    if (t.origen === 'suite') return 'suite/' + (t.run_id || 'sin-fixture');
    return 'manual';
  }

  function cabeceraTurnos() {
    return '<div class="turn-head">' +
      '<span>Hora</span>' +
      '<span>Canal</span>' +
      '<span>Caso</span>' +
      '<span>Prompt</span>' +
      '<span>Decisión</span>' +
      '<span>Defensas</span>' +
      '<span>Tiempo</span>' +
      '<span aria-hidden="true"></span>' +
    '</div>';
  }

  function cablearTurnos(raiz, soloNodo) {
    var nodos = soloNodo ? [soloNodo] : raiz.querySelectorAll('details.turn');
    Array.prototype.forEach.call(nodos, function (d) {
      if (d.dataset.cableado === '1') return;
      d.dataset.cableado = '1';
      d.addEventListener('toggle', function () {
        if (!d.open) return;
        var caja = d.querySelector('.trace');
        if (caja.dataset.cargado === '1') return;
        caja.dataset.cargado = '1';
        caja.innerHTML = esqueleto();
        api.turn(d.dataset.id).then(function (t) {
          caja.innerHTML = traza(t);
        }).catch(function (e) {
          caja.innerHTML = ui.banner('error', 'No se pudo cargar la traza: ' + esc(e.message));
        });
      });
    });
  }

  function traza(t) {
    var postura = '<div class="posture' + (t.vulnerable ? ' is-vulnerable' : '') + '">' +
      '<strong>Postura:</strong> ' + esc(t.postura || 'sin registrar') +
      ' · <strong>Usuario:</strong> ' + esc(t.user_id || 'sin registrar') +
      (t.fixture_id ? ' · <strong>Fixture:</strong> ' + esc(t.fixture_id) : '') +
      (t.categoria ? ' · <strong>Taxonomía:</strong> ' + esc(t.categoria) + '/' + esc(t.subcategoria) : '') +
    '</div>';

    var pasos = (t.eventos && t.eventos.length)
      ? '<div class="trace-steps">' + t.eventos.map(function (e) {
          var detalle = e.detalle ? '<em>' + esc(JSON.stringify(e.detalle)) + '</em>' : '';
          return '<div class="trace-step">' +
            '<span class="c">' + esc(e.componente) + '</span>' +
            '<span class="o">' + esc(e.objetivo) + '</span>' +
            '<span>' + ui.tag(e.accion) + '</span>' +
            '<span class="r">' + esc(e.razon || '—') +
              (e.regla ? '<em>regla: ' + esc(e.regla) + '</em>' : '') + detalle + '</span>' +
            '<span class="l">' + ui.ms(e.latencia_ms) + '</span>' +
          '</div>';
        }).join('') + '</div>'
      : '<div class="trace-empty"><strong>Ningún componente examinó este turno</strong>' +
        (t.vulnerable
          ? 'Modo vulnerable: todas las capas de defensa estaban desactivadas. Es el estado esperado, no un fallo de captura.'
          : 'Este endpoint no tiene ninguna defensa activa en esta configuración.') +
        '</div>';

    var io = '<div class="trace-io">' +
      '<div><h4>Prompt recibido</h4><pre>' + esc(t.prompt) + '</pre></div>' +
      '<div><h4>Respuesta entregada</h4><pre>' + esc(t.respuesta || '(sin respuesta)') + '</pre></div>' +
    '</div>';

    var k = t.conocimiento || {};
    var acciones = '<div class="trace-actions">' +
      '<a class="btn" href="#/sesion?id=' + encodeURIComponent(t.session_id) + '">Ver sesión completa</a>' +
      (k.playbook ? '<a class="btn" href="#/playbook?doc=' + encodeURIComponent(k.playbook.clave) +
        '">Playbook de respuesta</a>' : '') +
      (k.defensa ? '<a class="btn" href="#/conocimiento?doc=' + encodeURIComponent(k.defensa.clave) +
        '">Diseño de la defensa</a>' : '') +
      (k.disponible
        ? '<a class="btn subtle" href="#/conocimiento?cat=' + encodeURIComponent(t.categoria) +
          '&sub=' + encodeURIComponent(t.subcategoria) + '">Contexto del vector</a>'
        : '<span class="mono" style="font-size:11.5px;color:var(--ink-3)">' +
          (t.categoria ? 'Sin documentación para ' + esc(t.subcategoria) : 'Turno sin taxonomía: no hay documentación asociable') +
          '</span>') +
    '</div>';

    return postura + pasos + io + acciones;
  }

  // ======================================================================
  // Sesión — revisión y correlación de un chat concreto.
  // ======================================================================

  V.sesion = {
    titulo: 'Sesión',
    subtitulo: 'Un chat de principio a fin: la conversación, la traza de defensa de cada turno y con qué se relaciona.',
    render: function (el, params) {
      var id = params.get('id');
      if (!id) {
        el.innerHTML = '<section class="panel"><div class="panel-body">' + ui.vacio(
          'Ninguna sesión seleccionada',
          'Abre una sesión desde un turno del stream de eventos.',
          '<a class="btn" href="#/eventos">Ir a Eventos</a>'
        ) + '</div></section>';
        return Promise.resolve();
      }
      el.innerHTML = esqueleto();
      return api.session(id).then(function (d) {
        var turnos = d.turnos;
        var multi = turnos.length > 1;
        var partes = [];

        partes.push('<section class="panel"><div class="panel-head">' +
          '<h2 class="mono">' + esc(id) + '</h2>' +
          '<span class="hint">' + turnos.length + (multi ? ' turnos' : ' turno') + ' · ' +
          esc(turnos[0].endpoint) + ' · ' + esc(turnos[0].user_id) + '</span></div>' +
          '<div class="panel-body">' +
          (multi
            ? ui.banner('info', '<span>Sesión multi-turno: la escalada entre turnos es visible abajo, ' +
                'en orden cronológico. Los ataques progresivos se leen aquí, no en el stream.</span>')
            : ui.banner('info', '<span>Sesión de un solo turno: no hay escalada que mostrar.</span>')) +
          '</div></section>');

        partes.push('<section class="panel"><div class="panel-head"><h2>Conversación y defensa</h2></div>' +
          '<div class="panel-body"><div class="conv">' +
          turnos.map(function (t, i) {
            return '<div class="conv-turn">' +
              '<div class="conv-head">' +
                '<span class="conv-n">T' + (i + 1) + '</span>' +
                '<span class="mono" style="font-size:12px">' + ui.hora(t.ts) + '</span>' +
                ui.chain(t.eventos) +
                (t.fixture_id ? '<span class="turn-badge">' + esc(t.fixture_id) + '</span>' : '') +
                (t.vulnerable ? '<span class="turn-badge vuln">VULNERABLE</span>' : '') +
                '<span class="mono" style="font-size:11.5px;color:var(--ink-3);margin-left:auto">' +
                  ui.ms(t.latencia_total_ms) + '</span>' +
              '</div>' +
              '<div class="conv-body">' +
                '<div class="msg"><h4>Cliente</h4><pre>' + esc(t.prompt) + '</pre></div>' +
                '<div class="msg"><h4>Clara</h4><pre>' + esc(t.respuesta || '(sin respuesta)') + '</pre></div>' +
                (t.eventos.length
                  ? '<div class="trace-steps">' + t.eventos.map(function (e) {
                      return '<div class="trace-step">' +
                        '<span class="c">' + esc(e.componente) + '</span>' +
                        '<span class="o">' + esc(e.objetivo) + '</span>' +
                        '<span>' + ui.tag(e.accion) + '</span>' +
                        '<span class="r">' + esc(e.razon || '—') + '</span>' +
                        '<span class="l">' + ui.ms(e.latencia_ms) + '</span>' +
                      '</div>';
                    }).join('') + '</div>'
                  : '<div class="trace-empty"><strong>Ningún componente examinó este turno</strong>' +
                    'Postura: ' + esc(t.postura || 'sin registrar') + '</div>') +
              '</div></div>';
          }).join('') + '</div></div></section>');

        partes.push(relacionados(d.relacionados));

        var k = d.conocimiento || {};
        if (k.disponible) {
          partes.push('<section class="panel"><div class="panel-head">' +
            '<h2>Contexto de este vector</h2><span class="hint">' +
            esc(k.categoria) + ' / ' + esc(k.subcategoria) + '</span></div>' +
            '<div class="panel-body"><div class="trace-actions">' +
            (k.playbook ? '<a class="btn" href="#/playbook?doc=' + encodeURIComponent(k.playbook.clave) + '">Playbook</a>' : '') +
            (k.defensa ? '<a class="btn" href="#/conocimiento?doc=' + encodeURIComponent(k.defensa.clave) + '">Defensa</a>' : '') +
            k.ataque.map(function (doc) {
              return '<a class="btn subtle" href="#/conocimiento?doc=' + encodeURIComponent(doc.clave) + '">' +
                esc(doc.titulo) + '</a>';
            }).join('') + '</div></div></section>');
        }

        el.innerHTML = '<div class="stack">' + partes.join('') + '</div>';
      }).catch(function (e) {
        el.innerHTML = ui.banner('error', 'No se pudo cargar la sesión: ' + esc(e.message));
      });
    }
  };

  function relacionados(r) {
    var grupos = [
      ['mismo_usuario', 'Mismo usuario'],
      ['mismo_fixture', 'Mismo fixture'],
      ['misma_taxonomia', 'Misma taxonomía']
    ];
    var hay = grupos.some(function (g) { return (r[g[0]] || []).length; });
    if (!hay) {
      return '<section class="panel"><div class="panel-head"><h2>Relacionados</h2></div>' +
        '<div class="panel-body">' + ui.vacio(
          'Sin sesiones relacionadas',
          'Esta sesión es única en lo capturado: ningún otro chat comparte usuario, fixture ni taxonomía.'
        ) + '</div></section>';
    }
    return '<section class="panel"><div class="panel-head"><h2>Relacionados</h2>' +
      '<span class="hint">Coincidencias exactas sobre lo capturado — no es inferencia estadística</span>' +
      '</div><div class="panel-body"><div class="related">' +
      grupos.map(function (g) {
        var items = r[g[0]] || [];
        if (!items.length) return '';
        return '<div class="related-group"><h3>' + g[1] + ' (' + items.length + ')</h3>' +
          items.map(function (s) {
            return '<a class="related-item" href="#/sesion?id=' + encodeURIComponent(s.session_id) + '">' +
              '<span class="mono">' + esc(ui.recorta(s.session_id, 26)) + '</span>' +
              '<span class="mono">' + s.turnos + 'T · ' + (s.bloqueados || 0) + ' block</span></a>';
          }).join('') + '</div>';
      }).join('') + '</div></div></section>';
  }

  // ======================================================================
  // Conocimiento y Playbook — comparten el visor, difieren en el filtro.
  // ======================================================================

  function vistaKB(soloPlaybooks) {
    return {
      titulo: soloPlaybooks ? 'Playbooks' : 'Conocimiento',
      subtitulo: soloPlaybooks
        ? 'Los siete procedimientos de respuesta a incidentes: detección, clasificación, contención, ' +
          'erradicación, recuperación, post-mortem y roles.'
        : 'Los documentos de ataque y defensa del proyecto, navegables por taxonomía. Contexto y formación.',
      render: function (el, params) {
        el.innerHTML = esqueleto();
        return api.kb().then(function (idx) {
          if (!idx.disponible) {
            el.innerHTML = ui.banner('error',
              'La base de conocimiento no está disponible: el backend no encuentra <code>docs/</code>. ' +
              'Comprueba el montaje <code>../docs:/app/docs:ro</code> en docker-compose.yml.');
            return;
          }
          el.innerHTML = '<div class="kb">' +
            '<section class="panel kb-tree" id="kb-tree"></section>' +
            '<section class="panel" id="kb-doc"></section>' +
          '</div>';

          el.querySelector('#kb-tree').innerHTML = arbolKB(idx, soloPlaybooks);

          var inicial = params.get('doc');
          if (!inicial && params.get('cat')) {
            var cat = params.get('cat'), sub = params.get('sub');
            var clave = soloPlaybooks
              ? 'ataques/' + cat + '/' + sub + '/07-playbook-incident-response'
              : 'ataques/' + cat + '/' + sub + '/README';
            if (idx.documentos[clave]) inicial = clave;
          }
          if (!inicial) {
            var claves = Object.keys(idx.documentos).filter(function (k) {
              return soloPlaybooks ? idx.documentos[k].playbook : true;
            });
            inicial = claves[0];
          }

          el.addEventListener('click', function (ev) {
            var btn = ev.target.closest('.kb-doc');
            if (!btn) return;
            el.dataset.interactuado = '1';
            cargarDoc(el, btn.dataset.clave);
          });

          if (inicial) cargarDoc(el, inicial);
          else el.querySelector('#kb-doc').innerHTML = ui.vacio('Sin documentos', 'No hay nada que mostrar.');
        }).catch(function (e) {
          el.innerHTML = ui.banner('error', 'No se pudo cargar la base de conocimiento: ' + esc(e.message));
        });
      }
    };
  }

  function arbolKB(idx, soloPlaybooks) {
    var docs = idx.documentos;
    var html = Object.keys(idx.taxonomia).sort().map(function (cat) {
      var datos = idx.taxonomia[cat];
      var subs = Object.keys(datos.subcategorias).sort().map(function (sub) {
        var s = datos.subcategorias[sub];
        var claves = s.ataque.concat(s.defensa ? [s.defensa] : []);
        if (soloPlaybooks) claves = claves.filter(function (k) { return docs[k] && docs[k].playbook; });
        if (!claves.length) return '';
        return '<div class="kb-sub"><h4>' + esc(sub) + '</h4>' +
          claves.map(function (k) {
            var d = docs[k];
            if (!d) return '';
            return '<button class="kb-doc' + (d.playbook ? ' is-playbook' : '') +
              '" data-clave="' + esc(k) + '">' + esc(d.titulo) + '</button>';
          }).join('') + '</div>';
      }).join('');
      if (!subs) return '';
      var cabecera = !soloPlaybooks && datos.ataque_categoria
        ? '<button class="kb-doc" data-clave="' + esc(datos.ataque_categoria) + '">Visión de categoría</button>'
        : '';
      return '<div class="kb-cat"><h3>' + esc(cat) + '</h3>' + cabecera + subs + '</div>';
    }).join('');

    var huecos = (idx.sin_documentar || []).length
      ? '<div class="kb-cat"><h3>Sin documentación</h3>' +
        '<p style="font-size:12px;color:var(--ink-3);margin:0 0 6px">' +
        'Subcategorías con fixtures reales pero ningún documento escrito:</p>' +
        idx.sin_documentar.map(function (h) {
          return '<div style="font-size:12px;color:var(--ink-3);padding:2px 8px" class="mono">' +
            esc(h.subcategoria) + ' · ' + h.fixtures + ' fixtures</div>';
        }).join('') + '</div>'
      : '';

    return html + huecos;
  }

  function cargarDoc(el, clave) {
    var caja = el.querySelector('#kb-doc');
    caja.innerHTML = '<div class="doc">' + esqueleto() + '</div>';
    Array.prototype.forEach.call(el.querySelectorAll('.kb-doc'), function (b) {
      b.classList.toggle('is-active', b.dataset.clave === clave);
    });
    api.kbDoc(clave).then(function (doc) {
      caja.innerHTML = '<article class="doc">' + md.render(doc.contenido) + '</article>';
      // Solo se desplaza cuando el usuario ha elegido un documento. En la carga inicial
      // desplazar arrancaba la página a media altura, con la cabecera fuera de vista.
      if (el.dataset.interactuado === '1') caja.scrollIntoView({ block: 'nearest' });
    }).catch(function (e) {
      caja.innerHTML = ui.banner('error', 'No se pudo cargar el documento: ' + esc(e.message));
    });
  }

  V.conocimiento = vistaKB(false);
  V.playbook = vistaKB(true);

  // ======================================================================
  // Runs — comparación de corridas.
  // ======================================================================

  V.runs = {
    titulo: 'Corridas',
    subtitulo: 'Compara dos corridas de la batería componente a componente. Pone las columnas al lado; ' +
               'la lectura la hace quien mira.',
    render: function (el, params) {
      el.innerHTML = esqueleto();
      return api.runs().then(function (d) {
        if (!d.runs.length) {
          el.innerHTML = '<section class="panel"><div class="panel-body">' + ui.vacio(
            'Ninguna corrida capturada',
            'Las corridas aparecen aquí cuando la batería se ejecuta contra el backend.',
            '<div><code>make suite</code></div>'
          ) + '</div></section>';
          return;
        }
        var a = params.get('a'), b = params.get('b');
        var opciones = function (sel) {
          return d.runs.map(function (r) {
            return '<option value="' + esc(r.run_id) + '"' + (sel === r.run_id ? ' selected' : '') + '>' +
              esc(r.run_id) + ' (' + r.turnos + 'T)</option>';
          }).join('');
        };

        el.innerHTML = '<div class="stack">' +
          '<section class="panel"><div class="panel-head"><h2>Corridas capturadas</h2>' +
          '<span class="hint">' + d.runs.length + ' corridas</span></div>' +
          '<div class="panel-body">' + tablaRuns(d.runs) + '</div></section>' +
          '<section class="panel"><div class="filters">' +
            '<select id="cmp-a" aria-label="Corrida A"><option value="">Corrida A…</option>' + opciones(a) + '</select>' +
            '<span style="color:var(--ink-3)">frente a</span>' +
            '<select id="cmp-b" aria-label="Corrida B"><option value="">Corrida B…</option>' + opciones(b) + '</select>' +
          '</div><div class="panel-body" id="cmp-body">' +
            ui.vacio('Elige dos corridas', 'Selecciona una corrida en cada desplegable para compararlas.') +
          '</div></section>' +
        '</div>';

        var lanzar = function () {
          var va = el.querySelector('#cmp-a').value, vb = el.querySelector('#cmp-b').value;
          if (!va || !vb) return;
          if (va === vb) {
            el.querySelector('#cmp-body').innerHTML =
              ui.banner('warn', 'Has elegido la misma corrida dos veces.');
            return;
          }
          var caja = el.querySelector('#cmp-body');
          caja.innerHTML = esqueleto();
          api.compare(va, vb).then(function (c) { caja.innerHTML = comparacion(c); });
        };
        el.querySelector('#cmp-a').addEventListener('change', lanzar);
        el.querySelector('#cmp-b').addEventListener('change', lanzar);
        if (a && b) lanzar();
      });
    }
  };

  function tablaRuns(runs) {
    return '<div class="runs-wrap"><table class="runs"><thead><tr>' +
      '<th>Corrida</th><th>Origen</th><th>Inicio</th>' +
      '<th style="text-align:right">Turnos</th><th style="text-align:right">Sesiones</th>' +
      '<th style="text-align:right">Bloqueos</th><th style="text-align:right">Vulnerables</th>' +
      '</tr></thead><tbody>' + runs.map(function (r) {
        var href = '#/eventos?run_id=' + encodeURIComponent(r.run_id);
        return '<tr>' +
          '<td class="mono" style="font-size:12px"><a class="run-link" href="' + href +
            '" title="Abrir los Turns de esta corrida">' + esc(r.run_id) + '</a></td>' +
          '<td>' + esc(r.origen) + '</td>' +
          '<td class="mono" style="font-size:11.5px">' + ui.fecha(r.inicio) + '</td>' +
          '<td class="num">' + r.turnos + '</td>' +
          '<td class="num">' + r.sesiones + '</td>' +
          '<td class="num">' + (r.bloqueados || 0) + '</td>' +
          '<td class="num">' + (r.vulnerables || 0) + '</td>' +
        '</tr>';
      }).join('') + '</tbody></table></div>';
  }

  function comparacion(c) {
    var lado = function (l) {
      return '<div class="compare-side"><h3>' + esc(l.run_id) + '</h3>' +
        '<div class="panel-body">' +
          '<div class="station-counts" style="margin-bottom:12px">' +
            '<span><b>' + l.total_turnos + '</b> turnos</span>' +
            '<span><b>' + l.bloqueados + '</b> bloqueados</span>' +
            '<span><b>' + l.vulnerables + '</b> vulnerables</span>' +
          '</div>' +
        '</div>' +
        '<div class="panel-body flush">' + estaciones(l.componentes) + '</div>' +
        '<div class="panel-body"><table class="coverage"><thead><tr>' +
          '<th>Taxonomía</th><th style="text-align:right">Turnos</th>' +
          '<th style="text-align:right">Bloqueos</th>' +
        '</tr></thead><tbody>' +
          l.por_taxonomia.map(function (g) {
            return '<tr><td class="vector">' + esc(ui.vector(g.categoria)) +
              '<span class="sub">' + esc(g.subcategoria || '—') + '</span></td>' +
              '<td class="num">' + g.turnos + ' T</td>' +
              '<td class="num">' + g.bloqueados + ' block</td></tr>';
          }).join('') +
        '</tbody></table></div></div>';
    };
    return '<div class="compare">' + lado(c.a) + lado(c.b) + '</div>';
  }

  // ======================================================================
  // Alertas — triaje ligero. El único juicio del sistema, y es humano.
  // ======================================================================

  V.alertas = {
    titulo: 'Alertas',
    subtitulo: 'Un evento bloqueado o sospechoso por revisar. Marcar algo como descartado es un juicio — ' +
               'humano y trazable, nunca automático.',
    estado: '',
    render: function (el) {
      var self = this;
      el.innerHTML = esqueleto();
      return api.alerts(self.estado).then(function (d) {
        var filtro = '<div class="filters">' +
          ['', 'nueva', 'revisada', 'descartada'].map(function (e) {
            return '<button class="btn' + (self.estado === e ? ' is-active' : '') +
              '" data-estado="' + e + '">' + (e || 'Todas') + '</button>';
          }).join('') + '</div>';

        var cuerpo = d.alertas.length
          ? '<div class="alerts">' + cabeceraAlertas() + d.alertas.map(alerta).join('') + '</div>'
          : ui.vacio('Sin alertas',
              self.estado ? 'No hay alertas en estado «' + esc(self.estado) + '».'
                          : 'Ningún componente ha bloqueado ni marcado como sospechoso todavía.');

        el.innerHTML = '<section class="panel">' + filtro +
          '<div class="panel-body flush">' + cuerpo + '</div></section>';

        el.addEventListener('click', function (ev) {
          var f = ev.target.closest('[data-estado]');
          if (f && f.classList.contains('btn') && !f.dataset.alertId) {
            self.estado = f.dataset.estado;
            window.SOC.app.rerender();
            return;
          }
          var accion = ev.target.closest('[data-alert-id]');
          if (!accion) return;
          api.updateAlert(accion.dataset.alertId, { estado: accion.dataset.nuevo })
            .then(function () { window.SOC.app.rerender(); });
        });
      });
    }
  };

  function alerta(a) {
    return '<div class="alert is-' + esc(a.estado) + '">' +
      '<div><div class="alert-sev ' + esc(a.severidad) + '">' + esc(a.severidad) + '</div>' +
        '<span class="alert-origin">' + esc(a.severidad_origen) + '</span></div>' +
      '<div><div class="mono" style="font-size:12px">' + esc(a.componente) + '</div>' +
        '<div style="margin-top:4px">' + ui.tag(a.accion) + '</div></div>' +
      '<div><div style="font-size:13px">' + esc(a.razon || '—') + '</div>' +
        '<div class="mono" style="font-size:11px;color:var(--ink-3);margin-top:4px">' +
          esc(ui.recorta(ui.mensajeReal(a.prompt_extracto), 130)) + '</div>' +
        '<div style="margin-top:6px">' +
          '<a href="#/sesion?id=' + encodeURIComponent(a.session_id) + '" style="font-size:12px">ver sesión</a>' +
          (a.categoria ? ' · <a href="#/playbook?cat=' + encodeURIComponent(a.categoria) +
            '&sub=' + encodeURIComponent(a.subcategoria) + '" style="font-size:12px">playbook</a>' : '') +
        '</div></div>' +
      '<div class="alert-actions">' +
        (a.estado !== 'revisada'
          ? '<button class="btn" data-alert-id="' + a.id + '" data-nuevo="revisada">Revisada</button>' : '') +
        (a.estado !== 'descartada'
          ? '<button class="btn subtle" data-alert-id="' + a.id + '" data-nuevo="descartada">Descartar</button>' : '') +
        (a.estado !== 'nueva'
          ? '<button class="btn subtle" data-alert-id="' + a.id + '" data-nuevo="nueva">Reabrir</button>' : '') +
      '</div></div>';
  }

  function cabeceraAlertas() {
    return '<div class="alert-head">' +
      '<span>Severidad</span><span>Componente / acción</span>' +
      '<span>Hallazgo</span><span>Acciones</span>' +
    '</div>';
  }

  // ======================================================================

  function esqueleto() {
    return '<div style="padding:16px;display:flex;flex-direction:column;gap:9px">' +
      '<div class="skeleton" style="width:44%"></div>' +
      '<div class="skeleton" style="width:82%"></div>' +
      '<div class="skeleton" style="width:66%"></div>' +
      '<div class="skeleton" style="width:74%"></div></div>';
  }

  window.SOC.views = V;
})();
