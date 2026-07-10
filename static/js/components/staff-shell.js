/**
 * staff-shell.js — on load, scroll the active console tab into view inside
 * the horizontally scrolling tab row (static/css/components/staff-shell.css
 * .staff-shell-tabs) so it's never hidden off-screen on narrow viewports.
 * No animation — jumps straight to position.
 */
(function () {
  "use strict";

  function revealActiveTab() {
    var active = document.querySelector(".staff-shell-tabs .active");
    if (!active) { return; }
    active.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "auto" });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", revealActiveTab);
  } else {
    revealActiveTab();
  }
})();
