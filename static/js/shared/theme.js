/**
 * theme.js — dark/light theme resolution + toggle for takulife
 *
 * Resolution order: localStorage('takulife-theme') → matchMedia
 * ('prefers-color-scheme: dark') → light. Applies the winning value as
 * <html data-theme="light|dark">, which tokens.css's :root[data-theme=
 * "dark"] block consumes (2026-07-13 다크모드 계획 §1, A안).
 *
 * base.html's inline <head> snippet (FOUC guard) duplicates the minimal
 * read-only half of this same resolution so the theme applies before
 * first paint, before any deferred script (including this one) can run.
 * This file is the deferred, full version: it re-applies the identical
 * result (harmless no-op re-application, a safety net against the two
 * copies ever drifting) and additionally owns writes (the stored-value
 * mutation), the public toggle API, and the live system-theme listener.
 *
 * Exposes: window.TakuTheme.toggle() — flips the theme, stores the
 * explicit choice, and applies it immediately. Console-triggerable today;
 * PR-2's header button calls this.
 *
 * localStorage is this repo's first use of it — every access goes through
 * try/catch, since private-browsing/storage-blocked contexts can throw on
 * read or write, not just silently return null.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "takulife-theme";
  var mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

  function readStoredTheme() {
    try {
      var value = window.localStorage.getItem(STORAGE_KEY);
      return value === "light" || value === "dark" ? value : null;
    } catch (e) {
      return null;
    }
  }

  function writeStoredTheme(theme) {
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
      // Storage blocked — the theme still applies for this page load via
      // applyTheme(), it just won't persist across reloads.
    }
  }

  function resolveTheme() {
    var stored = readStoredTheme();
    if (stored) {
      return stored;
    }
    return mediaQuery.matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
  }

  function toggle() {
    var current = document.documentElement.getAttribute("data-theme");
    var next = current === "dark" ? "light" : "dark";
    writeStoredTheme(next);
    applyTheme(next);
  }

  // Keep following the system setting live, but only while the visitor
  // hasn't made an explicit choice yet (no stored value) — the confirmed
  // two-tier behavior: system-follow until a click pins an explicit theme.
  mediaQuery.addEventListener("change", function () {
    if (!readStoredTheme()) {
      applyTheme(mediaQuery.matches ? "dark" : "light");
    }
  });

  applyTheme(resolveTheme());

  window.TakuTheme = {
    toggle: toggle,
  };
})();
