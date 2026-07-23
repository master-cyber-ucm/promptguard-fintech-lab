/**
 * VerdaBank API client.
 * Global namespace: window.VB.API
 */

window.VB = window.VB || {};
window.VB.API = {};

(function() {

    var _backendPort = window.VB_BACKEND_PORT || 8000;
    var API_BASE = 'http://' + window.location.hostname + ':' + _backendPort;

window.VB.API.sendMessage = function(userId, sessionId, message, fixtureMetadata, endpoint) {
        var chatEndpoint = endpoint || window.VB_CHAT_ENDPOINT || 'complex-with-context';
        var body = { user_id: userId, session_id: sessionId, message: message };
        if (fixtureMetadata) {
            body.fixture_id = fixtureMetadata.fixture_id || null;
            body.fixture_kind = fixtureMetadata.fixture_kind || null;
            body.fixture_expected_result = fixtureMetadata.fixture_expected_result || null;
        }
        return fetch(API_BASE + '/api/v1/chat/' + chatEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        })
        .then(function(resp) {
            if (!resp.ok) {
                return resp.json().then(function(e) { throw new Error(e.detail || 'HTTP ' + resp.status); });
            }
            return resp.json();
        });
    };

    window.VB.API.sendMessageWithDocument = function(userId, sessionId, message, file, fixtureMetadata) {
        var formData = new FormData();
        formData.append('user_id', userId);
        formData.append('session_id', sessionId);
        formData.append('message', message);
        formData.append('document', file, file.name);
        if (fixtureMetadata) {
            if (fixtureMetadata.fixture_id) formData.append('fixture_id', fixtureMetadata.fixture_id);
            if (fixtureMetadata.fixture_kind) formData.append('fixture_kind', fixtureMetadata.fixture_kind);
            if (fixtureMetadata.fixture_expected_result) formData.append('fixture_expected_result', fixtureMetadata.fixture_expected_result);
        }
        return fetch(API_BASE + '/api/v1/chat/complex-with-document', {
            method: 'POST',
            body: formData,
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
