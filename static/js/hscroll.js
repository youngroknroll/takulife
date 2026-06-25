/**
 * hscroll.js — Horizontal scroller with prev/next arrow buttons for TakuLog
 *
 * Handles:
 *   - Arrow visibility based on overflow + scroll position
 *   - Edge-fade mask toggle via .at-start / .at-end on the wrap
 *   - Scroll by ~90% of track width on prev/next click
 *   - prefers-reduced-motion: uses 'instant' behavior instead of 'smooth'
 *   - ResizeObserver: re-evaluates overflow when viewport resizes
 *   - Multiple independent scrollers per page
 *   - No drag, no autoplay, no keyboard paging (native scroll + Tab work natively)
 *
 * DOM contract (set by home.html template):
 *   [data-hscroll]        — section wrap (position: relative; overflow: hidden)
 *   [data-hscroll-track]  — the scrollable flex row
 *   [data-hscroll-prev]   — prev arrow button
 *   [data-hscroll-next]   — next arrow button
 *
 * Arrow visibility uses visibility:hidden (not display:none) to avoid layout shift.
 * All DOM text writes use textContent only (no innerHTML with data).
 */

(function () {
  "use strict";

  var mqlReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function prefersReducedMotion() {
    return mqlReducedMotion.matches;
  }

  // ── scroller factory ──────────────────────────────────────────────────────

  function createScroller(wrap) {
    var track = wrap.querySelector("[data-hscroll-track]");
    var prevBtn = wrap.querySelector("[data-hscroll-prev]");
    var nextBtn = wrap.querySelector("[data-hscroll-next]");

    if (!track || !prevBtn || !nextBtn) {
      return;
    }

    var rafPending = false;

    // ── update arrow visibility and fade mask ──────────────────────────────

    function update() {
      var scrollLeft = track.scrollLeft;
      var clientWidth = track.clientWidth;
      var scrollWidth = track.scrollWidth;

      var overflowing = scrollWidth > clientWidth + 1;
      var atStart = scrollLeft <= 1;
      var atEnd = scrollLeft + clientWidth >= scrollWidth - 1;

      if (!overflowing) {
        // Everything fits — hide both arrows, remove fades
        prevBtn.style.visibility = "hidden";
        nextBtn.style.visibility = "hidden";
        wrap.classList.remove("at-start", "at-end");
        return;
      }

      // Show/hide each arrow based on scroll position
      prevBtn.style.visibility = atStart ? "hidden" : "visible";
      nextBtn.style.visibility = atEnd ? "hidden" : "visible";

      // Toggle fade classes for edge-gradient mask
      if (atStart) {
        wrap.classList.add("at-start");
      } else {
        wrap.classList.remove("at-start");
      }
      if (atEnd) {
        wrap.classList.add("at-end");
      } else {
        wrap.classList.remove("at-end");
      }
    }

    // ── scroll handler (RAF-gated) ─────────────────────────────────────────

    function onScroll() {
      if (rafPending) { return; }
      rafPending = true;
      requestAnimationFrame(function () {
        rafPending = false;
        update();
      });
    }

    // ── arrow clicks ───────────────────────────────────────────────────────

    function scrollBy(direction) {
      var behavior = prefersReducedMotion() ? "instant" : "smooth";
      track.scrollBy({ left: direction * track.clientWidth * 0.9, behavior: behavior });
    }

    prevBtn.addEventListener("click", function () {
      scrollBy(-1);
    });

    nextBtn.addEventListener("click", function () {
      scrollBy(1);
    });

    // ── scroll listener ────────────────────────────────────────────────────

    track.addEventListener("scroll", onScroll, { passive: true });

    // ── ResizeObserver ─────────────────────────────────────────────────────

    if (typeof ResizeObserver !== "undefined") {
      var ro = new ResizeObserver(function () {
        update();
      });
      ro.observe(track);
    }

    // ── init ───────────────────────────────────────────────────────────────

    update();
  }

  // ── bootstrap ─────────────────────────────────────────────────────────────

  function init() {
    var wraps = document.querySelectorAll("[data-hscroll]");
    for (var i = 0; i < wraps.length; i++) {
      createScroller(wraps[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
