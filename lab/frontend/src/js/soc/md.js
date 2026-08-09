/**
 * Renderizador Markdown mínimo para la base de conocimiento del SOC.
 *
 * El brief contemplaba vendorizar `marked`. Se descartó: los 71 documentos usan un
 * subconjunto acotado y regular de Markdown (encabezados, listas, tablas, código
 * vallado, citas, énfasis, enlaces, reglas), y escribirlo aquí evita meter en el
 * repositorio un blob de 40 KB que nadie va a revisar. Además da control total sobre
 * el escapado: todo entra escapado y solo salen las etiquetas que este fichero genera.
 *
 * Los bloques Mermaid NO se renderizan — se muestran como fuente etiquetada. Hacerlo
 * de verdad exigiría vendorizar ~2 MB y no compensa. Es una limitación declarada.
 */
window.SOC = window.SOC || {};

(function () {
  'use strict';

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Se aplica sobre texto YA escapado, así que no puede reintroducir etiquetas.
  function inline(s) {
    return s
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (_m, txt, href) {
        return /^(https?:|#)/.test(href)
          ? '<a href="' + href + '" target="_blank" rel="noopener">' + txt + '</a>'
          : '<span class="mono">' + txt + '</span>';   // rutas del repo: no son enlaces
      })
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>')
      .replace(/~~([^~]+)~~/g, '<del>$1</del>');
  }

  function tableRow(line, cell) {
    var cells = line.replace(/^\||\|$/g, '').split('|');
    return '<tr>' + cells.map(function (c) {
      return '<' + cell + '>' + inline(esc(c.trim())) + '</' + cell + '>';
    }).join('') + '</tr>';
  }

  function render(src) {
    var lines = String(src || '').replace(/\r\n/g, '\n').split('\n');
    var out = [];
    var i = 0;
    var listStack = [];

    function closeLists() {
      while (listStack.length) out.push('</' + listStack.pop() + '>');
    }

    while (i < lines.length) {
      var line = lines[i];

      // Código vallado
      var fence = line.match(/^```\s*(\w+)?/);
      if (fence) {
        closeLists();
        var lang = (fence[1] || '').toLowerCase();
        var buf = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
        i++;
        var esMermaid = lang === 'mermaid';
        out.push(
          (esMermaid ? '<div class="mermaid-note">diagrama Mermaid · se muestra el código fuente</div>' : '') +
          '<pre' + (esMermaid ? ' class="mermaid-src"' : '') + '><code>' + esc(buf.join('\n')) + '</code></pre>'
        );
        continue;
      }

      // Tabla
      if (/^\|/.test(line) && i + 1 < lines.length && /^\|[\s:|-]+\|?\s*$/.test(lines[i + 1])) {
        closeLists();
        var rows = ['<table><thead>' + tableRow(line, 'th') + '</thead><tbody>'];
        i += 2;
        while (i < lines.length && /^\|/.test(lines[i])) { rows.push(tableRow(lines[i], 'td')); i++; }
        out.push(rows.join('') + '</tbody></table>');
        continue;
      }

      var h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) {
        closeLists();
        var n = h[1].length;
        out.push('<h' + n + '>' + inline(esc(h[2])) + '</h' + n + '>');
        i++; continue;
      }

      if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(line)) { closeLists(); out.push('<hr />'); i++; continue; }

      if (/^>\s?/.test(line)) {
        closeLists();
        var quote = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) { quote.push(lines[i].replace(/^>\s?/, '')); i++; }
        out.push('<blockquote>' + render(quote.join('\n')) + '</blockquote>');
        continue;
      }

      var li = line.match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
      if (li) {
        var tipo = /\d/.test(li[2]) ? 'ol' : 'ul';
        var nivel = Math.floor(li[1].length / 2) + 1;
        while (listStack.length > nivel) out.push('</' + listStack.pop() + '>');
        while (listStack.length < nivel) { out.push('<' + tipo + '>'); listStack.push(tipo); }
        out.push('<li>' + inline(esc(li[3])) + '</li>');
        i++; continue;
      }

      if (!line.trim()) { closeLists(); i++; continue; }

      // Párrafo: acumula hasta la siguiente línea en blanco o construcción de bloque.
      closeLists();
      var para = [];
      while (i < lines.length && lines[i].trim() &&
             !/^(#{1,6}\s|>|```|\||\s*([-*+]|\d+\.)\s)/.test(lines[i])) {
        para.push(lines[i]); i++;
      }
      if (para.length) out.push('<p>' + inline(esc(para.join(' '))) + '</p>');
      else { out.push('<p>' + inline(esc(lines[i])) + '</p>'); i++; }
    }
    closeLists();
    return out.join('\n');
  }

  window.SOC.md = { render: render, esc: esc };
})();
