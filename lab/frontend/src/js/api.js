/**
 * VerdaBank API client.
 * Global namespace: window.VB.API
 */

window.VB = window.VB || {};
window.VB.API = {};

(function() {

    var API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ? 'http://localhost:8000'
        : 'http://' + window.location.hostname + ':8000';

    // Override if running inside Docker (frontend talks to backend by name)
    if (window.location.port === '3000' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        API_BASE = 'http://backend:8000';
    }

    window.VB.API.sendMessage = function(userId, message) {
        return fetch(API_BASE + '/api/v1/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, message: message }),
        })
        .then(function(resp) {
            if (!resp.ok) {
                return resp.json().then(function(e) { throw new Error(e.detail || 'HTTP ' + resp.status); });
            }
            return resp.json();
        });
    };

    window.VB.API.getAccounts = function() {
        return fetch(API_BASE + '/api/v1/accounts').then(function(r) { return r.json(); });
    };

    window.VB.API.getUsers = function() {
        return fetch(API_BASE + '/api/v1/users').then(function(r) { return r.json(); });
    };

    window.VB.API.health = function() {
        return fetch(API_BASE + '/api/v1/health').then(function(r) { return r.json(); });
    };

    window.VB.API.getFixtures = function() {
        return fetch(API_BASE + '/api/v1/fixtures').then(function(r) { return r.json(); });
    };

    window.VB.API.getTransactions = function(userId) {
        return fetch(API_BASE + '/api/v1/transactions/' + userId)
            .then(function(r) { return r.json(); });
    };

    console.log('[vb] api.js loaded — backend at ' + API_BASE);

})();
