/**
 * api.js — CSRF-aware REST client for takulife
 *
 * Exposes window.TakuAPI with the following methods:
 *   get(url)              — GET request, returns {ok, status, data}
 *   post(url, body)       — POST with JSON body
 *   patch(url, body)      — PATCH with JSON body
 *   del(url)              — DELETE (no body)
 *   upload(url, formData, method) — multipart request (default POST); does
 *                           NOT set Content-Type so the browser sets the
 *                           correct multipart boundary. method also accepts
 *                           "PATCH" for a multipart partial update.
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
 *                         'notfound' | 'server' | 'network' | 'ratelimited' |
 *                         'unknown'
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

  // DRF's "not authenticated" 403 detail, in every locale this app serves
  // (Django LANGUAGE_CODE is ko, so the Korean string is what actually ships).
  var AUTH_DETAIL_MARKERS = [
    "Authentication credentials were not provided",
    "자격 인증 데이터가 제공되지 않았습니다",
  ];

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
      // await is required: parseResponse's own await (response.json()) can
      // reject, and an un-awaited return here would let that rejection
      // escape this try/catch instead of hitting the network-error fallback.
      return await parseResponse(response);
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
   * 'ratelimited' — 429 Too Many Requests
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
      for (var m = 0; m < AUTH_DETAIL_MARKERS.length; m++) {
        if (detail.indexOf(AUTH_DETAIL_MARKERS[m]) !== -1) {
          return "auth";
        }
      }
      return "csrf";
    }
    if (s === 404) { return "notfound"; }
    if (s === 409) { return "conflict"; }
    if (s === 429) { return "ratelimited"; }
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
    // 429 Too Many Requests — checked before the data-presence check below
    // since a throttled response isn't guaranteed to carry a JSON body.
    // No automatic retry here; the caller's normal error-display path
    // (an inline message, no resubmission) is enough.
    if (result.status === 429) {
      return "요청이 많아요. 잠시 후 다시 시도해 주세요.";
    }
    var data = result.data;
    if (!data) {
      return "알 수 없는 오류가 발생했습니다.";
    }
    // Known semantic codes
    if (data.code === "duplicate_user_event_status") {
      return "이미 추가됨";
    }
    if (data.code === "duplicate_event_interest") {
      return "이미 찜한 행사입니다.";
    }
    if (data.code === "photo_limit_exceeded") {
      return "사진은 기록당 최대 5장까지 첨부할 수 있습니다.";
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

  /**
   * isAuthenticated() — read the login state the server stamped on <body>.
   * Lets callers skip a doomed request and prompt for login up front.
   */
  function isAuthenticated() {
    return document.body.dataset.authenticated === "true";
  }

  /**
   * promptLogin() — show a modal asking the visitor to log in or sign up,
   * instead of a hard redirect or a misleading error. Login/register links
   * carry ?next so the visitor returns to the current page. Idempotent
   * (one modal at a time). All text via textContent — no markup injection.
   *
   * Accessibility: focus moves to the close button on open, Tab/Shift+Tab
   * cycle only through the modal's focusable controls (close, login,
   * register), and focus returns to the element that had it before the
   * modal opened once the modal is dismissed.
   */
  function promptLogin() {
    if (document.querySelector(".auth-modal-overlay")) {
      return;
    }
    var next = encodeURIComponent(
      window.location.pathname + window.location.search
    );

    var overlay = document.createElement("div");
    overlay.className = "auth-modal-overlay";

    var modal = document.createElement("div");
    modal.className = "auth-modal";

    var close = document.createElement("button");
    close.type = "button";
    close.className = "auth-modal-close";
    close.textContent = "×";

    var title = document.createElement("h2");
    title.id = "auth-modal-title";
    title.textContent = "로그인이 필요합니다";

    var desc = document.createElement("p");
    desc.textContent = "찜·방문 예정을 저장하려면 로그인해 주세요.";

    var actions = document.createElement("div");
    actions.className = "auth-modal-actions";

    var loginLink = document.createElement("a");
    loginLink.className = "auth-modal-primary";
    loginLink.href = "/accounts/login/?next=" + next;
    loginLink.textContent = "로그인";

    var registerLink = document.createElement("a");
    registerLink.className = "auth-modal-secondary";
    registerLink.href = "/accounts/signup/?next=" + next;
    registerLink.textContent = "회원가입";

    actions.appendChild(loginLink);
    actions.appendChild(registerLink);
    modal.appendChild(close);
    modal.appendChild(title);
    modal.appendChild(desc);
    modal.appendChild(actions);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    var previouslyFocused = document.activeElement;
    var focusables = [close, loginLink, registerLink];

    function dismiss() {
      overlay.remove();
      document.removeEventListener("keydown", onKey);
      if (previouslyFocused && typeof previouslyFocused.focus === "function") {
        previouslyFocused.focus();
      }
    }
    function onKey(evt) {
      if (evt.key === "Escape") {
        dismiss();
        return;
      }
      if (evt.key === "Tab") {
        trapTab(evt);
      }
    }
    function trapTab(evt) {
      var first = focusables[0];
      var last = focusables[focusables.length - 1];
      if (evt.shiftKey) {
        if (document.activeElement === first || !overlay.contains(document.activeElement)) {
          evt.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last || !overlay.contains(document.activeElement)) {
          evt.preventDefault();
          first.focus();
        }
      }
    }
    close.addEventListener("click", dismiss);
    overlay.addEventListener("click", function (evt) {
      if (evt.target === overlay) {
        dismiss();
      }
    });
    document.addEventListener("keydown", onKey);
    close.focus();
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
     * upload(url, formData, method) — multipart request, default POST.
     * Does NOT set Content-Type so the browser sets the multipart boundary.
     * Injects X-CSRFToken and sends credentials: 'same-origin'. Pass
     * method: "PATCH" for a multipart partial update (e.g. replacing an
     * image alongside other fields on an existing resource).
     */
    upload: async function (url, formData, method) {
      try {
        var response = await fetch(url, {
          method: method || "POST",
          credentials: "same-origin",
          headers: buildUploadHeaders(),
          body: formData,
        });
        // await required — see request()'s parseResponse call for why.
        return await parseResponse(response);
      } catch (_networkError) {
        return { ok: false, status: 0, data: null };
      }
    },

    classify: classify,
    formatError: formatError,
    redirectToLogin: redirectToLogin,
    isAuthenticated: isAuthenticated,
    promptLogin: promptLogin,

    /**
     * setLoading(button, isLoading) — toggle a button's in-flight state.
     * Disables the button and adds the .is-loading spinner class while a
     * request runs, giving immediate click feedback and blocking
     * double-submits. Safe to call with a null/undefined button.
     */
    setLoading: function (button, isLoading) {
      if (!button) {
        return;
      }
      button.disabled = !!isLoading;
      if (isLoading) {
        button.classList.add("is-loading");
      } else {
        button.classList.remove("is-loading");
      }
    },

    /**
     * commitAndNavigate(button, url) — mark a just-succeeded submit as
     * committed, then navigate to url. The marker
     * (data-committed-redirect=url) is plain DOM state, so it survives a
     * back/forward-cache snapshot the way in-memory JS state cannot — on
     * restore, the pageshow handler below reads the marker as proof that
     * the prior submit already succeeded, instead of guessing from the
     * .is-loading class alone. Order (marker set before navigation
     * starts) is guaranteed by this helper, not by call-site discipline —
     * relying on call sites to remember that order already failed in
     * three files. Uses assign, not replace, because this is the normal
     * forward navigation after a successful submit and should keep a
     * normal history entry; only the bfcache restore path below needs
     * replace. Safe to call with a null/undefined button — navigation
     * still happens, only the marker is skipped.
     */
    commitAndNavigate: function (button, url) {
      if (button) {
        button.setAttribute("data-committed-redirect", url);
      }
      window.location.assign(url);
    },
  };

  // ── bfcache restore ───────────────────────────────────────────────────────

  // A back/forward-cache restore (event.persisted) can bring back a page
  // with a button still frozen in its in-flight state (disabled +
  // .is-loading) from before the user navigated away — the request that
  // would have called setLoading(btn, false) never got the chance to run
  // again. Scoped to .is-loading only, so a button the server rendered
  // disabled on purpose (e.g. an already-approved draft's 승인 button) is
  // left untouched. If a .is-loading button carries a
  // data-committed-redirect marker (set by commitAndNavigate right before
  // the prior submit navigated away), that prior submit is known to have
  // succeeded — re-enabling it would let the user resubmit an already-
  // committed form. Instead force the page forward to that destination
  // with replace, not assign: assign would let every future restore push
  // a fresh history entry, leaving a Back → form → forced-forward → Back
  // → form loop in place, while replace collapses the restored snapshot
  // in one hop. The first marked button found wins and the loop stops
  // there — navigation is about to leave the page anyway, so any buttons
  // re-enabled before it was found are harmless.
  window.addEventListener("pageshow", function (evt) {
    if (!evt.persisted) {
      return;
    }
    var loadingButtons = document.querySelectorAll(".is-loading");
    for (var i = 0; i < loadingButtons.length; i++) {
      var btn = loadingButtons[i];
      var committedRedirect = btn.dataset.committedRedirect;
      if (committedRedirect) {
        window.location.replace(committedRedirect);
        return;
      }
      window.TakuAPI.setLoading(btn, false);
    }
  });
})();
