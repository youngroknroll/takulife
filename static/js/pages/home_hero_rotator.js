/**
 * 홈 히어로 대표 행사 타이포 로테이터. 슬라이드 2건 이상일 때만 로드되며
 * 7초마다 자동 전환하고, 도트·정지 버튼을 JS가 직접 만들어 붙인다.
 * mouseenter/focusin/터치/도트 클릭으로 멈추고 mouseleave/focusout/토글로
 * 재개한다(도트 클릭은 영구 정지 — 토글로만 재개). reduced-motion에서는
 * 자동 전환과 토글 버튼 자체를 없앤다.
 */

(function () {
  "use strict";

  var AUTOPLAY_INTERVAL = 7000;

  var reducedMotionMql = window.matchMedia("(prefers-reduced-motion: reduce)");

  // ── 로테이터 하나 생성 ───────────────────────────────────────────────

  function createRotator(rotator) {
    var wrap = rotator.closest(".hero-rotator-wrap");
    if (!wrap) {
      return;
    }

    var slides = Array.prototype.slice.call(
      rotator.querySelectorAll("[data-hero-slide]")
    );
    if (slides.length < 2) {
      return;
    }

    var activeIndex = 0;
    for (var s = 0; s < slides.length; s++) {
      if (slides[s].classList.contains("is-active")) {
        activeIndex = s;
        break;
      }
    }

    // visibility 지연(350ms) 동안 나가는 슬라이드가 여전히 tabbable해
    // 활성·비활성 슬라이드가 동시에 포커스 가능한 창이 생긴다 — inert로
    // 탭 순서 제외를 시각 페이드와 분리해 그 창을 없앤다.
    slides.forEach(function (slide, index) {
      if (index !== activeIndex) {
        slide.setAttribute("inert", "");
      }
    });

    var hovered = false;
    var focused = false;
    // 터치가 감지되면 이후 mouseleave/focusout 재개를 막는다 — iOS는 탭 후
    // 가짜 mouseleave/blur를 보내 의도치 않게 자동재생을 되살릴 수 있다.
    // 터치 기기의 재개는 토글 버튼으로만 한다.
    var touched = false;
    // 도트 클릭 또는 토글로 정지한 상태 — hover/focus 재개로는 풀리지 않는다.
    var manuallyStopped = false;
    var timer = null;
    var toggleAttached = false;

    // ── 컨트롤 DOM 생성 ─────────────────────────────────────────────

    var controls = document.createElement("div");
    controls.className = "hero-rotator-controls";

    var dotsGroup = document.createElement("div");
    dotsGroup.className = "hero-rotator-dots";
    dotsGroup.setAttribute("role", "group");
    dotsGroup.setAttribute("aria-label", "대표 행사 선택");
    controls.appendChild(dotsGroup);

    var dots = slides.map(function (slide, index) {
      var dot = document.createElement("button");
      dot.type = "button";
      dot.className = "hero-rotator-dot";
      dotsGroup.appendChild(dot);
      dot.addEventListener("click", function () {
        goToSlide(index);
        manuallyStopped = true;
        stopAutoplay();
        updateToggleState();
      });
      return dot;
    });

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "hero-rotator-toggle";
    toggle.addEventListener("click", function () {
      manuallyStopped = !manuallyStopped;
      if (manuallyStopped) {
        stopAutoplay();
      } else {
        // 명시적 재개 클릭은 터치 가드보다 우선한다.
        touched = false;
        startAutoplay();
      }
      updateToggleState();
    });

    wrap.appendChild(controls);

    // ── 도트/토글 상태 표시 ─────────────────────────────────────────

    function updateDotState(index, active) {
      var dot = dots[index];
      if (active) {
        dot.setAttribute("aria-current", "true");
        // aria-current 단독은 Chromium AX 트리에 노출되지 않아 가시 텍스트
        // 없는 버튼이라도 aria-label에 상태 문구를 함께 넣는다.
        dot.setAttribute("aria-label", (index + 1) + "번째 대표 행사 (현재 표시 중)");
      } else {
        dot.removeAttribute("aria-current");
        dot.setAttribute("aria-label", (index + 1) + "번째 대표 행사 보기");
      }
    }

    dots.forEach(function (dot, index) {
      updateDotState(index, index === activeIndex);
    });

    function updateToggleState() {
      toggle.setAttribute("aria-pressed", manuallyStopped ? "true" : "false");
      toggle.setAttribute(
        "aria-label",
        manuallyStopped ? "자동 재생 재개" : "자동 재생 정지"
      );
    }

    // ── 슬라이드 전환 ───────────────────────────────────────────────

    function goToSlide(index) {
      if (index === activeIndex) {
        return;
      }
      slides[activeIndex].classList.remove("is-active");
      // is-active 전환과 같은 틱에서 즉시 inert를 걸어, opacity가 0으로
      // 수렴하는 350ms 동안 나가는 슬라이드가 계속 tabbable로 남지 않게 한다.
      slides[activeIndex].setAttribute("inert", "");
      updateDotState(activeIndex, false);
      activeIndex = index;
      slides[activeIndex].classList.add("is-active");
      slides[activeIndex].removeAttribute("inert");
      updateDotState(activeIndex, true);
    }

    // ── 자동재생 ────────────────────────────────────────────────────

    function shouldAutoplay() {
      return (
        !reducedMotionMql.matches &&
        !hovered &&
        !focused &&
        !touched &&
        !manuallyStopped
      );
    }

    function stopAutoplay() {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    }

    function startAutoplay() {
      stopAutoplay();
      if (!shouldAutoplay()) {
        return;
      }
      timer = setInterval(function () {
        if (!shouldAutoplay()) {
          stopAutoplay();
          return;
        }
        goToSlide((activeIndex + 1) % slides.length);
      }, AUTOPLAY_INTERVAL);
    }

    // ── 정지/재개 트리거 ─────────────────────────────────────────────

    wrap.addEventListener("mouseenter", function () {
      hovered = true;
      stopAutoplay(); // 동기적으로 즉시 멈춘다
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
    wrap.addEventListener(
      "touchstart",
      function () {
        touched = true;
        stopAutoplay();
      },
      { passive: true }
    );

    // ── reduced-motion 실행 중 반영 ───────────────────────────────────

    function attachToggle() {
      if (!toggleAttached) {
        controls.appendChild(toggle);
        toggleAttached = true;
      }
    }

    function detachToggle() {
      if (toggleAttached) {
        toggle.remove();
        toggleAttached = false;
      }
    }

    function syncReducedMotion() {
      if (reducedMotionMql.matches) {
        detachToggle();
        stopAutoplay();
      } else {
        updateToggleState();
        attachToggle();
        if (!manuallyStopped) {
          startAutoplay();
        }
      }
    }

    reducedMotionMql.addEventListener("change", syncReducedMotion);

    // bfcache 복원 시 정지 상태와 reduced-motion 설정을 다시 평가한다.
    window.addEventListener("pageshow", function (evt) {
      if (!evt.persisted) {
        return;
      }
      hovered = false;
      focused = false;
      syncReducedMotion();
    });

    syncReducedMotion();
  }

  // ── 부트스트랩 ───────────────────────────────────────────────────────

  function init() {
    var wraps = document.querySelectorAll("[data-hero-rotator]");
    for (var i = 0; i < wraps.length; i++) {
      createRotator(wraps[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
