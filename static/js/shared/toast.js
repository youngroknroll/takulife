/**
 * toast.js — lightweight success toast for takulife
 *
 * Exposes: window.TakuToast.show(message)
 *   role="status" aria-live="polite", textContent only (XSS-safe), auto-
 *   dismiss after ~3.5s. DOM: lazily built once on first use (singleton),
 *   same idiom as confirm-modal.js.
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
    toastEl.setAttribute("aria-live", "polite");
    toastEl.hidden = true;
    document.body.appendChild(toastEl);
  }

  function show(message) {
    if (!toastEl) {
      build();
    }
    if (hideTimer) {
      window.clearTimeout(hideTimer);
      hideTimer = null;
    }

    toastEl.textContent = message;
    toastEl.hidden = false;
    toastEl.classList.remove("is-visible");

    // rAF lets the browser paint the hidden state first so the CSS
    // opacity/transform transition actually fires (mirrors confirm-modal.js).
    requestAnimationFrame(function () {
      toastEl.classList.add("is-visible");
    });

    hideTimer = window.setTimeout(function () {
      toastEl.classList.remove("is-visible");
      toastEl.hidden = true;
      hideTimer = null;
    }, DISMISS_MS);
  }

  window.TakuToast = { show: show };

  function initReloadBridge() {
    var pending = window.sessionStorage.getItem(STORAGE_KEY);
    if (!pending) {
      return;
    }
    // Clear before showing so a reload during the toast's own lifetime
    // (or a later visit) never re-fires the same message.
    window.sessionStorage.removeItem(STORAGE_KEY);
    show(pending);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReloadBridge);
  } else {
    initReloadBridge();
  }
})();
