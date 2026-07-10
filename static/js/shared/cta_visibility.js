/**
 * cta_visibility.js — show a fixed mobile CTA bar only when its primary CTA
 * has scrolled out of view, so mobile users never see the same call to
 * action twice on screen at once (event detail + archive).
 *
 * DOM contract:
 *   [data-cta-watch] — the primary, in-flow CTA to observe.
 *   [data-cta-fixed] — the fixed bottom bar; starts with the `hidden`
 *                       attribute in markup so there is no flash before this
 *                       script decides whether to show it.
 *
 * No IntersectionObserver support: fall back to always showing the fixed
 * bar (the previous unconditional behaviour).
 */
(function () {
  "use strict";

  function initCtaVisibility() {
    var watchTarget = document.querySelector("[data-cta-watch]");
    var fixedBar = document.querySelector("[data-cta-fixed]");

    if (!watchTarget || !fixedBar) { return; }

    if (typeof window.IntersectionObserver !== "function") {
      fixedBar.hidden = false;
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      var entry = entries[0];
      fixedBar.hidden = entry.isIntersecting;
    });
    observer.observe(watchTarget);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCtaVisibility);
  } else {
    initCtaVisibility();
  }
})();
