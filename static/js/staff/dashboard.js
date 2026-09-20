/**
 * 스태프 대시보드의 "최근 탐색 실행" 표 — 행사별 결과 상세 토글.
 * discovery_live.js가 표 tbody를 통째로 교체하므로, 버튼마다 개별
 * 바인딩하는 대신 tbody에 위임 리스너 1개만 둔다.
 */

(function () {
  "use strict";

  function toggleOutcomeRow(btn) {
    var row = document.getElementById(btn.getAttribute("aria-controls"));
    if (!row) {
      return;
    }
    var isExpanded = btn.getAttribute("data-expanded") === "true";
    var expand = !isExpanded;

    row.hidden = !expand;
    btn.setAttribute("data-expanded", String(expand));
    btn.setAttribute("aria-expanded", String(expand));
  }

  function bindOutcomeToggleDelegation() {
    var tbody = document.getElementById("dash-runs-body");
    if (!tbody) {
      return;
    }
    tbody.addEventListener("click", function (event) {
      var btn = event.target.closest(".dash-outcome-toggle");
      if (!btn) {
        return;
      }
      toggleOutcomeRow(btn);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindOutcomeToggleDelegation();
  });
})();
