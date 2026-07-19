/**
 * toast.js — lightweight success toast for takulife
 *
 * Exposes: window.TakuToast.show(message)
 *   textContent only (XSS-safe), auto-dismiss after ~3.5s. DOM: built once,
 *   unconditionally, at script load (singleton) — role="status" must be
 *   present in the a11y tree before the first show().
 *
 * Reload bridge: pages that reload after a successful action (status.js
 * data-reload-on-success) stash the message in sessionStorage under
 * "taku:toast" before reloading; this file reads and clears it on
 * DOMContentLoaded so the toast survives the full page reload without
 * re-firing on a later visit.
 *
 * Reduced motion: the enter/exit transition is skipped via CSS
 * (@media prefers-reduced-motion: reduce); the auto-dismiss timer still runs.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "taku:toast";
  var DISMISS_MS = 3500;

  var toastEl = null;
  var hideTimer = null;

  function build() {
    toastEl = document.createElement("div");
    toastEl.className = "taku-toast";
    toastEl.setAttribute("role", "status");
    document.body.appendChild(toastEl);
  }

  function show(message) {
    if (hideTimer) {
      window.clearTimeout(hideTimer);
      hideTimer = null;
    }

    // Empty first so a repeat of the same message is still a detectable
    // mutation for assistive tech.
    toastEl.textContent = "";
    toastEl.classList.remove("is-visible");

    // rAF lets the browser paint the hidden state first so the CSS
    // opacity/transform transition actually fires (mirrors confirm-modal.js).
    requestAnimationFrame(function () {
      toastEl.textContent = message;
      toastEl.classList.add("is-visible");
    });

    hideTimer = window.setTimeout(function () {
      toastEl.classList.remove("is-visible");
      hideTimer = null;
    }, DISMISS_MS);
  }

  window.TakuToast = { show: show };

  function initReloadBridge() {
    var pending;
    try {
      pending = window.sessionStorage.getItem(STORAGE_KEY);
      if (!pending) {
        return;
      }
      // Clear before showing so a reload during the toast's own lifetime
      // (or a later visit) never re-fires the same message.
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      // Storage blocked — nothing to bridge, skip the toast silently.
      return;
    }
    show(pending);
  }

  build();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReloadBridge);
  } else {
    initReloadBridge();
  }
})();
