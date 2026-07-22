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
 *   [data-deck-card]         — each card, a real <a href="/events/N/">, with
 *                              a data-cardbg gradient value used as the hero
 *                              background *fallback* (category gradient —
 *                              present on every card regardless of whether
 *                              it shows a poster image or the gradient
 *                              fallback tile itself)
 *   .deck-card-img            — poster <img>, when present. Its rendered
 *                              edge colour (see cacheEdgeColor below)
 *                              is the *primary* hero background source,
 *                              cached on the card's `data-edge-rgb`.
 *   [data-deck-dots]         — optional dot-indicator wrapper (nested inside
 *                              [data-deck], only rendered when there is more
 *                              than one card)
 *   [data-deck-dot]          — each dot button
 *   [data-hero-card]         — ancestor of [data-deck] whose background is
 *                              swapped on every render() — 2026-07-21
 *                              correction: not the front card's category
 *                              (data-cardbg) but an average of its poster
 *                              image's own edge pixels, so the hero tint
 *                              follows the actual artwork. data-cardbg
 *                              stays the fallback when there's no poster,
 *                              the image hasn't loaded yet, or canvas
 *                              extraction fails. The template still sets an
 *                              initial inline background on [data-hero-card]
 *                              (category-based, for the first paint before
 *                              any image has loaded) — unchanged here.
 *
 * Once the initial depth layout has been applied, the deck container gets
 * `data-deck-ready`, the signal that layout is measurable. It must always be
 * set (even for a single-card deck with no autoplay) so manual browser checks
 * have a stable point to measure from.
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

  var EDGE_SAMPLE_W = 32;
  var EDGE_SAMPLE_H = 40; // 4:5, matches the deck's own aspect-ratio

  var mqlReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function prefersReducedMotion() {
    return mqlReducedMotion.matches;
  }

  // Average the 4-edge border pixels of a downscaled poster into one RGB
  // colour, cached on the card's own dataset (data-edge-rgb) so it's only
  // computed once per image. try/catch guards canvas readback — getImageData
  // throws SecurityError on a tainted canvas; posters are same-origin
  // uploaded media today so this isn't expected to fire, but a future
  // external image source (or any other decode failure) must not break the
  // deck, so any failure here just leaves data-edge-rgb unset and the caller
  // falls back to data-cardbg (see heroBackgroundFor below).
  function cacheEdgeColor(card, img) {
    if (card.dataset.edgeRgb) { return; } // already computed for this card
    try {
      var canvas = document.createElement("canvas");
      canvas.width = EDGE_SAMPLE_W;
      canvas.height = EDGE_SAMPLE_H;
      var ctx = canvas.getContext("2d");
      if (!ctx) { return; }
      ctx.drawImage(img, 0, 0, EDGE_SAMPLE_W, EDGE_SAMPLE_H);
      var data = ctx.getImageData(0, 0, EDGE_SAMPLE_W, EDGE_SAMPLE_H).data;
      var sumR = 0, sumG = 0, sumB = 0, count = 0;
      for (var y = 0; y < EDGE_SAMPLE_H; y++) {
        for (var x = 0; x < EDGE_SAMPLE_W; x++) {
          var onEdge = x === 0 || y === 0 || x === EDGE_SAMPLE_W - 1 || y === EDGE_SAMPLE_H - 1;
          if (!onEdge) { continue; }
          var i = (y * EDGE_SAMPLE_W + x) * 4;
          sumR += data[i];
          sumG += data[i + 1];
          sumB += data[i + 2];
          count++;
        }
      }
      if (count === 0) { return; }
      card.dataset.edgeRgb =
        Math.round(sumR / count) + "," + Math.round(sumG / count) + "," + Math.round(sumB / count);
    } catch (err) {
      // Canvas readback failed — leave data-edge-rgb unset, data-cardbg
      // fallback handles it (see comment above).
    }
  }

  // Primary source: the front card's own poster edge colour (once cached).
  // Fallback: its data-cardbg category gradient (also covers no-poster
  // cards, not-yet-loaded images, and canvas extraction failures).
  function heroBackgroundFor(card) {
    if (!card) { return null; }
    if (card.dataset.edgeRgb) {
      var rgb = card.dataset.edgeRgb;
      return (
        "linear-gradient(105deg, var(--surface) 10%, rgba(" + rgb + ", 0.35) 55%, " +
        "rgba(" + rgb + ", 0.8) 100%)"
      );
    }
    return card.getAttribute("data-cardbg");
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
    // Ancestor "hero card" whose background follows the active poster
    // (edge colour once available — see heroBackgroundFor above).
    var heroCard = deckEl.closest("[data-hero-card]");

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

    function updateHeroBackground() {
      if (!heroCard) { return; }
      var bg = heroBackgroundFor(cards[offset]);
      if (bg) {
        heroCard.style.background = bg;
      }
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
      updateHeroBackground();
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

    // Per-card poster edge-colour extraction (2026-07-21 correction — the
    // hero background follows the actual artwork, not the category). An
    // already-loaded image (cache hit, `complete` true) is scanned right
    // away; otherwise a one-shot `load` listener scans it once it finishes.
    // Either way, if the card being scanned is the *current* front card,
    // updateHeroBackground() re-runs so the hero swaps from the data-cardbg
    // fallback to the real edge colour the moment it becomes available,
    // without waiting for the next advance().
    cards.forEach(function (card) {
      var img = card.querySelector(".deck-card-img");
      if (!img) { return; } // no-poster card — data-cardbg fallback only
      if (img.complete && img.naturalWidth > 0) {
        cacheEdgeColor(card, img);
        return;
      }
      img.addEventListener("load", function () {
        cacheEdgeColor(card, img);
        if (cards[offset] === card) { updateHeroBackground(); }
      });
      // No explicit "error" handler needed: a failed load leaves
      // data-edge-rgb unset, and heroBackgroundFor() already falls back to
      // data-cardbg for that case.
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
