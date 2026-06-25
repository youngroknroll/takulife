/**
 * carousel.js — Home hero stacked card deck for TakuLog
 *
 * Handles:
 *   - Index-array rotation: front card cycles to back (unshift + pop pattern)
 *   - 3500ms auto-advance (disabled under prefers-reduced-motion)
 *   - Click front card  → navigate (allow <a> default)
 *   - Click back card   → advance deck (preventDefault, rotate)
 *   - Dot navigation: clicking a dot rotates deck so that card becomes front
 *   - Manual click/dot advances and resets the autoplay timer (autoplay keeps running)
 *   - Pause on mouseenter/focusin, resume on mouseleave/focusout
 *   - aria-live off during autoplay, polite on manual interaction
 *   - n <= 1 events: single card, no auto-advance, no dots needed
 *
 * DOM contract (set by home.html template):
 *   [data-carousel]           — deck wrapper (role=region)
 *   [data-carousel-track]     — .poster-deck containing .deck-card elements
 *   [data-carousel-controls]  — controls wrapper (dots)
 *   [data-dot-index]          — dot buttons
 *   [data-card-index]         — deck-card elements (original order index)
 *   [data-slide]              — current visual stack depth (0 = front)
 *
 * All DOM text writes use textContent only (no innerHTML with data).
 */

(function () {
  "use strict";

  var AUTOPLAY_INTERVAL = 3500;
  var MAX_VISIBLE_DEPTH = 5; /* data-slide 0..5 have distinct positions; 6+ capped */

  var mqlReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function prefersReducedMotion() {
    return mqlReducedMotion.matches;
  }

  // ── deck factory ───────────────────────────────────────────────────────────

  function createDeck(container) {
    var track = container.querySelector("[data-carousel-track]");
    var controlsEl = container.querySelector("[data-carousel-controls]");
    var dots = container.querySelectorAll("[data-dot-index]");
    var cards = track ? track.querySelectorAll("[data-card-index]") : [];

    if (!track || cards.length === 0) {
      return;
    }

    var totalCards = cards.length;

    // Single card: render static, no interaction needed
    if (totalCards <= 1) {
      if (controlsEl) { controlsEl.setAttribute("aria-hidden", "true"); }
      return;
    }

    // indexOrder[0] = original card index currently at front (data-slide=0)
    // e.g. [0, 1, 2, 3] initially
    var indexOrder = [];
    for (var k = 0; k < totalCards; k++) {
      indexOrder.push(k);
    }

    var timer = null;
    var hovered = false;
    var focused = false;

    // ── visual update ──────────────────────────────────────────────────────

    function applySlidePositions() {
      for (var i = 0; i < indexOrder.length; i++) {
        var cardOriginalIndex = indexOrder[i];
        var card = cards[cardOriginalIndex];
        var depth = i; // 0 = front
        var depthAttr = depth > MAX_VISIBLE_DEPTH ? String(MAX_VISIBLE_DEPTH + 1) : String(depth);
        card.setAttribute("data-slide", depthAttr);

        // Front card anchor is focusable/navigable; back cards get tabindex=-1
        var anchor = card.querySelector("a");
        if (anchor) {
          anchor.setAttribute("tabindex", depth === 0 ? "0" : "-1");
        }
      }
    }

    function updateDots() {
      var frontOriginalIndex = indexOrder[0];
      for (var i = 0; i < dots.length; i++) {
        var dotIdx = parseInt(dots[i].getAttribute("data-dot-index"), 10);
        dots[i].setAttribute("aria-current", dotIdx === frontOriginalIndex ? "true" : "false");
      }
    }

    // ── rotation ───────────────────────────────────────────────────────────

    // Move front card to back: indexOrder[0] pops to the end
    function rotateForward(isManual) {
      var front = indexOrder.shift();
      indexOrder.push(front);

      applySlidePositions();
      updateDots();

      track.setAttribute("aria-live", isManual ? "polite" : "off");
    }

    // Rotate deck so that the card with original index `targetIndex` is front
    function rotateTo(targetIndex, isManual) {
      // Find position of targetIndex in indexOrder
      var pos = indexOrder.indexOf(targetIndex);
      if (pos <= 0) {
        // Already front or not found
        applySlidePositions();
        updateDots();
        return;
      }
      // Rotate pos times to bring target to front
      for (var r = 0; r < pos; r++) {
        var front = indexOrder.shift();
        indexOrder.push(front);
      }
      applySlidePositions();
      updateDots();

      track.setAttribute("aria-live", isManual ? "polite" : "off");
    }

    // ── autoplay ───────────────────────────────────────────────────────────

    function shouldAutoplay() {
      return !prefersReducedMotion() && !hovered && !focused;
    }

    function startAutoplay() {
      stopAutoplay();
      if (!shouldAutoplay()) { return; }
      timer = setInterval(function () {
        if (shouldAutoplay()) {
          rotateForward(false);
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

    // ── dot clicks ─────────────────────────────────────────────────────────
    // Advance to the chosen card and reset the autoplay timer (keeps playing).

    function bindDots() {
      for (var i = 0; i < dots.length; i++) {
        (function (dot) {
          dot.addEventListener("click", function () {
            var target = parseInt(dot.getAttribute("data-dot-index"), 10);
            rotateTo(target, true);
            startAutoplay();
          });
        })(dots[i]);
      }
    }

    // ── card clicks ────────────────────────────────────────────────────────
    // Front card (data-slide=0): let <a> navigate (don't preventDefault)
    // Back card (data-slide!=0): advance deck, preventDefault

    function bindCardClicks() {
      for (var i = 0; i < cards.length; i++) {
        (function (card) {
          card.addEventListener("click", function (evt) {
            var depth = card.getAttribute("data-slide");
            if (depth !== "0") {
              evt.preventDefault();
              evt.stopPropagation();
              // Bring this card to front
              var origIdx = parseInt(card.getAttribute("data-card-index"), 10);
              rotateTo(origIdx, true);
              startAutoplay();
            }
            // depth === "0": allow default navigation
          });
        })(cards[i]);
      }
    }

    // ── hover and focus pause ──────────────────────────────────────────────

    function bindHoverFocus() {
      container.addEventListener("mouseenter", function () {
        pauseAutoplay("hover");
      });
      container.addEventListener("mouseleave", function () {
        resumeAutoplay("hover");
      });
      container.addEventListener("focusin", function () {
        pauseAutoplay("focus");
      });
      container.addEventListener("focusout", function (evt) {
        if (!container.contains(evt.relatedTarget)) {
          resumeAutoplay("focus");
        }
      });
    }

    // ── reduced-motion listener ────────────────────────────────────────────

    function bindReducedMotion() {
      mqlReducedMotion.addEventListener("change", function () {
        if (prefersReducedMotion()) {
          stopAutoplay();
        } else {
          startAutoplay();
        }
      });
    }

    // ── init ───────────────────────────────────────────────────────────────

    applySlidePositions();
    updateDots();

    bindDots();
    bindCardClicks();
    bindHoverFocus();
    bindReducedMotion();

    // Reveal controls (aria-hidden="true" is the no-JS/CSS-fallback state)
    if (controlsEl) {
      controlsEl.removeAttribute("aria-hidden");
    }

    startAutoplay();
  }

  // ── bootstrap ─────────────────────────────────────────────────────────────

  function init() {
    var containers = document.querySelectorAll("[data-carousel]");
    for (var i = 0; i < containers.length; i++) {
      createDeck(containers[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
