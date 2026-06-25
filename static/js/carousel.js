/**
 * carousel.js — Home hero poster carousel for TakuLog
 *
 * Handles:
 *   - Desktop auto-advance (4500ms), paused on hover/focus/reduced-motion/mobile
 *   - Pause/play toggle button (WCAG 2.2.2 compliance)
 *   - ArrowLeft/ArrowRight keyboard navigation when carousel is focused
 *   - Dot button navigation
 *   - aria-live switched off during autoplay, polite on manual interaction
 *   - Mobile (≤860px): CSS-only scroll-snap, no autoplay
 *
 * DOM contract (set by home.html template):
 *   [data-carousel]           — carousel container (role=region, tabindex=0)
 *   [data-carousel-track]     — flex track containing slides
 *   [data-carousel-controls]  — controls wrapper (dots + pause/play)
 *   [data-dot-index]          — dot buttons
 *   [data-carousel-pause]     — pause/play toggle
 *   [data-slide-index]        — slide anchor elements
 *
 * All DOM text writes use textContent only (no innerHTML with data).
 */

(function () {
  "use strict";

  var AUTOPLAY_INTERVAL = 4500;
  var MOBILE_BREAKPOINT = 860;

  // ── media queries ──────────────────────────────────────────────────────────

  var mqlMobile = window.matchMedia("(max-width: " + MOBILE_BREAKPOINT + "px)");
  var mqlReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function isMobile() {
    return mqlMobile.matches;
  }

  function prefersReducedMotion() {
    return mqlReducedMotion.matches;
  }

  // ── carousel state ─────────────────────────────────────────────────────────

  function createCarousel(container) {
    var track = container.querySelector("[data-carousel-track]");
    var controlsEl = container.querySelector("[data-carousel-controls]");
    var pauseBtn = container.querySelector("[data-carousel-pause]");
    var slides = container.querySelectorAll("[data-slide-index]");
    var dots = container.querySelectorAll("[data-dot-index]");

    if (!track || slides.length === 0) {
      return;
    }

    var totalSlides = slides.length;
    var currentIndex = 0;
    var timer = null;
    var userPaused = false;
    var hovered = false;
    var focused = false;

    // ── slide navigation ───────────────────────────────────────────────────

    function goTo(index, isManual) {
      currentIndex = (index + totalSlides) % totalSlides;

      // Scroll the track to show the correct slide
      var slide = slides[currentIndex];
      if (slide) {
        slide.scrollIntoView
          ? track.scrollTo({ left: slide.offsetLeft, behavior: "smooth" })
          : (track.scrollLeft = slide.offsetLeft);
      }

      // Update dots
      for (var i = 0; i < dots.length; i++) {
        dots[i].setAttribute("aria-current", i === currentIndex ? "true" : "false");
      }

      // Switch aria-live: off during autoplay, polite on manual interaction
      if (isManual) {
        track.setAttribute("aria-live", "polite");
      } else {
        track.setAttribute("aria-live", "off");
      }
    }

    function next(isManual) {
      goTo(currentIndex + 1, isManual);
    }

    function prev() {
      goTo(currentIndex - 1, true);
    }

    // ── autoplay ──────────────────────────────────────────────────────────

    function shouldAutoplay() {
      return !isMobile() && !prefersReducedMotion() && !userPaused && !hovered && !focused;
    }

    function startAutoplay() {
      stopAutoplay();
      if (!shouldAutoplay()) {
        return;
      }
      timer = setInterval(function () {
        if (shouldAutoplay()) {
          next(false);
        }
      }, AUTOPLAY_INTERVAL);
    }

    function stopAutoplay() {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    }

    function pauseAutoplay(reason) {
      if (reason === "hover") { hovered = true; }
      if (reason === "focus") { focused = true; }
      stopAutoplay();
    }

    function resumeAutoplay(reason) {
      if (reason === "hover") { hovered = false; }
      if (reason === "focus") { focused = false; }
      startAutoplay();
    }

    // ── pause/play toggle button ───────────────────────────────────────────

    function syncPauseBtn() {
      if (!pauseBtn) { return; }
      if (userPaused || isMobile() || prefersReducedMotion()) {
        pauseBtn.textContent = "▶";
        pauseBtn.setAttribute("aria-label", "슬라이드 재생");
      } else {
        pauseBtn.textContent = "⏸";
        pauseBtn.setAttribute("aria-label", "슬라이드 일시 정지");
      }
    }

    function bindPauseBtn() {
      if (!pauseBtn) { return; }
      pauseBtn.addEventListener("click", function () {
        userPaused = !userPaused;
        syncPauseBtn();
        if (userPaused) {
          stopAutoplay();
        } else {
          startAutoplay();
        }
      });
    }

    // ── dot buttons ────────────────────────────────────────────────────────

    function bindDots() {
      for (var i = 0; i < dots.length; i++) {
        (function (dot, idx) {
          dot.addEventListener("click", function () {
            goTo(idx, true);
            stopAutoplay();
            userPaused = true;
            syncPauseBtn();
          });
        })(dots[i], i);
      }
    }

    // ── keyboard navigation ────────────────────────────────────────────────

    function bindKeyboard() {
      container.addEventListener("keydown", function (evt) {
        if (evt.key === "ArrowRight") {
          evt.preventDefault();
          next(true);
          stopAutoplay();
          userPaused = true;
          syncPauseBtn();
        } else if (evt.key === "ArrowLeft") {
          evt.preventDefault();
          prev();
          stopAutoplay();
          userPaused = true;
          syncPauseBtn();
        }
      });
    }

    // ── hover pause ────────────────────────────────────────────────────────

    function bindHover() {
      container.addEventListener("mouseenter", function () {
        pauseAutoplay("hover");
      });
      container.addEventListener("mouseleave", function () {
        resumeAutoplay("hover");
      });
    }

    // ── focus pause (WCAG 2.2.2: pause on focus within) ────────────────────

    function bindFocus() {
      container.addEventListener("focusin", function () {
        pauseAutoplay("focus");
      });
      container.addEventListener("focusout", function (evt) {
        // Only resume if focus left the carousel entirely
        if (!container.contains(evt.relatedTarget)) {
          resumeAutoplay("focus");
        }
      });
    }

    // ── reduced-motion listener ────────────────────────────────────────────

    function bindReducedMotion() {
      mqlReducedMotion.addEventListener("change", function () {
        syncPauseBtn();
        if (prefersReducedMotion()) {
          stopAutoplay();
        } else {
          startAutoplay();
        }
      });
    }

    // ── mobile breakpoint listener ─────────────────────────────────────────

    function bindMobileBreakpoint() {
      mqlMobile.addEventListener("change", function () {
        syncPauseBtn();
        if (isMobile()) {
          stopAutoplay();
        } else {
          startAutoplay();
        }
      });
    }

    // ── init ───────────────────────────────────────────────────────────────

    syncPauseBtn();
    bindPauseBtn();
    bindDots();
    bindKeyboard();
    bindHover();
    bindFocus();
    bindReducedMotion();
    bindMobileBreakpoint();

    // Make controls visible (they're aria-hidden="true" by default for
    // CSS-only no-JS fallback; JS reveals and manages them)
    if (controlsEl) {
      controlsEl.removeAttribute("aria-hidden");
    }

    // Start autoplay only on desktop, without reduced-motion
    startAutoplay();
  }

  // ── init ──────────────────────────────────────────────────────────────────

  function init() {
    var carousels = document.querySelectorAll("[data-carousel]");
    for (var i = 0; i < carousels.length; i++) {
      createCarousel(carousels[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
