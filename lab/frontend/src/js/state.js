/**
 * VerdaBank State — simple sessionStorage wrapper.
 * Global namespace: window.VB
 */

window.VB = window.VB || {};

window.VB.getState = function(key) {
    try {
        var raw = sessionStorage.getItem('vb_' + key);
        return raw ? JSON.parse(raw) : null;
    } catch(e) {
        return null;
    }
};

window.VB.setState = function(key, value) {
    sessionStorage.setItem('vb_' + key, JSON.stringify(value));
};

window.VB.clearState = function() {
    Object.keys(sessionStorage)
        .filter(function(k) { return k.startsWith('vb_'); })
        .forEach(function(k) { sessionStorage.removeItem(k); });
};

console.log('[vb] state.js loaded');
