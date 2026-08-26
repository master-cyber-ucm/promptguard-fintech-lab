/**
 * VerdaBank Full Chat View — estilo corporativo.
 */

window.VB = window.VB || {};
window.VB.Views = window.VB.Views || {};

(function() {

    var ICON = window.VB.Views._icons || {};
    var sidebar = window.VB.Views._sidebar || function() { return ''; };


    window.VB.Views.chat = function() {
        var user = VB.getState('user');
        if (!user) { VB.navigate('/'); return; }

        var firstName = user.name.split(' ')[0];

        var app = document.getElementById('app');
        app.innerHTML =
            '<div class="dashboard">' +
                sidebar(user, 'chat') +
                '<div class="main-content">' +
                    '<div class="page-header">' +
                        '<div style="display:flex;align-items:center;gap:10px">' +
                            '<div style="width:36px;height:36px;border-radius:50%;background:var(--primary-light);color:var(--primary);display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700">CL</div>' +
                            '<div>' +
                                '<h1 style="font-size:1.1rem;margin:0">Clara</h1>' +
                                '<p style="margin:0;font-size:0.78rem;color:var(--text-tertiary)">Asistente virtual VerdaBank</p>' +
                            '</div>' +
                        '</div>' +
                    '</div>' +
                    '<div class="full-chat-page">' +
                        '<div class="full-chat-container">' +
                            '<div id="full-chat-messages" class="full-chat-messages">' +
                                '<div class="fc-msg-welcome">' +
                                    '<h3>Hola, ' + firstName + '</h3>' +
                                    '<p>Soy Clara, tu asistente virtual de VerdaBank. Puedo ayudarte con consultas de saldo, transferencias, bloqueo de tarjetas y mas.</p>' +
                                '</div>' +
                            '</div>' +
                            '<div class="full-chat-input">' +
                                '<textarea id="full-chat-input" placeholder="Escribe tu mensaje..." rows="1"></textarea>' +
                                '<button id="full-chat-send">Enviar</button>' +
                            '</div>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>';

        initFullChat(user);
    };


    function initFullChat(user) {
        var messages = document.getElementById('full-chat-messages');
        var input = document.getElementById('full-chat-input');
        var sendBtn = document.getElementById('full-chat-send');
        if (!messages || !input || !sendBtn) return;

        var sending = false;

        input.addEventListener('input', function() {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        });

        sendBtn.addEventListener('click', handleSend);
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
        });

        function handleSend() {
            if (sending) return;
            var msg = input.value.trim();
            if (!msg) return;

            var t = new Date().toLocaleTimeString('es-ES', {hour:'2-digit', minute:'2-digit'});

            messages.innerHTML +=
                '<div class="fc-msg fc-msg-user">' + esc(msg) +
                '<div class="fc-msg-meta">' + t + '</div></div>';

            input.value = '';
            input.style.height = 'auto';
            messages.scrollTop = messages.scrollHeight;

            var lid = 'fl' + Date.now();
            messages.innerHTML += '<div id="' + lid + '" class="fc-msg fc-msg-clara" style="color:var(--text-tertiary)">...</div>';
            messages.scrollTop = messages.scrollHeight;

            sending = true;
            sendBtn.disabled = true;
            var start = Date.now();

            VB.API.sendMessage(user.id, 'ses_' + Date.now(), msg)
                .then(function(resp) {
                    var lat = Date.now() - start;
                    var el = document.getElementById(lid);
                    if (el) el.remove();

                    if (resp.error) {
                        messages.innerHTML += '<div class="fc-msg fc-msg-clara"><em style="color:var(--danger)">' + esc(resp.error) + '</em><div class="fc-msg-meta">' + lat + 'ms</div></div>';
                    } else {
                        var tm = '';
                        if (resp.tools_used && resp.tools_used.length > 0) {
                            tm = ' / ' + resp.tools_used.map(function(t) { return t.tool || t; }).join(', ');
                        }
                        messages.innerHTML +=
                            '<div class="fc-msg fc-msg-clara">' + esc(resp.response || '') +
                            '<div class="fc-msg-meta">' + lat + 'ms' + tm + '</div></div>';
                    }
                })
                .catch(function(err) {
                    var el = document.getElementById(lid);
                    if (el) el.remove();
                    messages.innerHTML += '<div class="fc-msg fc-msg-clara"><em style="color:var(--danger)">Error: ' + esc(err.message) + '</em></div>';
                })
                .finally(function() {
                    sending = false;
                    sendBtn.disabled = false;
                    input.focus();
                    messages.scrollTop = messages.scrollHeight;
                });
        }
    }


    function esc(t) { var d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    console.log('[vb] views/chat.js loaded');
})();
