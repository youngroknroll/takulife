/**
 * account_menu.js — header account dropdown for takulife
 *
 * Toggles the .account-menu-panel disclosure next to the authenticated
 * user's initial-avatar button (see core/partials/_topbar.html). Ported
 * from the region-select dropdown pattern (static/js/pages/event_list.js):
 * click toggle, close on outside click, Escape closes and returns focus to
 * the trigger. No focus trap and no forced focus on open (same as
 * region-select) — every item is a page navigation (or the logout POST),
 * so there is nothing left to manage inside the panel after a click.
 *
 * Runs on every page (global script, see base.html) — no-ops for an
 * anonymous visitor, since _topbar.html only renders [data-account-menu]
 * for an authenticated user.
 */
(function () {
  "use strict";

  function initAccountMenu() {
    var accountMenu = document.querySelector("[data-account-menu]");
    if (!accountMenu) {
      return;
    }

    var toggle = accountMenu.querySelector("[data-account-menu-toggle]");
    var panel = accountMenu.querySelector("[data-account-menu-panel]");

    function setOpen(open) {
      panel.hidden = !open;
      toggle.setAttribute("data-expanded", String(open));
      toggle.setAttribute("aria-expanded", String(open));
    }

    toggle.addEventListener("click", function () {
      setOpen(panel.hidden);
    });

    document.addEventListener("click", function (event) {
      if (!accountMenu.contains(event.target)) {
        setOpen(false);
      }
    });

    accountMenu.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !panel.hidden) {
        setOpen(false);
        toggle.focus();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAccountMenu);
  } else {
    initAccountMenu();
  }
})();
