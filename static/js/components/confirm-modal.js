/**
 * confirm-modal.js — Custom 예/아니오 confirmation dialog for takulife
 *
 * Exposes: window.TakuConfirm(message) → Promise<boolean>
 *   Resolves true  → 예 (proceed)
 *   Resolves false → 아니오 / ESC / backdrop click (abort)
 *
 * DOM: lazily built once on first use (singleton overlay).
 * XSS-safe: message written with textContent only.
 * Focus: opens on 아니오 (safer default for destructive confirm), restores on close.
 * Focus trap: Tab cycles between the two buttons only.
 * Reduced-motion: CSS handles it via @media (prefers-reduced-motion: reduce).
 */

(function () {
  "use strict";

  // ── singleton refs ────────────────────────────────────────────────────────

  var overlay = null;
  var dialog = null;
  var messageEl = null;
  var noBtn = null;
  var yesBtn = null;

  var currentResolve = null;
  var previousFocus = null;

  // ── DOM builder (first use only) ──────────────────────────────────────────

  function buildDOM() {
    overlay = document.createElement("div");
    overlay.className = "confirm-overlay";
    overlay.setAttribute("hidden", "");

    dialog = document.createElement("div");
    dialog.className = "confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "confirm-modal-message");

    messageEl = document.createElement("p");
    messageEl.className = "confirm-message";
    messageEl.id = "confirm-modal-message";

    var actions = document.createElement("div");
    actions.className = "confirm-actions";

    noBtn = document.createElement("button");
    noBtn.type = "button";
    noBtn.className = "confirm-no";
    noBtn.textContent = "아니오";

    yesBtn = document.createElement("button");
    yesBtn.type = "button";
    yesBtn.className = "confirm-yes";
    yesBtn.textContent = "예";

    // 아니오 first (left), 예 second (right)
    actions.appendChild(noBtn);
    actions.appendChild(yesBtn);

    dialog.appendChild(messageEl);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // ── event bindings ─────────────────────────────────────────────────────

    yesBtn.addEventListener("click", function () {
      resolve(true);
    });

    noBtn.addEventListener("click", function () {
      resolve(false);
    });

    // Backdrop click — only when the click target is the overlay itself
    overlay.addEventListener("click", function (evt) {
      if (evt.target === overlay) {
        resolve(false);
      }
    });

    // ESC key
    overlay.addEventListener("keydown", function (evt) {
      if (evt.key === "Escape") {
        evt.preventDefault();
        resolve(false);
      }

      // Focus trap: Tab cycles between noBtn and yesBtn only
      if (evt.key === "Tab") {
        var focused = document.activeElement;
        if (evt.shiftKey) {
          // Shift+Tab: if on noBtn, wrap to yesBtn
          if (focused === noBtn) {
            evt.preventDefault();
            yesBtn.focus();
          }
        } else {
          // Tab: if on yesBtn, wrap to noBtn
          if (focused === yesBtn) {
            evt.preventDefault();
            noBtn.focus();
          }
        }
      }
    });
  }

  // ── open / close ──────────────────────────────────────────────────────────

  function open(message) {
    if (!overlay) {
      buildDOM();
    }

    messageEl.textContent = message;

    previousFocus = document.activeElement || document.body;

    overlay.removeAttribute("hidden");

    // rAF lets the browser paint the initial state before adding .is-open,
    // so the CSS opacity/transform transition actually fires
    requestAnimationFrame(function () {
      overlay.classList.add("is-open");
      noBtn.focus();
    });
  }

  function close() {
    overlay.classList.remove("is-open");

    // prefers-reduced-motion strips the CSS transition (confirm-modal.css),
    // so transitionend never fires — restore hidden immediately instead of
    // waiting for it.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      overlay.setAttribute("hidden", "");
    } else {
      // Wait for the CSS transition to finish before hiding
      overlay.addEventListener("transitionend", function handler() {
        overlay.removeEventListener("transitionend", handler);
        overlay.setAttribute("hidden", "");
      });
    }

    if (previousFocus && typeof previousFocus.focus === "function") {
      previousFocus.focus();
    }
    previousFocus = null;
  }

  function resolve(value) {
    if (currentResolve === null) {
      return;
    }
    var fn = currentResolve;
    currentResolve = null;
    close();
    fn(value);
  }

  // ── public API ────────────────────────────────────────────────────────────

  function TakuConfirm(message) {
    // If already open (shouldn't happen in serial use), resolve false and reopen
    if (currentResolve !== null) {
      var oldResolve = currentResolve;
      currentResolve = null;
      oldResolve(false);
    }

    return new Promise(function (res) {
      currentResolve = res;
      open(message);
    });
  }

  window.TakuConfirm = TakuConfirm;
})();
