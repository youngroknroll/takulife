/**
 * archive_search.js — debounced live search for the archive list pages.
 *
 * Progressive enhancement over the no-JS server-side search (PR #61): the
 * GET form still works without this script. When present, typing in the
 * search box fetches only the results fragment (?partial=1) and swaps it into
 * #archive-results, keeping the input focused and the URL in sync.
 *
 * Behavior:
 *   - Debounced input (250ms) → fetch path + current filters + ?partial=1.
 *   - AbortController cancels the previous in-flight request so a slow earlier
 *     response can never overwrite a newer one (race-free).
 *   - history.pushState keeps a shareable, reload-safe URL (without partial=1);
 *     popstate (back/forward) re-syncs the input and results.
 *   - On an auth-expiry redirect the partial GET follows to the login page;
 *     we detect response.redirected and navigate there.
 *   - Swapped HTML is server-rendered (Django auto-escaped); this script never
 *     interpolates the query into markup.
 *   - After each swap it dispatches `archive:listswapped` so status.js / visit.js
 *     / personal_entries.js re-wire the freshly inserted controls.
 */
(function () {
  "use strict";

  var DEBOUNCE_MS = 250;

  var form = document.querySelector(".archive-search");
  var results = document.getElementById("archive-results");
  if (!form || !results) { return; }

  var input = form.querySelector('input[name="q"]');
  if (!input) { return; }

  var path = window.location.pathname;
  var controller = null;
  var timer = null;

  // Build the query params from the live URL so active filters (status, filter)
  // are preserved; a new search term resets paging to page 1.
  function buildParams(term) {
    var params = new URLSearchParams(window.location.search);
    if (term) {
      params.set("q", term);
    } else {
      params.delete("q");
    }
    params.delete("page");
    params.delete("partial");
    return params;
  }

  function userUrl(params) {
    var qs = params.toString();
    return qs ? path + "?" + qs : path;
  }

  function setLoading(on) {
    results.classList.toggle("is-loading", on);
    if (on) {
      results.setAttribute("aria-busy", "true");
    } else {
      results.removeAttribute("aria-busy");
    }
  }

  // Fetch the results fragment for `term` and swap it in. `push` controls
  // whether a new history entry is created (false when replaying popstate).
  function runSearch(term, push) {
    var params = buildParams(term);

    if (controller) { controller.abort(); }
    controller = new AbortController();

    var fetchParams = new URLSearchParams(params);
    fetchParams.set("partial", "1");

    setLoading(true);

    fetch(path + "?" + fetchParams.toString(), {
      credentials: "same-origin",
      headers: { "X-Requested-With": "fetch" },
      signal: controller.signal,
    })
      .then(function (response) {
        // Session expired (or any redirect to a non-fragment page): follow it.
        if (response.redirected) {
          window.location.href = response.url;
          return null;
        }
        if (!response.ok) { return null; }
        return response.text();
      })
      .then(function (html) {
        // Clear loading for every non-abort outcome — including a redirect or a
        // non-ok response that resolved `html` to null — so the dim/aria-busy
        // state can never get stuck on after a server error.
        setLoading(false);
        if (html === null) { return; }
        results.innerHTML = html;
        if (push) {
          window.history.pushState({ q: term }, "", userUrl(params));
        }
        // Re-wire the swapped controls (status/interest/delete/promote/carousel).
        document.dispatchEvent(new CustomEvent("archive:listswapped"));
      })
      .catch(function (error) {
        // Aborted requests are expected when typing fast — ignore them.
        if (error && error.name === "AbortError") { return; }
        // Network failure: drop the loading state and leave current results.
        setLoading(false);
      });
  }

  input.addEventListener("input", function () {
    if (timer) { window.clearTimeout(timer); }
    var term = input.value.trim();
    timer = window.setTimeout(function () {
      runSearch(term, true);
    }, DEBOUNCE_MS);
  });

  // Enter (form submit) should search immediately, not full-reload.
  form.addEventListener("submit", function (evt) {
    evt.preventDefault();
    if (timer) { window.clearTimeout(timer); }
    runSearch(input.value.trim(), true);
  });

  // Back/forward: re-sync the input from the URL and replay the search without
  // pushing a new entry.
  window.addEventListener("popstate", function () {
    var term = new URLSearchParams(window.location.search).get("q") || "";
    input.value = term;
    runSearch(term, false);
  });
})();
