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
 * explicit choice, and applies it immediately. The header's
 * [data-theme-toggle] button (core/partials/_site_header.html) is wired to
 * it below; the icon swap itself is pure CSS (site-chrome.css reads the
 * same data-theme attribute), so no DOM update is needed here beyond the
 * attribute toggle already done by toggle().
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

  function bindToggleButtons() {
    var buttons = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", toggle);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindToggleButtons);
  } else {
    bindToggleButtons();
  }

  // A bfcache restore (event.persisted) can bring back a page frozen in
  // whatever data-theme it had at the moment the visitor navigated away —
  // if the theme changed since then (another tab's toggle, or the stored
  // value expiring), the restored page never re-runs this file's own
  // applyTheme(resolveTheme()) call above to pick that up. Re-applying is a
  // no-op when the stored value hasn't changed, so this is safe to run on
  // every bfcache restore. api.js's/status.js's own pageshow listeners
  // recover their own unrelated frozen-state concerns; this file owns
  // recovering its own (stale theme).
  window.addEventListener("pageshow", function (evt) {
    if (!evt.persisted) {
      return;
    }
    applyTheme(resolveTheme());
  });

  window.TakuTheme = {
    toggle: toggle,
  };
})();
