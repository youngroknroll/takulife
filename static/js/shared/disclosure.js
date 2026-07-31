/**
 * 범용 접기/펼치기 토글. [data-disclosure] 컨테이너의 data-expanded
 * 속성값(true/false)을 CSS가 그대로 읽어 보이기·숨기기를 결정한다.
 * [data-disclosure-toggle] 버튼을 누르면 조상 컨테이너의 값이 뒤집힌다.
 * 한 페이지에 여러 개를 독립적으로 둘 수 있다.
 */
(function () {
  "use strict";

  function initDisclosures() {
    var toggles = document.querySelectorAll("[data-disclosure-toggle]");
    for (var i = 0; i < toggles.length; i++) {
      toggles[i].addEventListener("click", handleToggleClick);
    }
  }

  function handleToggleClick(event) {
    var container = event.currentTarget.closest("[data-disclosure]");
    if (!container) { return; }
    var expanded = container.getAttribute("data-expanded") === "true";
    var nextExpanded = expanded ? "false" : "true";
    container.setAttribute("data-expanded", nextExpanded);
    event.currentTarget.setAttribute("aria-expanded", nextExpanded);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDisclosures);
  } else {
    initDisclosures();
  }
})();
