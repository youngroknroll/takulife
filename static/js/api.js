/**
 * api.js — CSRF-aware REST client for TakuLog
 *
 * Exposes window.TakuAPI with the following methods:
 *   get(url)              — GET request, returns {ok, status, data}
 *   post(url, body)       — POST with JSON body
 *   patch(url, body)      — PATCH with JSON body
 *   del(url)              — DELETE (no body)
 *   upload(url, formData) — multipart POST; does NOT set Content-Type so the
 *                           browser sets the correct multipart boundary
 *
 * All methods:
 *   - read the csrftoken cookie and inject X-CSRFToken header
 *     (upload omits Content-Type only; still injects X-CSRFToken)
 *   - send credentials: 'same-origin'
 *   - return a normalized { ok, status, data } object
 *
 * Shared error helpers (consumed by status.js, draft.js, visit.js):
 *   classify(result)   — returns a stable error kind string:
 *                         'auth' | 'csrf' | 'validation' | 'conflict' |
 *                         'notfound' | 'server' | 'network' | 'unknown'
 *   formatError(result) — human-readable Korean message from DRF error envelopes:
 *                          field-error dicts, detail string, and known code values
 *   redirectToLogin()  — builds /accounts/login/?next=<encoded current path>
 *                        and navigates; single definition used by all consumers
 *
 * Security contract:
 *   - CSRF token is read from the csrftoken cookie (CSRF_COOKIE_HTTPONLY=False).
 *   - Header name is X-CSRFToken (matches Django's CSRF_HEADER_NAME default).
 *   - credentials: 'same-origin' ensures the session cookie is sent.
 */

(function () {
  "use strict";

  var AUTH_DETAIL_MARKER = "Authentication credentials were not provided";

  // ── cookie reader ──────────────────────────────────────────────────────────

  function getCookie(name) {
    var prefix = name + "=";
    for (var part of document.cookie.split(";")) {
      var trimmed = part.trim();
      if (trimmed.startsWith(prefix)) {
        return decodeURIComponent(trimmed.slice(prefix.length));
      }
    }
    return "";
  }

  // ── internal request helpers ───────────────────────────────────────────────

  function buildJsonHeaders() {
    return {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    };
  }

  function buildUploadHeaders() {
    // Do NOT include Content-Type — browser must set multipart boundary
    return {
      "X-CSRFToken": getCookie("csrftoken"),
    };
  }

  async function parseResponse(response) {
    var data = null;
    var contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    }
    return { ok: response.ok, status: response.status, data: data };
  }

  async function request(method, url, body) {
    var options = {
      method: method,
      credentials: "same-origin",
      headers: buildJsonHeaders(),
    };
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }
    try {
      var response = await fetch(url, options);
      return parseResponse(response);
    } catch (_networkError) {
      return { ok: false, status: 0, data: null };
    }
  }

  // ── shared error helpers ───────────────────────────────────────────────────

  /**
   * classify(result) → stable error kind string
   *
   * 'auth'       — 403 whose detail mentions authentication/credentials
   * 'csrf'       — other 403 (CSRF failure, permission denied)
   * 'validation' — 400 Bad Request
   * 'conflict'   — 409 Conflict
   * 'notfound'   — 404 Not Found
   * 'server'     — 500+
   * 'network'    — status 0 (fetch threw, no connection)
   * 'unknown'    — everything else
   */
  function classify(result) {
    var s = result.status;
    if (s === 0) { return "network"; }
    if (s === 400) { return "validation"; }
    if (s === 403) {
      var detail = (result.data && typeof result.data.detail === "string")
        ? result.data.detail
        : "";
      if (detail.indexOf(AUTH_DETAIL_MARKER) !== -1) {
        return "auth";
      }
      return "csrf";
    }
    if (s === 404) { return "notfound"; }
    if (s === 409) { return "conflict"; }
    if (s >= 500) { return "server"; }
    return "unknown";
  }

  /**
   * formatError(result) → human-readable Korean message
   *
   * Handles:
   *   - Network error (status 0)
   *   - Known code values: duplicate_user_event_status, photo_limit_exceeded
   *   - detail string
   *   - Field-error dict: { field: ["msg", ...] } or { field: "msg" }
   */
  function formatError(result) {
    if (result.status === 0) {
      return "네트워크 오류가 발생했습니다. 다시 시도해 주세요.";
    }
    var data = result.data;
    if (!data) {
      return "알 수 없는 오류가 발생했습니다.";
    }
    // Known semantic codes
    if (data.code === "duplicate_user_event_status") {
      return "이미 추가됨";
    }
    if (data.code === "photo_limit_exceeded") {
      return "사진은 기록당 최대 10장까지 첨부할 수 있습니다.";
    }
    // detail string (DRF default for non-field errors)
    if (typeof data.detail === "string") {
      return data.detail;
    }
    // Field-error dict: { field: ["msg", ...], ... } or { field: "msg", ... }
    if (typeof data === "object") {
      var parts = [];
      Object.keys(data).forEach(function (field) {
        var val = data[field];
        var messages = Array.isArray(val) ? val : [String(val)];
        parts.push(field + ": " + messages.join(" "));
      });
      if (parts.length > 0) {
        return parts.join(" | ");
      }
    }
    return "알 수 없는 오류가 발생했습니다.";
  }

  /**
   * redirectToLogin() — builds /accounts/login/?next=<current path+search>
   * and navigates. Single definition; all consumers call this instead of
   * each constructing their own login URL.
   */
  function redirectToLogin() {
    var next = encodeURIComponent(
      window.location.pathname + window.location.search
    );
    window.location.href = "/accounts/login/?next=" + next;
  }

  // ── public API ─────────────────────────────────────────────────────────────

  window.TakuAPI = {
    getCookie: getCookie,

    get: function (url) {
      return request("GET", url, undefined);
    },

    post: function (url, body) {
      return request("POST", url, body);
    },

    patch: function (url, body) {
      return request("PATCH", url, body);
    },

    del: function (url) {
      return request("DELETE", url, undefined);
    },

    /**
     * upload(url, formData) — multipart POST
     * Does NOT set Content-Type so the browser sets the multipart boundary.
     * Injects X-CSRFToken and sends credentials: 'same-origin'.
     */
    upload: async function (url, formData) {
      try {
        var response = await fetch(url, {
          method: "POST",
          credentials: "same-origin",
          headers: buildUploadHeaders(),
          body: formData,
        });
        return parseResponse(response);
      } catch (_networkError) {
        return { ok: false, status: 0, data: null };
      }
    },

    classify: classify,
    formatError: formatError,
    redirectToLogin: redirectToLogin,

    /**
     * setLoading(button, isLoading) — toggle a button's in-flight state.
     * Disables the button and adds the .is-loading spinner class (+ aria-busy)
     * while a request runs, giving immediate click feedback and blocking
     * double-submits. Safe to call with a null/undefined button.
     */
    setLoading: function (button, isLoading) {
      if (!button) {
        return;
      }
      button.disabled = !!isLoading;
      if (isLoading) {
        button.classList.add("is-loading");
        button.setAttribute("aria-busy", "true");
      } else {
        button.classList.remove("is-loading");
        button.removeAttribute("aria-busy");
      }
    },
  };
})();
