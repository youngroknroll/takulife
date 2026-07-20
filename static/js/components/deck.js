/**
 * deck.js — Home hero stack deck for takulife
 *
 * Editorial redesign replacement for carousel.js's tarot-style fan (deleted —
 * this is the only consumer). Cards are stacked with a fixed depth offset
 * (front card full-size, back cards progressively smaller/lower/fainter).
 * Every card is a real <a> to its own event, so the front card's image area
 * navigates on click like any link — no JS interception. Clicking a *back*
 * card instead brings it to the front (its own click is prevented so the
 * user can look before navigating); dots and ArrowLeft/ArrowRight jump/step
 * the same way.
 *
 * DOM contract (set by home.html template):
 *   [data-deck]              — deck container (position: relative)
 *   [data-deck-card]         — each card, a real <a href="/events/N/">
 *   [data-deck-dots]         — optional dot-indicator wrapper (nested inside
 *                              [data-deck], only rendered when there is more
 *                              than one card)
 *   [data-deck-dot]          — each dot button
 *
 * Once the initial depth layout has been applied, the deck container gets
 * `data-deck-ready` — the e2e mobile-overflow smoke test waits on
 * `[data-deck][data-deck-ready]` before measuring layout, so this attribute
 * must always be set (even for a single-card deck with no autoplay).
 *
 * Motion contract (design-rules.md §3.1-2 — WCAG 2.2.2): autoplay every
 * 4200ms, paused on hover, paused on focusin (cards are real links, so
 * focus-pause applies), and permanently stopped after the first touch (no
 * hover-out equivalent on touch). prefers-reduced-motion never starts the
 * timer, and a runtime change is re-checked (same pattern as hscroll.js /
 * the old carousel.js).
 */

(function () {
  "use strict";

  var AUTOPLAY_INTERVAL = 4200;
  var DEPTH_STEP_Y = 12; // px per depth step
  var DEPTH_STEP_SCALE = 0.035; // scale reduction per depth step
  var MAX_VISIBLE_DEPTH = 4; // depths beyond this are fully hidden

  var mqlReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function prefersReducedMotion() {
    return mqlReducedMotion.matches;
  }

  function createDeck(deckEl) {
    var cards = Array.prototype.slice.call(deckEl.querySelectorAll("[data-deck-card]"));
    var n = cards.length;

    if (n === 0) {
      return;
    }

    var dotsWrap = deckEl.querySelector("[data-deck-dots]");
    var dots = dotsWrap
      ? Array.prototype.slice.call(dotsWrap.querySelectorAll("[data-deck-dot]"))
      : [];

    var offset = 0;
    var timer = null;
    var hovered = false;
    var focused = false;
    var touched = false;

    function applyDepth(card, d) {
      var hidden = d > MAX_VISIBLE_DEPTH;
      card.style.transform =
        "translateY(" + (d * DEPTH_STEP_Y) + "px) scale(" + (1 - d * DEPTH_STEP_SCALE).toFixed(3) + ")";
      card.style.opacity = hidden ? "0" : "1";
      card.style.zIndex = String(30 - d);
      card.style.pointerEvents = hidden ? "none" : "auto";
      // Roving tabindex: only the front card is a Tab stop.
      card.tabIndex = d === 0 ? 0 : -1;
    }

    function render() {
      cards.forEach(function (card, i) {
        applyDepth(card, (i - offset + n) % n);
      });
      dots.forEach(function (dot, i) {
        var active = i === offset;
        dot.classList.toggle("active", active);
        dot.setAttribute("aria-current", active ? "true" : "false");
      });
    }

    function goTo(i) {
      offset = ((i % n) + n) % n;
      render();
    }

    function advance() { goTo(offset + 1); }
    function retreat() { goTo(offset - 1); }

    function stop() {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    }

    function start() {
      stop();
      if (n < 2 || prefersReducedMotion() || hovered || focused || touched) {
        return;
      }
      timer = window.setInterval(advance, AUTOPLAY_INTERVAL);
    }

    // Click on a non-front card brings it to the front instead of following
    // its link immediately; the front card has no interception, so its own
    // click navigates via the real href (image-area click navigation).
    deckEl.addEventListener("click", function (e) {
      var card = e.target && e.target.closest ? e.target.closest("[data-deck-card]") : null;
      if (!card) { return; }
      var idx = cards.indexOf(card);
      if (idx === -1 || idx === offset) { return; }
      e.preventDefault();
      stop();
      goTo(idx);
      start();
    });

    // Keyboard: ArrowLeft/ArrowRight while focus is inside the deck.
    deckEl.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") { return; }
      e.preventDefault();
      stop();
      if (e.key === "ArrowLeft") { retreat(); } else { advance(); }
      start();
      var front = cards[offset];
      if (front) { front.focus(); }
    });

    dots.forEach(function (dot, i) {
      dot.addEventListener("click", function () {
        stop();
        goTo(i);
        start();
      });
    });

    deckEl.addEventListener("mouseenter", function () { hovered = true; stop(); });
    deckEl.addEventListener("mouseleave", function () { hovered = false; start(); });
    deckEl.addEventListener("focusin", function () { focused = true; stop(); });
    deckEl.addEventListener("focusout", function (e) {
      if (!deckEl.contains(e.relatedTarget)) {
        focused = false;
        start();
      }
    });
    // Touch has no hover-out equivalent — stop permanently (WCAG 2.2.2).
    deckEl.addEventListener("touchstart", function () {
      touched = true;
      stop();
    }, { passive: true });

    // Respect reduced-motion changes at runtime (same pattern as hscroll.js).
    mqlReducedMotion.addEventListener("change", function () {
      if (prefersReducedMotion()) {
        stop();
      } else {
        start();
      }
    });

    render();
    start();
    deckEl.setAttribute("data-deck-ready", "");
  }

  function init() {
    var decks = document.querySelectorAll("[data-deck]");
    for (var i = 0; i < decks.length; i++) {
      createDeck(decks[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
