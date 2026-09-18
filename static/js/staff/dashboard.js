/**
 * 스태프 대시보드의 "최근 탐색 실행" 표 — 행사별 결과 상세 토글.
 * hidden 속성만 바꿀 뿐 서버가 이미 렌더한 목록 내용을 직접 읽거나
 * 쓰지 않는다.
 */

(function () {
  "use strict";

  function bindOutcomeToggles() {
    var buttons = document.querySelectorAll(".dash-outcome-toggle");
    buttons.forEach(function (btn) {
      var row = document.getElementById(btn.getAttribute("aria-controls"));
      if (!row) {
        return;
      }

      btn.addEventListener("click", function () {
        var isExpanded = btn.getAttribute("data-expanded") === "true";
        var expand = !isExpanded;

        row.hidden = !expand;
        btn.setAttribute("data-expanded", String(expand));
        btn.setAttribute("aria-expanded", String(expand));
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindOutcomeToggles();
  });
})();
