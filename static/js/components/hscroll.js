/**
 * 이전/다음 화살표가 있는 가로 스크롤 컴포넌트. 넘침·스크롤 위치에 따라
 * 화살표를 보이거나 숨기고 양 끝 흐림 효과를 토글한다. 클릭 시 트랙
 * 너비의 약 90%만큼 스크롤하며, 동작 최소화 설정에서는 부드러운 스크롤
 * 대신 즉시 이동한다. data-hscroll-auto가 있으면 3.5초마다 자동 이동하며
 * 끝에 닿으면 처음으로 돌아가고, 마우스오버·포커스·수동 클릭 시 멈추며
 * 데스크톱 너비에서만 동작한다(모바일 레일은 자동 슬라이드 없음).
 * 화살표는 레이아웃이 흔들리지 않도록 display:none이 아니라 visibility로 숨긴다.
 */

(function () {
  "use strict";

  var AUTOPLAY_INTERVAL = 3500;

  var mqlReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  // 45rem을 모바일 상한으로 쓰는 CSS 기준과 맞춰, 그보다 넓을 때만
  // 데스크톱으로 판단해 모바일에서는 자동재생을 끈다.
  var mqlDesktop = window.matchMedia("(min-width: 45.0625rem)");

  function prefersReducedMotion() {
    return mqlReducedMotion.matches;
  }

  function isDesktopViewport() {
    return mqlDesktop.matches;
  }

  // ── 스크롤러 생성 ──────────────────────────────────────────────────────

  function createScroller(wrap) {
    var track = wrap.querySelector("[data-hscroll-track]");
    var prevBtn = wrap.querySelector("[data-hscroll-prev]");
    var nextBtn = wrap.querySelector("[data-hscroll-next]");

    if (!track || !prevBtn || !nextBtn) {
      return;
    }

    var rafPending = false;

    // ── 화살표 표시와 흐림 효과 갱신 ──────────────────────────────

    function update() {
      var scrollLeft = track.scrollLeft;
      var clientWidth = track.clientWidth;
      var scrollWidth = track.scrollWidth;

      var overflowing = scrollWidth > clientWidth + 1;
      var atStart = scrollLeft <= 1;
      var atEnd = scrollLeft + clientWidth >= scrollWidth - 1;

      if (!overflowing) {
        // 다 보이면 화살표를 숨기고 흐림 효과도 없앤다. CSS에서는
        // .at-start와 .at-end가 동시에 있어야 흐림 효과가 완전히 사라지므로
        // 지우는 대신 둘 다 추가해야 한다.
        prevBtn.style.visibility = "hidden";
        nextBtn.style.visibility = "hidden";
        wrap.classList.add("at-start", "at-end");
        // 스크롤할 게 없으니 Tab으로 멈출 이유도 없다.
        track.tabIndex = -1;
        return;
      }

      // 리사이즈 등으로 다시 넘치게 됐으면 Tab 정지 지점으로 되돌린다.
      track.tabIndex = 0;

      // 스크롤 위치에 따라 각 화살표를 보이거나 숨긴다
      prevBtn.style.visibility = atStart ? "hidden" : "visible";
      nextBtn.style.visibility = atEnd ? "hidden" : "visible";

      // 가장자리 흐림 효과 클래스 토글
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

    // ── 스크롤 핸들러(requestAnimationFrame으로 빈도 제한) ─────────────────────────────────────────

    function onScroll() {
      if (rafPending) { return; }
      rafPending = true;
      requestAnimationFrame(function () {
        rafPending = false;
        update();
      });
    }

    // ── 화살표 클릭 ───────────────────────────────────────────────────────

    function scrollBy(direction) {
      var behavior = prefersReducedMotion() ? "instant" : "smooth";
      track.scrollBy({ left: direction * track.clientWidth * 0.9, behavior: behavior });
    }

    prevBtn.addEventListener("click", function () {
      scrollBy(-1);
      if (autoTimer !== null) { startAutoplay(); } // 수동 클릭 시 타이머 초기화
    });

    nextBtn.addEventListener("click", function () {
      scrollBy(1);
      if (autoTimer !== null) { startAutoplay(); } // 수동 클릭 시 타이머 초기화
    });

    // ── 스크롤 리스너 ────────────────────────────────────────────────────

    track.addEventListener("scroll", onScroll, { passive: true });

    // ── ResizeObserver ─────────────────────────────────────────────────────

    if (typeof ResizeObserver !== "undefined") {
      var ro = new ResizeObserver(function () {
        update();
        // 리사이즈로 넘침 여부가 바뀔 수 있으니 자동재생도 다시 평가한다.
        // startAutoplay는 조건이 안 맞으면 스스로 아무 것도 안 하므로
        // 무조건 호출해도 안전하다.
        if (wantsAutoplay) {
          startAutoplay();
        }
      });
      ro.observe(track);
    }

    // ── 자동재생(data-hscroll-auto로 opt-in) ────────────────────────────

    var autoTimer = null;
    var hovered = false;
    var focused = false;
    // 터치가 한 번이라도 감지되면 이후 자동재생이 다시 시작되지 않게 한다.
    // 터치에는 "마우스가 떠난다"는 개념이 없고, iOS는 탭 후 가짜
    // mouseleave/focus 이벤트를 보내 자동재생을 다시 켜버릴 수 있다.
    var touched = false;
    var wantsAutoplay = wrap.hasAttribute("data-hscroll-auto");

    function isOverflowing() {
      return track.scrollWidth > track.clientWidth + 1;
    }

    function shouldAutoplay() {
      return wantsAutoplay && isDesktopViewport() && !prefersReducedMotion() && !hovered && !focused && !touched && isOverflowing();
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
          // 처음으로 되돌아간다
          track.scrollTo({ left: 0, behavior: "smooth" });
        } else {
          track.scrollBy({ left: track.clientWidth * 0.9, behavior: "smooth" });
        }
      }, AUTOPLAY_INTERVAL);
    }

    if (wantsAutoplay) {
      // 포인터나 키보드가 영역에 들어오면 멈춘다
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
      wrap.addEventListener("touchstart", function () {
        touched = true;
        stopAutoplay();
      }, { passive: true });

      // 실행 중 동작 최소화 설정이 바뀌어도 반영한다
      mqlReducedMotion.addEventListener("change", function () {
        if (prefersReducedMotion()) {
          stopAutoplay();
        } else {
          startAutoplay();
        }
      });

      // 데스크톱/모바일 경계를 넘나들 때도(리사이즈, 회전 등) 다시 평가한다.
      mqlDesktop.addEventListener("change", function () {
        if (isDesktopViewport()) {
          startAutoplay();
        } else {
          stopAutoplay();
        }
      });

      startAutoplay();
    }

    // ── 초기화 ───────────────────────────────────────────────────────────────

    update();
  }

  // ── 부트스트랩 ─────────────────────────────────────────────────────────────

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
