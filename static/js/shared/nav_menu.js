/**
 * nav_menu.js — mobile hamburger toggle for the primary nav
 *
 * Toggles visibility of #primary-nav (see core/partials/_site_header.html)
 * on narrow viewports via [data-nav-menu-toggle] / .site-nav[data-expanded]
 * (see static/css/components/site-chrome.css's <=45rem block — >45rem the
 * CSS never hides the nav regardless of this attribute, so the toggle is a
 * no-op there). A dedicated data hook, not account_menu.js's
 * [data-account-menu-toggle]: that module's init queries the DOM once for
 * a single account-menu instance, so reusing its hook here would make one
 * of the two toggles silently unwired depending on source order.
 *
 * Deliberately does *not* close on outside click, unlike account_menu.js's
 * dropdown: the expanded nav is an in-flow block (pushes the header taller,
 * same shape as _archive_nav's <details> panel), not an overlay floating
 * above page content, so there is no "away" affordance to click through —
 * closing only on Escape (or re-tapping the toggle / navigating away) is
 * the archive-nav precedent this follows. No focus trap either: every item
 * inside is a plain navigation link, nothing to manage once opened (same
 * rationale as account_menu.js).
 */
(function () {
  "use strict";

  function initNavMenu() {
    var toggle = document.querySelector("[data-nav-menu-toggle]");
    var nav = document.getElementById("primary-nav");
    if (!toggle || !nav) {
      return;
    }

    function setOpen(open) {
      nav.setAttribute("data-expanded", String(open));
      toggle.setAttribute("data-expanded", String(open));
      toggle.setAttribute("aria-expanded", String(open));
    }

    toggle.addEventListener("click", function () {
      setOpen(nav.getAttribute("data-expanded") !== "true");
    });

    // Document-level, like account_menu.js: right after opening via click
    // the focus sits on the toggle (outside the nav), and a nav-scoped
    // listener would never see that Escape. Gated on focus context so an
    // Escape aimed at another open widget (e.g. the account dropdown, whose
    // own handler bubbles here without stopPropagation) can't also close
    // this nav and steal the focus that widget just restored.
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || nav.getAttribute("data-expanded") !== "true") {
        return;
      }
      if (!nav.contains(document.activeElement) && document.activeElement !== toggle) {
        return;
      }
      setOpen(false);
      toggle.focus();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initNavMenu);
  } else {
    initNavMenu();
  }
})();
