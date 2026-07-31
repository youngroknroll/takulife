/**
 * 원래 위치의 CTA가 화면 밖으로 스크롤됐을 때만 하단 고정 CTA 바를 보여준다.
 * 모바일에서 같은 행동 유도 버튼이 화면에 두 번 겹쳐 보이지 않게 하기 위해서다.
 * [data-cta-fixed]는 마크업에 hidden 속성으로 시작해 이 스크립트가 판단하기
 * 전에 잠깐 나타났다 사라지는 깜빡임이 없다.
 * IntersectionObserver를 지원하지 않는 브라우저는 항상 고정 바를 보여준다.
 */
(function () {
  "use strict";

  function initCtaVisibility() {
    var watchTarget = document.querySelector("[data-cta-watch]");
    var fixedBar = document.querySelector("[data-cta-fixed]");

    if (!watchTarget || !fixedBar) { return; }

    if (typeof window.IntersectionObserver !== "function") {
      fixedBar.hidden = false;
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      var entry = entries[0];
      fixedBar.hidden = entry.isIntersecting;
    });
    observer.observe(watchTarget);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCtaVisibility);
  } else {
    initCtaVisibility();
  }
})();
