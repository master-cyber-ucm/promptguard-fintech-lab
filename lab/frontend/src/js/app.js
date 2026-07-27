/**
 * PromptGuard Lab — App principal.
 * Chat con Clara (estado VULNERABLE, sin defensas).
 */

import { initFixtureBrowser, advancePendingStep, getActiveFixtureMeta } from './fixture-browser.js';


// --- State ---
let isSending = false;
const SESSION_ID = `ses_${Date.now()}`;

// --- DOM ---
const chatMessages   = document.getElementById('chat-messages');
const chatInput      = document.getElementById('chat-input');
const btnSend        = document.getElementById('btn-send');
const btnClear       = document.getElementById('btn-clear');
const userSelect     = document.getElementById('user-select');
const modeSelectEl   = document.getElementById('mode-select');
const documentAttach = document.getElementById('document-attach');
const documentInput  = document.getElementById('document-input');
const documentName   = document.getElementById('document-filename');
const defensasPanel  = document.getElementById('defensas-panel');
const defensaCheckboxes = {
    estructural:         document.getElementById('defensa-estructural'),
    sanitizer:            document.getElementById('defensa-sanitizer'),
    separacionSemantica: document.getElementById('defensa-separacion-semantica'),
    toolGatekeeper:      document.getElementById('defensa-tool-gatekeeper'),
};


// --- Init ---
function init() {
    btnSend.addEventListener('click', handleSend);
    btnClear.addEventListener('click', handleClear);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    if (modeSelectEl) {
        modeSelectEl.addEventListener('change', updateDocumentAttachVisibility);
        updateDocumentAttachVisibility();
    }
    if (documentInput) {
        documentInput.addEventListener('change', () => {
            const f = documentInput.files[0];
            documentName.textContent = f ? f.name : '';
        });
    }

    initFixtureBrowser({
        container: document.getElementById('fixture-list'),
        onLoadStep: (content) => {
            chatInput.value = content;
            chatInput.focus();
            chatInput.scrollTop = chatInput.scrollHeight;
        },
    });
}


function updateDocumentAttachVisibility() {
    if (!documentAttach || !modeSelectEl) return;
    const isDocumentMode = modeSelectEl.value === 'complex-with-document';
    documentAttach.style.display = isDocumentMode ? 'flex' : 'none';
    if (defensasPanel) defensasPanel.style.display = isDocumentMode ? 'flex' : 'none';
}


function getDefensasFromUI() {
    const d = {};
    for (const key in defensaCheckboxes) {
        const el = defensaCheckboxes[key];
        d[key] = el ? el.checked : true;
    }
    return d;
}


// --- Send message ---
async function handleSend() {
    if (isSending) return;

    const message = chatInput.value.trim();
    if (!message) return;

    const endpoint = modeSelectEl ? modeSelectEl.value : null;
    const isDocumentMode = endpoint === 'complex-with-document';

    const documentFile = isDocumentMode && documentInput ? documentInput.files[0] : null;
    if (isDocumentMode && !documentFile) {
        alert('Selecciona un documento (PDF/DOCX/XLSX) para adjuntar antes de enviar.');
        return;
    }

    const userId   = userSelect.value;
    const userName = userSelect.options[userSelect.selectedIndex].text;

    const userMessageDisplay = documentFile ? `${message}\n📎 ${documentFile.name}` : message;
    addMessage('user', userMessageDisplay, { userName });
    chatInput.value = '';
    chatInput.style.height = 'auto';

    const loadingEl = addLoading();

    try {
        isSending = true;
        btnSend.disabled = true;

        const response = documentFile
            ? await window.VB.API.sendMessageWithDocument(userId, SESSION_ID, message, documentFile, getActiveFixtureMeta(), getDefensasFromUI())
            : await window.VB.API.sendMessage(userId, SESSION_ID, message, getActiveFixtureMeta(), endpoint);

        if (documentInput) { documentInput.value = ''; documentName.textContent = ''; }

        loadingEl.remove();

        if (response.error) {
            addMessage('error', `Error: ${response.error}`);
        } else {
            addMessage('clara', response.response, {
                latency: response.latency_ms,
                model:   response.model,
                tools:   response.tools_used,
            });
        }

        // If a multi-step fixture is active, auto-load the next step
        advancePendingStep((content) => {
            chatInput.value = content;
            chatInput.focus();
        });
    } catch (err) {
        loadingEl.remove();
        addMessage('error', `Error de conexión: ${err.message}`);
    } finally {
        isSending = false;
        btnSend.disabled = false;
        chatInput.focus();
    }
}


// --- UI helpers ---

function addMessage(type, content, meta = {}) {
    const templateId = type === 'user'  ? 'msg-user'
                     : type === 'error' ? 'msg-error'
                     : 'msg-clara';

    const template = document.getElementById(templateId);
    const msg = template.content.cloneNode(true);

    msg.querySelector('.msg-body').textContent = content;

    if (type === 'user' && meta.userName) {
        const nameEl = msg.querySelector('.user-name');
        if (nameEl) nameEl.textContent = meta.userName;
    }

    const metaEl = msg.querySelector('.msg-meta');
    if (metaEl) {
        const parts = [];
        if (meta.latency) parts.push(`⏱ ${meta.latency.toFixed(0)}ms`);
        if (meta.model)   parts.push(`🤖 ${meta.model.split('/').pop()}`);
        if (meta.tools && meta.tools.length > 0) {
            parts.push(`🔧 ${meta.tools.map(t => t.tool || t).join(', ')}`);
        }
        metaEl.textContent = parts.join(' · ');
    }

    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return msg;
}


function addLoading() {
    const div = document.createElement('div');
    div.className = 'message message-clara';
    div.id = 'loading-msg';
    div.innerHTML = `
        <div class="msg-header">🤖 <strong>Clara</strong></div>
        <div class="msg-body">
            <div class="loading"><span></span><span></span><span></span></div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}


function handleClear() {
    chatMessages.innerHTML = `
        <div class="system-message">
            <p>🏦 <strong>Chat limpiado</strong></p>
            <p>Soy Clara, tu asistente virtual. ¿En qué puedo ayudarte?</p>
        </div>
    `;
}


// --- Boot ---
document.addEventListener('DOMContentLoaded', init);
