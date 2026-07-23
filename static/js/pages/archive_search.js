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
 *   - The results-head sort <details> menu lives outside #archive-results (so
 *     it is never swapped); its links' `q` param is rewritten in place after
 *     each swap so a sort click never drops the current search term.
 */
(function () {
  "use strict";

  var DEBOUNCE_MS = 250;

  var form = document.querySelector(".archive-search");
  var results = document.getElementById("archive-results");
  if (!form || !results) { return; }

  var input = form.querySelector('input[name="q"]');
  if (!input) { return; }
  var clearLink = form.querySelector(".archive-search-clear");

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

  // Keep the "지우기" link in sync with the live search term — the server
  // only renders it from has_query on full page load, but live search swaps
  // just the results fragment, so the form's own clear link must be toggled
  // here instead.
  function syncClearLink(term) {
    if (!clearLink) { return; }
    clearLink.hidden = !term;
  }

  function setLoading(on) {
    results.classList.toggle("is-loading", on);
  }

  // The sort <details> menu (results-head) lives outside #archive-results, so
  // live search never swaps it — its anchors are only rendered once, at the
  // page's original GET. Without this, the `q` baked into their hrefs goes
  // stale the moment the user types a new search term, and clicking a sort
  // option silently drops what they just searched for. Only the `q` param is
  // rewritten; each anchor's own `sort` value (and any other existing params)
  // is left untouched. Pages without a sort menu (statuses/visits/items) have
  // no `[data-sort-menu]` element, so this is a no-op there.
  var sortMenu = document.querySelector("[data-sort-menu]");
  var sortLinks = sortMenu ? sortMenu.querySelectorAll("a[href]") : [];

  function syncSortLinks(term) {
    for (var i = 0; i < sortLinks.length; i++) {
      var link = sortLinks[i];
      var url = new URL(link.getAttribute("href"), window.location.href);
      if (term) {
        url.searchParams.set("q", term);
      } else {
        url.searchParams.delete("q");
      }
      link.setAttribute("href", url.pathname + url.search);
    }
  }

  // Inline failure notice (_archive_search.html) — a fresh attempt clears it
  // up front so it never lingers over results a later, successful search
  // replaces.
  var searchError = document.getElementById("archive-search-error");

  function setSearchError(message) {
    if (searchError) { searchError.textContent = message; }
  }

  // SR-only result count summary (_archive_search.html) — the innerHTML swap
  // itself never fires accessibility events, so this is the only announcement
  // a screen reader gets for a search outcome.
  var searchStatus = document.getElementById("archive-search-status");

  // Reads the server-rendered count marker out of the just-swapped fragment
  // and announces it. Defensive: a blank term clears with no announcement, a
  // missing/unparseable marker leaves the region untouched rather than
  // announcing a broken state.
  function announceResultCount(term) {
    if (!searchStatus) { return; }
    if (!term) {
      searchStatus.textContent = "";
      return;
    }
    var marker = results.querySelector("[data-result-count]");
    if (!marker) { return; }
    var count = parseInt(marker.getAttribute("data-result-count"), 10);
    if (isNaN(count)) { return; }
    var message = count > 0 ? count + "건 검색됨" : "검색 결과가 없습니다";

    // Empty first so a repeat of the same message is still a detectable
    // mutation for assistive tech (mirrors toast.js).
    searchStatus.textContent = "";
    requestAnimationFrame(function () {
      searchStatus.textContent = message;
    });
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
    setSearchError("");

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
        if (!response.ok) {
          setSearchError("검색 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
          return null;
        }
        return response.text();
      })
      .then(function (html) {
        // Clear loading for every non-abort outcome — including a redirect or a
        // non-ok response that resolved `html` to null — so the dim state can
        // never get stuck on after a server error.
        setLoading(false);
        if (html === null) { return; }
        results.innerHTML = html;
        announceResultCount(term);
        syncSortLinks(term);
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
        setSearchError("검색 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
      });
  }

  input.addEventListener("input", function (evt) {
    // IME composition (한글/日本語/中文 등) fires an `input` event per
    // intermediate keystroke while composing a character — searching on
    // those fragments wastes fetches and can flash wrong results mid-type.
    // Browsers fire a final `input` event with isComposing:false right
    // after `compositionend`, so this alone is enough to pick up the
    // completed term without a separate compositionend listener.
    if (evt.isComposing) { return; }
    if (timer) { window.clearTimeout(timer); }
    var term = input.value.trim();
    syncClearLink(term);
    timer = window.setTimeout(function () {
      runSearch(term, true);
    }, DEBOUNCE_MS);
  });

  // Enter (form submit) should search immediately, not full-reload.
  form.addEventListener("submit", function (evt) {
    evt.preventDefault();
    if (timer) { window.clearTimeout(timer); }
    var term = input.value.trim();
    syncClearLink(term);
    runSearch(term, true);
  });

  // Back/forward: re-sync the input from the URL and replay the search without
  // pushing a new entry.
  window.addEventListener("popstate", function () {
    var term = new URLSearchParams(window.location.search).get("q") || "";
    input.value = term;
    syncClearLink(term);
    runSearch(term, false);
  });
})();
