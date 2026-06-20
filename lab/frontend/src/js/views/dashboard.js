/**
 * VerdaBank Dashboard — estilo corporativo, sin emojis.
 * SVG icons inline.
 */

window.VB = window.VB || {};
window.VB.Views = window.VB.Views || {};

(function() {

    // SVG icons (stroke-based, no emojis)
    var ICON = {
        home: '<svg viewBox="0 0 24 24"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1"/></svg>',
        chat: '<svg viewBox="0 0 24 24"><path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>',
        card: '<svg viewBox="0 0 24 24"><path d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/></svg>',
        transfer: '<svg viewBox="0 0 24 24"><path d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/></svg>',
        chart: '<svg viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>',
        flask: '<svg viewBox="0 0 24 24"><path d="M9 3v2m6-2v2M9 15v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h.01M15 9h.01M9 13h6"/></svg>',
        logout: '<svg viewBox="0 0 24 24"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>',
    };

    var ACCOUNTS = {
        'usr_001': { iban: 'ES91 2100 0418 4502 0005 1332', balance: 15420.50, label: 'Cuenta Nomina' },
        'usr_002': { iban: 'ES76 2100 0418 4502 0005 1333', balance: 8750.25, label: 'Cuenta Corriente' },
        'usr_003': { iban: 'ES34 2100 0418 4502 0005 1334', balance: 231500.00, label: 'Cuenta Premium' },
        'usr_admin': { iban: 'ES58 2100 0418 4502 0005 1335', balance: 999999.99, label: 'Cuenta Admin' },
    };


    window.VB.Views.dashboard = function() {
        var user = VB.getState('user');
        if (!user) { VB.navigate('/'); return; }

        var acc = ACCOUNTS[user.id] || ACCOUNTS['usr_001'];
        var balFmt = acc.balance.toLocaleString('es-ES', { minimumFractionDigits: 2 });
        var firstName = user.name.split(' ')[0];

        var app = document.getElementById('app');
        app.innerHTML =
            '<div class="dashboard">' +
                sidebar(user, 'home') +
                '<div class="main-content">' +
                    '<div class="page-header">' +
                        '<h1>Buenos dias, ' + firstName + '</h1>' +
                        '<p>Resumen de tus cuentas</p>' +
                    '</div>' +
                    '<div class="page-body">' +
                        '<div class="account-cards">' +
                            '<div class="account-card">' +
                                '<div class="acc-label">' + acc.label + '</div>' +
                                '<div class="acc-balance">' + balFmt + ' EUR</div>' +
                                '<div class="acc-details"><span>' + user.name + '</span><span>Disponible</span></div>' +
                                '<div class="acc-iban">' + acc.iban + '</div>' +
                            '</div>' +
                        '</div>' +
                        '<div class="quick-actions">' +
                            '<button class="action-btn" onclick="VB.navigate(\'/chat\')">' +
                                '<div class="action-icon green">' + ICON.chat + '</div>' +
                                '<span class="action-label">Hablar con Clara</span>' +
                            '</button>' +
                            '<button class="action-btn">' +
                                '<div class="action-icon blue">' + ICON.transfer + '</div>' +
                                '<span class="action-label">Transferir</span>' +
                            '</button>' +
                            '<button class="action-btn">' +
                                '<div class="action-icon amber">' + ICON.card + '</div>' +
                                '<span class="action-label">Mis tarjetas</span>' +
                            '</button>' +
                            '<button class="action-btn">' +
                                '<div class="action-icon purple">' + ICON.chart + '</div>' +
                                '<span class="action-label">Inversiones</span>' +
                            '</button>' +
                        '</div>' +
                        '<div class="card">' +
                            '<div class="card-header"><h3>Ultimos movimientos</h3></div>' +
                            '<table class="tx-table">' +
                                '<thead><tr><th>Fecha</th><th>Descripcion</th><th>Tipo</th><th style="text-align:right">Importe</th></tr></thead>' +
                                '<tbody id="tx-tbody"><tr><td colspan="4" style="color:var(--text-tertiary);text-align:center;padding:24px">Cargando...</td></tr></tbody>' +
                            '</table>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>' +
            chatWidget(user);

        initChatWidget(user);
        loadTransactions(user.id);
    };


    function loadTransactions(userId) {
        VB.API.getTransactions(userId)
            .then(function(data) {
                var tbody = document.getElementById('tx-tbody');
                if (!tbody) return;

                var txs = data.transactions || [];
                if (txs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-tertiary);text-align:center;padding:24px">Sin movimientos</td></tr>';
                    return;
                }

                tbody.innerHTML = txs.map(function(tx) {
                    var cls = tx.amount >= 0 ? 'positive' : 'negative';
                    var sign = tx.amount >= 0 ? '+' : '';
                    return '<tr>' +
                        '<td>' + tx.date + '</td>' +
                        '<td>' + tx.desc + '</td>' +
                        '<td>' + tx.type + '</td>' +
                        '<td class="tx-amount ' + cls + '" style="text-align:right">' + sign + tx.amount.toFixed(2) + ' EUR</td>' +
                    '</tr>';
                }).join('');
            })
            .catch(function() {
                var tbody = document.getElementById('tx-tbody');
                if (tbody) tbody.innerHTML = '<tr><td colspan="4" style="color:var(--danger);text-align:center;padding:24px">Error cargando movimientos</td></tr>';
            });
    }


    function sidebar(user, active) {
        var items = [
            { id: 'home', label: 'Inicio', icon: ICON.home, action: 'VB.navigate(\'/dashboard\')' },
            { id: 'chat', label: 'Clara', icon: ICON.chat, action: 'VB.navigate(\'/chat\')' },
            { id: 'card', label: 'Tarjetas', icon: ICON.card, action: '' },
            { id: 'transfer', label: 'Transferencias', icon: ICON.transfer, action: '' },
            { id: 'chart', label: 'Inversiones', icon: ICON.chart, action: '' },
            { id: 'flask', label: 'Lab de ataques', icon: ICON.flask, action: 'window.location.href=\'/playground.html\'' },
        ];

        var navHtml = items.map(function(it) {
            var cls = it.id === active ? ' active' : '';
            var onclick = it.action ? ' onclick="' + it.action + '"' : '';
            return '<button class="nav-item' + cls + '"' + onclick + '><span class="nav-icon">' + it.icon + '</span> ' + it.label + '</button>';
        }).join('');

        return '<aside class="sidebar">' +
            '<div class="sidebar-brand"><h2>VerdaBank</h2></div>' +
            '<div class="sidebar-user">' +
                '<div class="user-avatar">' + user.initials + '</div>' +
                '<div class="user-name">' + user.name + '</div>' +
                '<div class="user-role">Cuenta personal</div>' +
            '</div>' +
            '<nav class="sidebar-nav">' + navHtml + '</nav>' +
            '<div class="sidebar-footer">' +
                '<button class="nav-item" onclick="VB.logout()"><span class="nav-icon">' + ICON.logout + '</span> Cerrar sesion</button>' +
            '</div>' +
        '</aside>';
    }

    window.VB.Views._sidebar = sidebar;
    window.VB.Views._icons = ICON;


    function chatWidget(user) {
        var firstName = user.name.split(' ')[0];
        return '<div class="chat-widget">' +
            '<div id="chat-window" class="chat-window hidden">' +
                '<div class="chat-window-header">' +
                    '<div class="clara-avatar">CL</div>' +
                    '<div class="clara-info"><h4>Clara</h4><span>En linea</span></div>' +
                    '<button class="chat-close" onclick="document.getElementById(\'chat-window\').classList.add(\'hidden\')">x</button>' +
                '</div>' +
                '<div id="chat-widget-messages" class="chat-window-messages">' +
                    '<div class="chat-msg-welcome"><strong>Hola, ' + firstName + '</strong>Soy Clara, tu asistente VerdaBank.</div>' +
                '</div>' +
                '<div class="chat-window-input">' +
                    '<input type="text" id="chat-widget-input" placeholder="Escribe tu mensaje..." />' +
                    '<button id="chat-widget-send"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg></button>' +
                '</div>' +
            '</div>' +
            '<button id="chat-fab" class="chat-fab">💬</button>' +
        '</div>';
    }


    function initChatWidget(user) {
        var fab = document.getElementById('chat-fab');
        var chatWindow = document.getElementById('chat-window');
        var input = document.getElementById('chat-widget-input');
        var sendBtn = document.getElementById('chat-widget-send');
        var messages = document.getElementById('chat-widget-messages');
        if (!fab || !chatWindow) return;

        var sending = false;

        fab.addEventListener('click', function() {
            chatWindow.classList.toggle('hidden');
            if (!chatWindow.classList.contains('hidden')) input.focus();
        });

        sendBtn.addEventListener('click', handleSend);
        input.addEventListener('keydown', function(e) { if (e.key === 'Enter') handleSend(); });

        function handleSend() {
            if (sending) return;
            var msg = input.value.trim();
            if (!msg) return;

            messages.innerHTML += '<div class="chat-msg chat-msg-user">' + esc(msg) + '</div>';
            input.value = '';
            messages.scrollTop = messages.scrollHeight;

            var lid = 'l' + Date.now();
            messages.innerHTML += '<div id="' + lid + '" class="chat-msg chat-msg-loading">...</div>';
            messages.scrollTop = messages.scrollHeight;

            sending = true;
            sendBtn.disabled = true;

            VB.API.sendMessage(user.id, msg)
                .then(function(resp) {
                    var el = document.getElementById(lid);
                    if (el) el.remove();
                    var text = resp.error
                        ? '<em style="color:var(--danger)">' + esc(resp.error) + '</em>'
                        : esc(resp.response || '');
                    messages.innerHTML += '<div class="chat-msg chat-msg-clara">' + text + '</div>';
                })
                .catch(function() {
                    var el = document.getElementById(lid);
                    if (el) el.remove();
                    messages.innerHTML += '<div class="chat-msg chat-msg-clara"><em style="color:var(--danger)">Error de conexion</em></div>';
                })
                .finally(function() {
                    sending = false;
                    sendBtn.disabled = false;
                    messages.scrollTop = messages.scrollHeight;
                });
        }
    }


    function esc(t) { var d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    console.log('[vb] views/dashboard.js loaded');
})();
