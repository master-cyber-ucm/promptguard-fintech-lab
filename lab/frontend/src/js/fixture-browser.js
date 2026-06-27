/**
 * Fixture Browser — lista los fixtures del lab en el side-panel del Playground.
 * Agrupa por attack category (LLM01/02/06/07) con acordeón colapsable.
 * Gestiona carga guiada para fixtures multi-step.
 */

const KIND_ICON = {
    'attack-prompts':    '⚔️',
    'legitimate-prompts': '✅',
    'navi-prompts':      '🔰',
};

const CAT_LABELS = {
    'LLM01': 'LLM01 · Prompt Injection',
    'LLM02': 'LLM02 · Info Disclosure',
    'LLM06': 'LLM06 · Excessive Agency',
    'LLM07': 'LLM07 · System Prompt Leakage',
    '_extensiones': 'Extensiones',
};

const CAT_ORDER = ['LLM01', 'LLM02', 'LLM06', 'LLM07', '_extensiones'];

// Pending multi-step state: null | { steps, nextIndex, fixture }
let _pending = null;
// Active fixture metadata for the current turn
let _activeFixture = null;

/** Devuelve los metadatos del fixture activo para incluir en el ChatRequest. */
export function getActiveFixtureMeta() {
    return _activeFixture;
}

/**
 * @param {Object} opts
 * @param {HTMLElement} opts.container  - el elemento donde se renderiza la lista
 * @param {Function}    opts.onLoadStep - callback(content: string) cuando se carga un step
 */
export function initFixtureBrowser({ container, onLoadStep }) {
    _render(container, onLoadStep);
}

/**
 * Llamar después de que se envía y recibe un mensaje.
 * Si hay un step pendiente de un fixture multi-step, lo carga en el textarea.
 * @param {Function} onLoadStep
 */
export function advancePendingStep(onLoadStep) {
    if (!_pending) { _activeFixture = null; return; }
    const step = _pending.steps[_pending.nextIndex];
    if (!step) { _pending = null; _activeFixture = null; return; }

    _activeFixture = _pending.fixture;
    _pending.nextIndex++;
    if (_pending.nextIndex >= _pending.steps.length) _pending = null;

    onLoadStep(step.content);
}

async function _render(container, onLoadStep) {
    container.innerHTML = '<p class="text-muted fb-loading">Cargando fixtures…</p>';

    let data;
    try {
        data = await window.VB.API.getFixtures();
    } catch (_) {
        container.innerHTML = '<p class="text-muted">⚠️ Error cargando fixtures.</p>';
        return;
    }

    const byCategory = {};
    for (const f of data.fixtures || []) {
        const cat = f.category || '_extensiones';
        (byCategory[cat] = byCategory[cat] || []).push(f);
    }

    container.innerHTML = '';

    for (const cat of CAT_ORDER) {
        const items = byCategory[cat];
        if (!items || items.length === 0) continue;

        const group = document.createElement('div');
        group.className = 'fixture-group';

        const header = document.createElement('button');
        header.className = 'fixture-group-header';
        header.textContent = CAT_LABELS[cat] || cat;
        header.setAttribute('aria-expanded', 'true');

        const list = document.createElement('div');
        list.className = 'fixture-list';

        for (const fixture of items) {
            list.appendChild(_makeItem(fixture, onLoadStep));
        }

        header.addEventListener('click', () => {
            const collapsed = list.classList.toggle('fixture-list--collapsed');
            header.setAttribute('aria-expanded', String(!collapsed));
        });

        group.appendChild(header);
        group.appendChild(list);
        container.appendChild(group);
    }
}

function _makeItem(fixture, onLoadStep) {
    const div = document.createElement('div');
    div.className = 'fixture-item';

    const btn = document.createElement('button');
    btn.className = 'btn-fixture';
    if (fixture.severity === 'CRITICAL') btn.classList.add('btn-fixture--critical');
    else if (fixture.severity === 'HIGH')     btn.classList.add('btn-fixture--high');

    const subcategory = fixture.attack ? fixture.attack.split('/').pop() : '';
    const kindIcon = KIND_ICON[fixture.kind] || '?';
    const isMulti = fixture.type === 'multi-step' && (fixture.rendered_steps || []).length > 1;

    btn.innerHTML =
        `<span class="fb-icon">${kindIcon}</span>` +
        `<span class="fb-name">${fixture.name}${isMulti ? ' <small>(multi)</small>' : ''}</span>` +
        (fixture.severity !== 'LOW'
            ? `<span class="fb-sev fb-sev--${fixture.severity.toLowerCase()}">${fixture.severity}</span>`
            : '');

    btn.title = [fixture.description, subcategory ? `· ${subcategory}` : ''].filter(Boolean).join(' ');

    btn.addEventListener('click', () => {
        const steps = fixture.rendered_steps || [];
        if (steps.length === 0) return;

        _activeFixture = {
            fixture_id: fixture.id,
            fixture_kind: fixture.kind,
            fixture_expected_result: fixture.expected_result,
        };

        _pending = null;
        if (isMulti) {
            _pending = { steps, nextIndex: 1, fixture: _activeFixture };
        }

        onLoadStep(steps[0].content);

        document.querySelectorAll('.btn-fixture').forEach(b => b.classList.remove('btn-fixture--active'));
        btn.classList.add('btn-fixture--active');
    });

    div.appendChild(btn);
    return div;
}
