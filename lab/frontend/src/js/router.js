/**
 * VerdaBank SPA Router.
 * Cargado DESPUÉS de state.js, api.js y views/*.js
 * Las vistas están en window.VB.Views.*
 */

(function() {

    // Wait until all view scripts are loaded
    function boot() {
        if (!window.VB || !window.VB.Views || !window.VB.Views.login) {
            console.warn('[vb] Waiting for views to load...');
            setTimeout(boot, 100);
            return;
        }
        console.log('[vb] All views loaded, starting router');
        resolve();
    }


    function navigate(path) {
        window.history.pushState({}, '', path);
        resolve();
    }

    function logout() {
        VB.clearState();
        navigate('/');
    }

    // Expose globally for onclick handlers
    window.VB.navigate = navigate;
    window.VB.logout = logout;


    function resolve() {
        var path = window.location.pathname.replace(/\/$/, '') || '/';

        console.log('[vb] Resolving route: ' + path);

        // No user → must login
        var user = VB.getState('user');
        if (!user && path !== '/') {
            window.history.pushState({}, '', '/');
            path = '/';
        }

        switch (path) {
            case '/':
                if (user) {
                    VB.Views.dashboard();
                } else {
                    VB.Views.login();
                }
                break;
            case '/dashboard':
                VB.Views.dashboard();
                break;
            case '/chat':
                VB.Views.chat();
                break;
            default:
                // Unknown route → redirect to root
                window.history.pushState({}, '', '/');
                VB.Views.login();
        }
    }


    // Handle browser back/forward
    window.addEventListener('popstate', resolve);

    // Boot when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

    console.log('[vb] router.js loaded');

})();
