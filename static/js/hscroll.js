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
 *   - Optional autoplay (data-hscroll-auto): advances every 3500ms, loops to
 *     start at end, pauses on hover/focus/manual arrow click, respects
 *     prefers-reduced-motion, only runs when overflowing
 *
 * DOM contract (set by home.html template):
 *   [data-hscroll]        — section wrap (position: relative; overflow: hidden)
 *   [data-hscroll-auto]   — opt-in attribute on wrap to enable autoplay
 *   [data-hscroll-track]  — the scrollable flex row
 *   [data-hscroll-prev]   — prev arrow button
 *   [data-hscroll-next]   — next arrow button
 *
 * Arrow visibility uses visibility:hidden (not display:none) to avoid layout shift.
 * All DOM text writes use textContent only (no innerHTML with data).
 */

(function () {
  "use strict";

  var AUTOPLAY_INTERVAL = 3500;

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
      if (autoTimer !== null) { startAutoplay(); } // reset timer on manual click
    });

    nextBtn.addEventListener("click", function () {
      scrollBy(1);
      if (autoTimer !== null) { startAutoplay(); } // reset timer on manual click
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

    // ── autoplay (opt-in via data-hscroll-auto) ────────────────────────────

    var autoTimer = null;
    var hovered = false;
    var focused = false;
    var wantsAutoplay = wrap.hasAttribute("data-hscroll-auto");

    function isOverflowing() {
      return track.scrollWidth > track.clientWidth + 1;
    }

    function shouldAutoplay() {
      return wantsAutoplay && !prefersReducedMotion() && !hovered && !focused && isOverflowing();
    }

    function stopAutoplay() {
      if (autoTimer !== null) {
        clearInterval(autoTimer);
        autoTimer = null;
      }
    }

    function startAutoplay() {
      stopAutoplay();
      if (!shouldAutoplay()) { return; }
      autoTimer = setInterval(function () {
        if (!shouldAutoplay()) { return; }
        var atEnd = track.scrollLeft + track.clientWidth >= track.scrollWidth - 1;
        if (atEnd) {
          // Loop back to start
          track.scrollTo({ left: 0, behavior: "smooth" });
        } else {
          track.scrollBy({ left: track.clientWidth * 0.9, behavior: "smooth" });
        }
      }, AUTOPLAY_INTERVAL);
    }

    if (wantsAutoplay) {
      // Pause on pointer or keyboard entering the wrap
      wrap.addEventListener("mouseenter", function () {
        hovered = true;
        stopAutoplay();
      });
      wrap.addEventListener("mouseleave", function () {
        hovered = false;
        startAutoplay();
      });
      wrap.addEventListener("focusin", function () {
        focused = true;
        stopAutoplay();
      });
      wrap.addEventListener("focusout", function (evt) {
        if (!wrap.contains(evt.relatedTarget)) {
          focused = false;
          startAutoplay();
        }
      });

      // Respect reduced-motion changes at runtime
      mqlReducedMotion.addEventListener("change", function () {
        if (prefersReducedMotion()) {
          stopAutoplay();
        } else {
          startAutoplay();
        }
      });

      startAutoplay();
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
