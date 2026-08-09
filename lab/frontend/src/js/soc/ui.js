/** Piezas visuales compartidas del SOC. */
window.SOC = window.SOC || {};

(function () {
  'use strict';

  var esc = window.SOC.md.esc;

  // Orden canónico del pipeline. La cadena de una fila SIEMPRE tiene estas seis
  // ranuras en este orden: que no se muevan es lo que permite comparar dos turnos
  // de un vistazo y ver dónde hay hueco.
  var COMPONENTES = [
    'input_sanitizer', 'pii_shield', 'document_sanitizer',
    'tool_gatekeeper', 'output_auditor', 'leak_guard'
  ];

  var CLASE = { ALLOW: 'allow', SUSPICIOUS: 'susp', BLOCK: 'block' };

  function claseAccion(a) { return CLASE[a] || 'neutral'; }

  /** Etiqueta de acción: color + forma + texto. Nunca solo color. */
  function tag(accion) {
    return '<span class="tag ' + claseAccion(accion) + '">' + esc(accion) + '</span>';
  }

  /**
   * Cadena de seis posiciones: relleno = evaluó, hueco punteado = no evaluó.
   * Sin desplegar nada se ve a la vez la cobertura y el desenlace — y un turno en
   * modo vulnerable son seis puntos vacíos en fila.
   */
  function chain(eventos) {
    var peor = {};
    (eventos || []).forEach(function (e) {
      var actual = peor[e.componente];
      var rango = { ALLOW: 1, SUSPICIOUS: 2, BLOCK: 3 };
      if (!actual || (rango[e.accion] || 0) > (rango[actual] || 0)) peor[e.componente] = e.accion;
    });
    var celdas = COMPONENTES.map(function (c) {
      var a = peor[c];
      var cls = a ? claseAccion(a) : 'absent';
      var txt = c + ': ' + (a || 'no evaluó este turno');
      return '<i class="' + cls + '" title="' + esc(txt) + '"></i>';
    }).join('');
    var resumen = COMPONENTES.map(function (c) {
      return c + '=' + (peor[c] || 'ausente');
    }).join(', ');
    return '<span class="chain" role="img" aria-label="' + esc(resumen) + '">' + celdas + '</span>';
  }

  function hora(ts) {
    if (!ts) return '—';
    var d = new Date(ts);
    if (isNaN(d)) return String(ts).slice(11, 19);
    return d.toLocaleTimeString('es-ES', { hour12: false });
  }

  function fecha(ts) {
    if (!ts) return '—';
    var d = new Date(ts);
    return isNaN(d) ? String(ts) : d.toLocaleString('es-ES', { hour12: false });
  }

  /**
   * Las defensas deterministas deciden en decenas de microsegundos: redondear a
   * milisegundos enteros las convertía todas en un "0 ms" que parecía un fallo de
   * captura. Que un componente tarde 0.02 ms es justamente lo que hay que poder leer.
   */
  function ms(v) {
    if (v === null || v === undefined) return '—';
    if (v >= 1000) return (v / 1000).toFixed(2) + ' s';
    if (v >= 10) return Math.round(v) + ' ms';
    if (v >= 0.01) return v.toFixed(2) + ' ms';
    return '<0.01 ms';
  }

  /**
   * El mensaje real del cliente, sin el bloque de contexto que el backend antepone.
   * Sin esto todas las filas del stream empiezan igual ("[Contexto del usuario
   * autenticado: user_id=…") y el stream deja de servir para orientarse de un vistazo.
   */
  function mensajeReal(prompt) {
    var s = String(prompt || '');
    var marca = s.indexOf('Mensaje del cliente:');
    if (marca !== -1) return s.slice(marca + 'Mensaje del cliente:'.length).trim();
    return s.replace(/^\[Contexto del usuario autenticado:[^\]]*\]\s*/, '').trim();
  }

  function recorta(s, n) {
    s = String(s || '');
    return s.length > n ? s.slice(0, n) + '…' : s;
  }

  function vacio(titulo, cuerpo, pistas) {
    return '<div class="empty"><h3>' + esc(titulo) + '</h3><p>' + cuerpo + '</p>' +
      (pistas ? '<div class="hints">' + pistas + '</div>' : '') + '</div>';
  }

  function banner(tipo, texto) {
    return '<div class="banner ' + tipo + '">' + texto + '</div>';
  }

  /** Nombre legible de un vector a partir de su categoría OWASP. */
  var VECTORES = {
    'LLM01-prompt-injection': 'Prompt Injection',
    'LLM02-sensitive-information-disclosure': 'Divulgación de datos sensibles',
    'LLM06-excessive-agency': 'Excessive Agency',
    'LLM07-system-prompt-leakage': 'System Prompt Leakage',
    '_extensiones': 'Extensiones'
  };
  function vector(cat) { return VECTORES[cat] || cat || 'sin taxonomía'; }

  window.SOC.ui = {
    COMPONENTES: COMPONENTES,
    claseAccion: claseAccion,
    tag: tag,
    chain: chain,
    hora: hora,
    fecha: fecha,
    ms: ms,
    mensajeReal: mensajeReal,
    recorta: recorta,
    vacio: vacio,
    banner: banner,
    vector: vector,
    esc: esc
  };
})();
