/**
 * 홈 히어로의 카드 더미(deck). 앞 카드는 원래 크기, 뒤 카드일수록 작고
 * 아래로 처지며 흐려진다. 모든 카드가 실제 <a> 링크라 앞 카드는 그냥
 * 클릭하면 이동하고, 뒤 카드를 클릭하면 이동 대신 앞으로 가져온다.
 * 점 표시와 좌우 화살표 키도 같은 방식으로 이동한다.
 * 히어로 배경은 앞 카드 포스터 이미지의 가장자리 색을 평균 내 우려낸
 * 색을 쓰고, 포스터가 없거나 아직 로드되지 않았거나 캔버스 추출이
 * 실패하면 카테고리별 고정 그라디언트로 대체한다.
 * 자동 재생은 3초 간격이며 마우스오버·포커스 시 멈추고, 터치가 한 번이라도
 * 감지되면 이후 다시 켜지지 않는다(터치에는 마우스가 떠나는 개념이 없어서다).
 * 동작 최소화 설정에서는 자동 재생을 시작하지 않는다.
 */

(function () {
  "use strict";

  var AUTOPLAY_INTERVAL = 3000;
  var DEPTH_STEP_Y = 12; // 깊이 단계당 px
  var DEPTH_STEP_SCALE = 0.035; // 깊이 단계당 축소 비율
  var MAX_VISIBLE_DEPTH = 4; // 이보다 깊으면 완전히 숨긴다

  var EDGE_SAMPLE_W = 32;
  var EDGE_SAMPLE_H = 40; // 4:5, 덱 자체의 가로세로 비율과 맞춤

  var mqlReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function prefersReducedMotion() {
    return mqlReducedMotion.matches;
  }

  // 포스터를 축소한 뒤 가장자리 픽셀들을 평균 내 하나의 RGB 색으로
  // 만들고 카드의 data-edge-rgb에 캐시해 이미지당 한 번만 계산한다.
  // 캔버스 읽기가 실패해도(외부 이미지 등으로 인한 보안 오류 포함) 덱
  // 자체가 깨지면 안 되므로, 실패 시 그냥 data-edge-rgb를 비워두고
  // 아래 heroBackgroundFor에서 data-cardbg로 대체한다.
  function cacheEdgeColor(card, img) {
    if (card.dataset.edgeRgb) { return; } // 이미 계산됨
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
      // 캔버스 읽기 실패 — data-edge-rgb를 비워두면 data-cardbg로 대체된다.
    }
  }

  // 우선순위: 앞 카드 포스터의 가장자리 색(캐시됐다면). 없으면 카테고리
  // 그라디언트(data-cardbg)로 대체 — 포스터가 없거나 아직 로드 전이거나
  // 추출에 실패한 경우 모두 포함.
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
    // 활성 포스터의 색을 따라가는 조상 "히어로 카드"
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
      // 앞 카드만 Tab으로 멈춘다.
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

    // 앞이 아닌 카드를 클릭하면 링크를 바로 따라가는 대신 앞으로 가져온다.
    // 앞 카드는 가로채지 않아 그대로 실제 href로 이동한다.
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

    // 키보드: 포커스가 덱 안에 있을 때 좌우 화살표로 이동한다.
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
    // 터치에는 "마우스가 떠난다"는 개념이 없어 아예 영구적으로 멈춘다.
    deckEl.addEventListener("touchstart", function () {
      touched = true;
      stop();
    }, { passive: true });

    // 실행 중 동작 최소화 설정이 바뀌어도 반영한다.
    mqlReducedMotion.addEventListener("change", function () {
      if (prefersReducedMotion()) {
        stop();
      } else {
        start();
      }
    });

    // 카드별로 포스터 가장자리 색을 추출한다. 이미 로드된 이미지는 바로
    // 처리하고, 아니면 load 이벤트를 한 번만 듣는다. 처리된 카드가 지금
    // 앞 카드라면 다음 넘김을 기다리지 않고 바로 히어로 배경을 갱신한다.
    cards.forEach(function (card) {
      var img = card.querySelector(".deck-card-img");
      if (!img) { return; } // 포스터가 없는 카드는 data-cardbg만 쓴다
      if (img.complete && img.naturalWidth > 0) {
        cacheEdgeColor(card, img);
        return;
      }
      img.addEventListener("load", function () {
        cacheEdgeColor(card, img);
        if (cards[offset] === card) { updateHeroBackground(); }
      });
      // 로드 실패 시 별도 처리 없이 data-edge-rgb를 비워두면
      // heroBackgroundFor()가 알아서 data-cardbg로 대체한다.
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
