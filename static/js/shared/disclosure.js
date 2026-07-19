/**
 * disclosure.js — generic collapse/expand toggle.
 *
 * DOM contract:
 *   [data-disclosure]        — the collapsible container; its
 *                               data-expanded attribute ("true"/"false")
 *                               drives the CSS (see calendar filter panels).
 *   [data-disclosure-toggle] — a button inside a [data-disclosure] ancestor;
 *                               clicking it flips that ancestor's
 *                               data-expanded value.
 *
 * Multiple independent instances are supported per page.
 */
(function () {
  "use strict";

  function initDisclosures() {
    var toggles = document.querySelectorAll("[data-disclosure-toggle]");
    for (var i = 0; i < toggles.length; i++) {
      toggles[i].addEventListener("click", handleToggleClick);
    }
  }

  function handleToggleClick(event) {
    var container = event.currentTarget.closest("[data-disclosure]");
    if (!container) { return; }
    var expanded = container.getAttribute("data-expanded") === "true";
    container.setAttribute("data-expanded", expanded ? "false" : "true");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDisclosures);
  } else {
    initDisclosures();
  }
})();
