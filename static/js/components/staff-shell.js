/**
 * 좁은 화면의 가로 스크롤 탭 목록에서 현재 활성 탭이 화면 밖에 가려지지
 * 않도록 로드 시 즉시 스크롤해 보여준다. 애니메이션 없이 바로 이동한다.
 */
(function () {
  "use strict";

  function revealActiveTab() {
    var active = document.querySelector(".staff-shell-tabs .active");
    if (!active) { return; }
    active.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "auto" });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", revealActiveTab);
  } else {
    revealActiveTab();
  }
})();
