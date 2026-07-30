/**
 * account_settings.js — on load, scroll the active account-settings index
 * tab into view inside its horizontally scrolling mobile track
 * (static/css/pages/account_settings.css .account-settings-index-tabs), so
 * it's never hidden off-screen on narrow viewports. Same pattern as
 * static/js/components/staff-shell.js's revealActiveTab, ported here
 * page-scoped instead of reused directly — that file's own selector is
 * hardcoded to .staff-shell-tabs and this page is not part of the staff
 * shell. No animation — jumps straight to position.
 */
(function () {
  "use strict";

  function revealActiveTab() {
    var active = document.querySelector(".account-settings-index-tabs .is-active");
    if (!active) { return; }
    active.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "auto" });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", revealActiveTab);
  } else {
    revealActiveTab();
  }
})();
