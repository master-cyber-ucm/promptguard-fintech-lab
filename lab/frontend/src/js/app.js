/**
 * PromptGuard Lab — App principal.
 * Chat con Clara (estado VULNERABLE, sin defensas).
 */

import { sendMessage } from './api.js';
import { ATTACKS } from './attacks.js';


// --- State ---
let isSending = false;

// --- DOM ---
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const btnClear = document.getElementById('btn-clear');
const userSelect = document.getElementById('user-select');


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

    // Attack buttons
    document.querySelectorAll('.btn-attack').forEach(btn => {
        btn.addEventListener('click', () => {
            const attackKey = btn.dataset.attack;
            const attack = ATTACKS[attackKey];
            if (attack) {
                chatInput.value = attack.payload;
                chatInput.focus();
                // Auto-scroll textarea
                chatInput.scrollTop = chatInput.scrollHeight;
            }
        });
    });
}


// --- Send message ---
async function handleSend() {
    if (isSending) return;

    const message = chatInput.value.trim();
    if (!message) return;

    const userId = userSelect.value;
    const userName = userSelect.options[userSelect.selectedIndex].text;

    // Show user message
    addMessage('user', message, { userName });

    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';

    // Show loading
    const loadingEl = addLoading();

    try {
        isSending = true;
        btnSend.disabled = true;

        const response = await sendMessage(userId, message);

        // Remove loading
        loadingEl.remove();

        if (response.error) {
            addMessage('error', `Error: ${response.error}`);
        } else {
            addMessage('clara', response.response, {
                latency: response.latency_ms,
                model: response.model,
                tools: response.tools_used,
            });
        }
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
    const templateId = type === 'user' ? 'msg-user'
                     : type === 'error' ? 'msg-error'
                     : 'msg-clara';

    const template = document.getElementById(templateId);
    const msg = template.content.cloneNode(true);

    // Body
    const body = msg.querySelector('.msg-body');
    body.textContent = content;

    // Header (user name)
    if (type === 'user' && meta.userName) {
        const nameEl = msg.querySelector('.user-name');
        if (nameEl) nameEl.textContent = meta.userName;
    }

    // Meta
    const metaEl = msg.querySelector('.msg-meta');
    if (metaEl) {
        const parts = [];
        if (meta.latency) parts.push(`⏱ ${meta.latency.toFixed(0)}ms`);
        if (meta.model) parts.push(`🤖 ${meta.model.split('/').pop()}`);
        if (meta.tools && meta.tools.length > 0) {
            const toolNames = meta.tools.map(t => t.tool || t).join(', ');
            parts.push(`🔧 ${toolNames}`);
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
