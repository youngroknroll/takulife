/**
 * carousel.js — Home hero card fan (tarot-style hand) for takulife
 *
 * Cards are laid out as a horizontal, slightly-rotated fan (like a tarot spread
 * / hand of cards). As the pointer moves across the deck, the card nearest the
 * cursor lifts and straightens, and the cards to its left/right part away from
 * it — so the selection follows the cursor naturally. Click navigates.
 *
 * DOM contract (set by home.html template):
 *   [data-carousel]           — deck wrapper (role=region)
 *   [data-carousel-track]     — .poster-deck containing .deck-card elements
 *   [data-card-index]         — deck-card elements (original order index)
 *
 * Reduced-motion: renders a static fan (no cursor tracking), still clickable.
 */

(function () {
  "use strict";

  var mqlReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  function prefersReducedMotion() { return mqlReducedMotion.matches; }

  // Fan geometry (px / deg)
  var REST_X = 58;      // horizontal gap between adjacent card slots
  var REST_ANGLE = 6;   // fan rotation per step from center
  var REST_ARC = 7;     // downward arc per step from center
  var LIFT = 28;        // how far the focused card rises
  var PART = 38;        // extra spread applied to cards beside the focused one
  var FOCUS_SCALE = 1.16;
  var AUTO_INTERVAL = 1300; // auto-shuffle: focus sweeps one card per tick

  function createFan(container) {
    var track = container.querySelector("[data-carousel-track]");
    var cards = track
      ? Array.prototype.slice.call(track.querySelectorAll("[data-card-index]"))
      : [];

    if (!track || cards.length === 0) { return; }

    track.classList.add("fan");

    var n = cards.length;
    var center = (n - 1) / 2;
    var focused = null;

    // ── overflow guard ───────────────────────────────────────────────────
    // The fan's widest reach (a parted neighbour at either end) is
    // center*REST_X + PART either side of the track's own center. On a
    // narrow viewport that reach can exceed the track's width and push the
    // page wider than the screen. scaleX shrinks REST_X/PART just enough to
    // keep the fan inside the track; on desktop widths (where the fan
    // already fits) it resolves to exactly 1, so layout is pixel-identical.
    var scaleX = 1;

    function computeScaleX() {
      var trackWidth = track.clientWidth;
      var maxReach = center * REST_X + PART;
      if (!trackWidth || maxReach <= 0) { scaleX = 1; return; }
      var cardWidth = cards[0].offsetWidth || 0;
      var available = trackWidth / 2 - cardWidth / 2;
      scaleX = Math.min(1, Math.max(0, available / maxReach));
    }

    // ── layout ────────────────────────────────────────────────────────────
    // f === null → resting fan. Otherwise card f is lifted and neighbours part.
    function applyLayout(f) {
      for (var i = 0; i < n; i++) {
        var card = cards[i];
        var tx = (i - center) * REST_X * scaleX;
        var ty = Math.abs(i - center) * REST_ARC;
        var rot = (i - center) * REST_ANGLE;
        var scale = 1;
        var z = 50 - Math.round(Math.abs(i - center));

        if (f !== null) {
          if (i === f) {
            ty = -LIFT;
            rot = 0;
            scale = FOCUS_SCALE;
            z = 100;
          } else {
            tx += (i < f ? -PART : PART) * scaleX; // part away from the focused card
            z = 60 - Math.abs(i - f);
          }
        }

        card.style.transform =
          "translateX(" + tx + "px) translateY(" + ty + "px) " +
          "rotate(" + rot + "deg) scale(" + scale + ")";
        card.style.zIndex = String(z);
      }
    }

    // Map a pointer X to the nearest resting slot index (stable: based on the
    // resting slot centers, not the current parted positions).
    function focusFromX(clientX) {
      var rect = track.getBoundingClientRect();
      var rel = clientX - rect.left - rect.width / 2;
      var effRestX = REST_X * scaleX || REST_X;
      var idx = Math.round(rel / effRestX + center);
      if (idx < 0) { idx = 0; }
      if (idx > n - 1) { idx = n - 1; }
      return idx;
    }

    // ── auto-shuffle ──────────────────────────────────────────────────────
    // Idle animation: the focus sweeps back and forth across the fan, so the
    // deck looks alive. Pointing at the deck stops it; leaving resumes it.
    var autoTimer = null;
    var autoIdx = Math.round(center);
    var autoDir = 1;

    function autoTick() {
      autoIdx += autoDir;
      if (autoIdx >= n - 1) { autoIdx = n - 1; autoDir = -1; }
      else if (autoIdx <= 0) { autoIdx = 0; autoDir = 1; }
      focused = autoIdx;
      applyLayout(autoIdx);
    }

    function startAuto() {
      if (prefersReducedMotion()) { return; }
      stopAuto();
      autoTimer = window.setInterval(autoTick, AUTO_INTERVAL);
    }

    function stopAuto() {
      if (autoTimer !== null) {
        window.clearInterval(autoTimer);
        autoTimer = null;
      }
    }

    // ── keyboard (roving tabindex) ───────────────────────────────────────
    // Only the resting first card is a tab stop (see home.html). Arrow keys
    // move focus — and the tabindex="0" — between cards; Home/End jump to
    // the ends. Tab/Shift+Tab leave the widget as usual. Keyboard nav and
    // the resulting lift (applyLayout) always run, even under reduced
    // motion — only the idle auto-shuffle and pointer-tracking below are
    // motion-gated (the lift *transition* itself is disabled via CSS).
    function cardLink(i) {
      return cards[i].querySelector(".deck-slide");
    }

    function setFocused(i) {
      focused = i;
      for (var j = 0; j < n; j++) {
        var link = cardLink(j);
        if (link) { link.tabIndex = j === i ? 0 : -1; }
      }
      applyLayout(i);
    }

    container.addEventListener("keydown", function (e) {
      var key = e.key;
      if (key !== "ArrowLeft" && key !== "ArrowRight" && key !== "Home" && key !== "End") {
        return;
      }
      e.preventDefault();
      stopAuto();
      var current = focused !== null ? focused : 0;
      var next = current;
      if (key === "ArrowLeft") { next = Math.max(0, current - 1); }
      else if (key === "ArrowRight") { next = Math.min(n - 1, current + 1); }
      else if (key === "Home") { next = 0; }
      else { next = n - 1; } // End
      setFocused(next);
      var link = cardLink(next);
      if (link) { link.focus(); }
    });

    // Focusing a card (e.g. Tab into the deck) halts the shuffle, lifts it,
    // and keeps the roving tabindex in sync with the arrow-key path above.
    cards.forEach(function (card, i) {
      card.addEventListener("focusin", function () {
        stopAuto();
        setFocused(i);
      });
    });
    container.addEventListener("focusout", function (evt) {
      if (!container.contains(evt.relatedTarget)) {
        startAuto();
      }
    });

    // ── pointer interaction (motion-gated) ───────────────────────────────
    if (!prefersReducedMotion()) {
      // Pointer over the deck takes control and halts the shuffle.
      track.addEventListener("mouseenter", stopAuto);
      track.addEventListener("mousemove", function (e) {
        stopAuto();
        var f = focusFromX(e.clientX);
        if (f !== focused) {
          focused = f;
          applyLayout(f);
        }
      });
      track.addEventListener("mouseleave", function () {
        startAuto(); // resume sweeping
      });
    }

    // Keep the fan inside the viewport as it's resized/rotated (debounced —
    // no need to recompute on every intermediate resize tick).
    var resizeTimer = null;
    function handleResize() {
      if (resizeTimer !== null) { window.clearTimeout(resizeTimer); }
      resizeTimer = window.setTimeout(function () {
        resizeTimer = null;
        computeScaleX();
        applyLayout(focused);
      }, 150);
    }
    window.addEventListener("resize", handleResize);
    window.addEventListener("orientationchange", handleResize);

    // Initial state: static fan under reduced-motion, else start the shuffle.
    computeScaleX();
    if (prefersReducedMotion()) {
      applyLayout(null);
    } else {
      applyLayout(autoIdx);
      startAuto();
    }
  }

  function init() {
    var containers = document.querySelectorAll("[data-carousel]");
    for (var i = 0; i < containers.length; i++) {
      createFan(containers[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
