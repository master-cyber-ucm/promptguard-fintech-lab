/**
 * VerdaBank Login View — estilo corporativo, sin emojis.
 */

window.VB = window.VB || {};
window.VB.Views = window.VB.Views || {};

(function() {

    var MOCK_USERS = [
        { id: 'usr_001', name: 'María García López', account: 'ES91...1332', balance: '15.420,50', initials: 'MG' },
        { id: 'usr_002', name: 'Carlos Rodríguez Martín', account: 'ES76...1333', balance: '8.750,25', initials: 'CR' },
        { id: 'usr_003', name: 'Ana Fernández Ruiz', account: 'ES34...1334', balance: '231.500,00', initials: 'AF' },
        { id: 'usr_admin', name: 'Admin Banco', account: 'ES58...1335', balance: '999.999,99', initials: 'AB' },
    ];


    window.VB.Views.login = function() {
        var app = document.getElementById('app');

        var optionsHtml = MOCK_USERS.map(function(u) {
            return '<option value="' + u.id + '">' + u.name + ' — ' + u.account + '</option>';
        }).join('');

        app.innerHTML =
            '<div class="login-page">' +
                '<div class="login-left">' +
                    '<h1>Verda<span class="brand-light">Bank</span></h1>' +
                    '<p class="tagline">Banca digital para la gestion inteligente de tus finanzas. Segura, transparente y sostenible.</p>' +
                    '<div class="features">' +
                        '<div class="feature">' +
                            '<span class="feature-num">1</span>' +
                            '<span>Tarjetas sin comisiones con programa de cashback</span>' +
                        '</div>' +
                        '<div class="feature">' +
                            '<span class="feature-num">2</span>' +
                            '<span>Transferencias SEPA inmediatas y gratuitas</span>' +
                        '</div>' +
                        '<div class="feature">' +
                            '<span class="feature-num">3</span>' +
                            '<span>Asistente virtual disponible las 24 horas</span>' +
                        '</div>' +
                        '<div class="feature">' +
                            '<span class="feature-num">4</span>' +
                            '<span>Cumplimiento normativo: DORA, AI Act, PSD2</span>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
                '<div class="login-right">' +
                    '<div class="login-card">' +
                        '<h2>Acceder</h2>' +
                        '<p class="subtitle">Introduce tus credenciales de VerdaBank</p>' +
                        '<div class="form-group">' +
                            '<label for="login-user">Cuenta</label>' +
                            '<select id="login-user">' + optionsHtml + '</select>' +
                        '</div>' +
                        '<div class="form-group">' +
                            '<label for="login-pass">Contrasena</label>' +
                            '<input type="password" id="login-pass" value="••••••••" placeholder="Tu contrasena">' +
                        '</div>' +
                        '<button id="btn-login" class="btn-login">Entrar</button>' +
                        '<div class="login-hint">' +
                            '<strong>Entorno de laboratorio TFM.</strong> Selecciona un usuario mock. ' +
                            'La contrasena es irrelevante. Cada usuario tiene datos bancarios diferentes.' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>';

        document.getElementById('btn-login').addEventListener('click', handleLogin);
        document.getElementById('login-pass').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') handleLogin();
        });
    };


    function handleLogin() {
        var select = document.getElementById('login-user');
        var userId = select.value;
        var user = MOCK_USERS.find(function(u) { return u.id === userId; });
        if (user) {
            VB.setState('user', user);
            VB.navigate('/dashboard');
        }
    }

    console.log('[vb] views/login.js loaded');
})();
