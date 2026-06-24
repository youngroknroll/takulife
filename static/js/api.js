/**
 * api.js — CSRF-aware fetch helper for TakuLog
 *
 * Exposes window.TakuAPI with three methods: post, patch, del.
 * All methods:
 *   - read the csrftoken cookie and inject X-CSRFToken header
 *   - send credentials: 'same-origin'
 *   - set Content-Type: application/json
 *   - return a normalized { ok, status, data } object
 *
 * No business logic lives here. Error routing (403 disambiguation,
 * 409 reconciliation) is handled in status.js.
 *
 * Security contract:
 *   - CSRF token is read from the csrftoken cookie (CSRF_COOKIE_HTTPONLY=False).
 *   - Header name is X-CSRFToken (matches Django's CSRF_HEADER_NAME default).
 *   - credentials: 'same-origin' ensures the session cookie is sent.
 */

(function () {
  "use strict";

  function getCookie(name) {
    const prefix = name + "=";
    for (const part of document.cookie.split(";")) {
      const trimmed = part.trim();
      if (trimmed.startsWith(prefix)) {
        return decodeURIComponent(trimmed.slice(prefix.length));
      }
    }
    return "";
  }

  function buildHeaders() {
    return {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    };
  }

  async function request(method, url, body) {
    const options = {
      method: method,
      credentials: "same-origin",
      headers: buildHeaders(),
    };
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }
    try {
      const response = await fetch(url, options);
      let data = null;
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        data = await response.json();
      }
      return { ok: response.ok, status: response.status, data: data };
    } catch (networkError) {
      return { ok: false, status: 0, data: null };
    }
  }

  window.TakuAPI = {
    getCookie: getCookie,

    post: function (url, body) {
      return request("POST", url, body);
    },

    patch: function (url, body) {
      return request("PATCH", url, body);
    },

    del: function (url) {
      return request("DELETE", url, undefined);
    },
  };
})();
