/**
 * Fixture Editor — formulario modal de autoría de fixtures desde el Playground.
 *
 * Toma la conversación capturada (los turns que el usuario envió a Clara) como
 * steps candidatos, deja configurar metadatos y el bloque de evaluación, y
 * persiste el Fixture Draft vía POST /api/v1/fixtures.
 */

import { refreshFixtureBrowser } from './fixture-browser.js';

const CATEGORIES = ['LLM01', 'LLM02', 'LLM06', 'LLM07', '_extensiones'];
const KINDS = ['attack-prompts', 'legitimate-prompts', 'navi-prompts'];
const ID_PREFIX = {
    'attack-prompts': 'atk',
    'legitimate-prompts': 'leg',
    'navi-prompts': 'navi',
};
const SEVERITIES = ['CRITICAL', 'HIGH', 'LOW'];
const EXPECTED = ['BLOCK', 'ALLOW', 'REFUSE'];

// Regexes para sugerir indicadores desde la respuesta de Clara.
const SUGGESTION_PATTERNS = [
    /\bES\d{22}\b/g,                     // IBAN
    /\b(?:pg_internal_sk_|sk_)[A-Za-z0-9]+\b/g,  // secretos / API keys
    /\bVULNERABILIDAD\b/g,
    /\bAPI_KEY_INTERNAL\b/g,
    /\bdb-[a-z0-9.\-]+\b/g,              // hosts internos
    /\bs3:\/\/[a-z0-9.\-\/]+/g,          // buckets
];

let _overlay = null;

/**
 * @param {Object} opts
 * @param {Array<{content:string}>} opts.capturedSteps  turns enviados por el usuario
 * @param {string}  opts.lastResponse  última respuesta de Clara (para sugerencias)
 * @param {Array}   opts.lastTools     tools invocadas (para sugerencias)
 */
export async function openFixtureEditor({ capturedSteps, lastResponse, lastTools }) {
    let existing = [];
    try {
        const data = await window.VB.API.getFixtures();
        existing = data.fixtures || [];
    } catch (_) { /* seguimos sin sugerencias de id/subcat */ }

    const subcatsByCat = _subcatsByCategory(existing);
    const steps = (capturedSteps && capturedSteps.length)
        ? capturedSteps.map(s => s.content)
        : [''];

    _buildModal({ existing, subcatsByCat, steps, lastResponse: lastResponse || '', lastTools: lastTools || [] });
}

// ── derivar categorías/subcategorías del árbol existente ──────────────────────
function _subcatsByCategory(fixtures) {
    const map = {};
    for (const cat of CATEGORIES) map[cat] = new Set();
    for (const f of fixtures) {
        const attack = f.attack || '';
        const parts = attack.split('/');
        if (parts.length < 2) continue;
        const catDir = parts[0];
        const code = catDir.startsWith('LLM') ? catDir.split('-')[0] : catDir;
        if (map[code]) map[code].add(parts[1]);
    }
    const out = {};
    for (const cat of CATEGORIES) out[cat] = Array.from(map[cat]).sort();
    return out;
}

function _nextId(fixtures, kind) {
    const prefix = ID_PREFIX[kind];
    let max = 0;
    for (const f of fixtures) {
        const m = (f.id || '').match(new RegExp('^' + prefix + '_(\\d+)$'));
        if (m) max = Math.max(max, parseInt(m[1], 10));
    }
    return `${prefix}_${String(max + 1).padStart(3, '0')}`;
}

function _suggestions(lastResponse, lastTools) {
    const out = [];
    const seen = new Set();
    for (const re of SUGGESTION_PATTERNS) {
        const matches = lastResponse.match(re) || [];
        for (const m of matches) {
            const key = 'rc:' + m;
            if (!seen.has(key)) { seen.add(key); out.push({ type: 'response_contains', value: m }); }
        }
    }
    for (const t of lastTools) {
        const tool = t.tool || t;
        const key = 'tc:' + tool;
        if (tool && !seen.has(key)) { seen.add(key); out.push({ type: 'tool_called', tool }); }
    }
    return out;
}

// ── construcción del modal ────────────────────────────────────────────────────
function _el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
}

function _option(value, label, selected) {
    const o = document.createElement('option');
    o.value = value;
    o.textContent = label || value;
    if (selected) o.selected = true;
    return o;
}

function _buildModal({ existing, subcatsByCat, steps, lastResponse, lastTools }) {
    closeFixtureEditor();

    _overlay = _el('div', 'fe-overlay');
    const modal = _el('div', 'fe-modal');
    _overlay.appendChild(modal);

    modal.appendChild(_el('div', 'fe-header',
        '<h3>💾 Guardar como fixture</h3><button class="fe-close" title="Cerrar">✕</button>'));

    const body = _el('div', 'fe-body');
    modal.appendChild(body);

    // --- Metadatos: category / subcategory / kind ---
    const rowCat = _el('div', 'fe-row');
    const selCat = _el('select', 'fe-input');
    CATEGORIES.forEach(c => selCat.appendChild(_option(c, c === '_extensiones' ? 'Extensiones' : c, c === 'LLM01')));
    const selKind = _el('select', 'fe-input');
    KINDS.forEach(k => selKind.appendChild(_option(k, k, k === 'attack-prompts')));

    // Subcategory: select + "+ nueva" → input
    const selSub = _el('select', 'fe-input');
    const inpSubNew = _el('input', 'fe-input fe-hidden');
    inpSubNew.placeholder = 'nueva-subcategoria';

    function refreshSubcats() {
        selSub.innerHTML = '';
        (subcatsByCat[selCat.value] || []).forEach(s => selSub.appendChild(_option(s, s)));
        selSub.appendChild(_option('__new__', '➕ nueva subcategoría…'));
        _toggleNewSub();
    }
    function _toggleNewSub() {
        const isNew = selSub.value === '__new__';
        inpSubNew.classList.toggle('fe-hidden', !isNew);
    }
    selSub.addEventListener('change', _toggleNewSub);

    rowCat.appendChild(_field('Category', selCat));
    rowCat.appendChild(_field('Subcategory', _wrap([selSub, inpSubNew])));
    rowCat.appendChild(_field('Kind', selKind));
    body.appendChild(rowCat);

    // --- id / name ---
    const rowId = _el('div', 'fe-row');
    const inpId = _el('input', 'fe-input');
    const inpName = _el('input', 'fe-input');
    inpName.placeholder = 'nombre_descriptivo';
    function refreshId() { inpId.value = _nextId(existing, selKind.value); }
    rowId.appendChild(_field('id', inpId));
    rowId.appendChild(_field('name', inpName));
    body.appendChild(rowId);

    // --- severity / expected_result ---
    const rowSev = _el('div', 'fe-row');
    const selSev = _el('select', 'fe-input');
    SEVERITIES.forEach(s => selSev.appendChild(_option(s, s, s === 'HIGH')));
    const selExp = _el('select', 'fe-input');
    EXPECTED.forEach(e => selExp.appendChild(_option(e, e, e === 'BLOCK')));
    rowSev.appendChild(_field('severity', selSev));
    rowSev.appendChild(_field('expected_result', selExp));
    body.appendChild(rowSev);

    // --- description ---
    const inpDesc = _el('input', 'fe-input');
    inpDesc.placeholder = 'Breve descripción del ataque o petición';
    body.appendChild(_field('description', inpDesc, true));

    // --- steps ---
    body.appendChild(_el('div', 'fe-section-title', 'Steps <small>(turns del usuario)</small>'));
    const stepsBox = _el('div', 'fe-steps');
    body.appendChild(stepsBox);
    function addStep(content) {
        const wrap = _el('div', 'fe-step');
        const ta = _el('textarea', 'fe-input fe-step-text');
        ta.value = content || '';
        ta.rows = 2;
        const del = _el('button', 'fe-icon-btn', '🗑');
        del.title = 'Eliminar step';
        del.addEventListener('click', () => { wrap.remove(); _renumberSteps(stepsBox); });
        wrap.appendChild(_el('span', 'fe-step-num', ''));
        wrap.appendChild(ta);
        wrap.appendChild(del);
        stepsBox.appendChild(wrap);
        _renumberSteps(stepsBox);
    }
    steps.forEach(addStep);
    const btnAddStep = _el('button', 'fe-add', '➕ añadir step');
    btnAddStep.addEventListener('click', () => addStep(''));
    body.appendChild(btnAddStep);

    // --- evaluation ---
    body.appendChild(_el('div', 'fe-section-title', 'Evaluación'));
    const rowMethod = _el('div', 'fe-method');
    rowMethod.innerHTML =
        '<label><input type="radio" name="fe-method" value="deterministic" checked> determinista</label>' +
        '<label><input type="radio" name="fe-method" value="llm"> juez (llm)</label>';
    body.appendChild(rowMethod);

    // Deterministic panel: event rows + suggestions
    const detPanel = _el('div', 'fe-eval-panel');
    const eventsBox = _el('div', 'fe-events');
    detPanel.appendChild(eventsBox);
    function addEvent(ev) {
        const row = _el('div', 'fe-event');
        const selType = _el('select', 'fe-input fe-event-type');
        ['response_contains', 'tool_called', 'tool_called_with'].forEach(t =>
            selType.appendChild(_option(t, t, ev && ev.type === t)));
        const inpVal = _el('input', 'fe-input fe-event-val');
        function syncPlaceholder() {
            inpVal.placeholder = selType.value === 'response_contains' ? 'texto que delata la brecha' : 'nombre de la tool';
        }
        selType.addEventListener('change', syncPlaceholder);
        syncPlaceholder();
        if (ev) inpVal.value = ev.value || ev.tool || '';
        const del = _el('button', 'fe-icon-btn', '🗑');
        del.addEventListener('click', () => row.remove());
        row.appendChild(selType);
        row.appendChild(inpVal);
        row.appendChild(del);
        eventsBox.appendChild(row);
    }
    const btnAddEvent = _el('button', 'fe-add', '➕ añadir evento');
    btnAddEvent.addEventListener('click', () => addEvent(null));
    detPanel.appendChild(btnAddEvent);

    // suggestions chips
    const suggestions = _suggestions(lastResponse, lastTools);
    if (suggestions.length) {
        const chipBox = _el('div', 'fe-chips');
        chipBox.appendChild(_el('span', 'fe-chips-label', 'Sugerencias de la respuesta:'));
        suggestions.forEach(s => {
            const label = s.type === 'tool_called' ? `🔧 ${s.tool}` : `"${_truncate(s.value, 24)}"`;
            const chip = _el('button', 'fe-chip', label);
            chip.title = 'Añadir como evento';
            chip.addEventListener('click', () => addEvent(s));
            chipBox.appendChild(chip);
        });
        detPanel.appendChild(chipBox);
    }
    addEvent(suggestions[0] || null);  // empezar con una fila

    // LLM panel
    const llmPanel = _el('div', 'fe-eval-panel fe-hidden');
    const taQuestion = _el('textarea', 'fe-input');
    taQuestion.rows = 2;
    taQuestion.placeholder = '¿El agente hizo lo que debía? (pregunta SI/NO para el juez)';
    llmPanel.appendChild(_field('question', taQuestion, true));
    const selSystem = _el('select', 'fe-input');
    selSystem.appendChild(_option('neutral', 'neutral (calidad de servicio)'));
    selSystem.appendChild(_option('security', 'security (fuga / violación de regla)'));
    llmPanel.appendChild(_field('judge.system', selSystem, true));
    body.appendChild(detPanel);
    body.appendChild(llmPanel);

    rowMethod.querySelectorAll('input[name="fe-method"]').forEach(r =>
        r.addEventListener('change', () => {
            const m = rowMethod.querySelector('input[name="fe-method"]:checked').value;
            detPanel.classList.toggle('fe-hidden', m !== 'deterministic');
            llmPanel.classList.toggle('fe-hidden', m !== 'llm');
        }));

    // --- footer / actions ---
    const footer = _el('div', 'fe-footer');
    const status = _el('div', 'fe-status', '');
    const btnCancel = _el('button', 'btn btn-secondary', 'Cancelar');
    const btnSave = _el('button', 'btn btn-primary', 'Guardar fixture');
    footer.appendChild(status);
    footer.appendChild(btnCancel);
    footer.appendChild(btnSave);
    modal.appendChild(footer);

    // init dependent widgets
    refreshSubcats();
    refreshId();
    selCat.addEventListener('change', refreshSubcats);
    selKind.addEventListener('change', refreshId);

    // --- events ---
    modal.querySelector('.fe-close').addEventListener('click', closeFixtureEditor);
    btnCancel.addEventListener('click', closeFixtureEditor);
    _overlay.addEventListener('click', (e) => { if (e.target === _overlay) closeFixtureEditor(); });

    btnSave.addEventListener('click', async () => {
        const method = rowMethod.querySelector('input[name="fe-method"]:checked').value;
        const subcategory = selSub.value === '__new__' ? inpSubNew.value.trim() : selSub.value;
        const stepEls = Array.from(stepsBox.querySelectorAll('.fe-step-text'));
        const draft = {
            category: selCat.value,
            subcategory,
            kind: selKind.value,
            id: inpId.value.trim(),
            name: inpName.value.trim(),
            severity: selSev.value,
            expected_result: selExp.value,
            description: inpDesc.value.trim(),
            steps: stepEls.map(ta => ({ content: ta.value.trim() })).filter(s => s.content),
            evaluation: method === 'deterministic'
                ? {
                    method: 'deterministic',
                    events: Array.from(eventsBox.querySelectorAll('.fe-event')).map(row => {
                        const type = row.querySelector('.fe-event-type').value;
                        const val = row.querySelector('.fe-event-val').value.trim();
                        return type === 'response_contains' ? { type, value: val } : { type, tool: val };
                    }).filter(e => (e.value || e.tool)),
                }
                : { method: 'llm', question: taQuestion.value.trim(), system: selSystem.value },
        };

        status.textContent = 'Guardando…';
        status.className = 'fe-status';
        btnSave.disabled = true;
        try {
            const res = await window.VB.API.createFixture(draft);
            status.textContent = `✅ Guardado: ${res.path}`;
            status.className = 'fe-status fe-status--ok';
            refreshFixtureBrowser();
            setTimeout(closeFixtureEditor, 1200);
        } catch (err) {
            status.textContent = `❌ ${err.message}`;
            status.className = 'fe-status fe-status--err';
            btnSave.disabled = false;
        }
    });

    document.body.appendChild(_overlay);
    inpName.focus();
}

export function closeFixtureEditor() {
    if (_overlay) { _overlay.remove(); _overlay = null; }
}

// ── helpers de layout ─────────────────────────────────────────────────────────
function _field(label, control, full) {
    const wrap = _el('div', full ? 'fe-field fe-field--full' : 'fe-field');
    wrap.appendChild(_el('label', 'fe-label', label));
    wrap.appendChild(control);
    return wrap;
}

function _wrap(children) {
    const w = _el('div', 'fe-subwrap');
    children.forEach(c => w.appendChild(c));
    return w;
}

function _renumberSteps(box) {
    Array.from(box.querySelectorAll('.fe-step')).forEach((el, i) => {
        const num = el.querySelector('.fe-step-num');
        if (num) num.textContent = `T${i + 1}`;
    });
}

function _truncate(s, n) { return s.length > n ? s.slice(0, n) + '…' : s; }
