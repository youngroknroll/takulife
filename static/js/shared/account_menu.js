/**
 * 헤더의 계정 드롭다운. 바깥을 클릭하거나 Escape를 누르면 닫히고,
 * Escape로 닫으면 포커스가 다시 토글 버튼으로 돌아간다. 항목이 전부
 * 페이지 이동(또는 로그아웃 POST)이라 열림 상태에서 포커스를 강제로
 * 가두거나 옮길 필요는 없다.
 * 모든 페이지에서 로드되지만(base.html), 비로그인 방문자는
 * _topbar.html이 [data-account-menu] 자체를 렌더링하지 않아 아무 동작도 하지 않는다.
 */
(function () {
  "use strict";

  function initAccountMenu() {
    var accountMenu = document.querySelector("[data-account-menu]");
    if (!accountMenu) {
      return;
    }

    var toggle = accountMenu.querySelector("[data-account-menu-toggle]");
    var panel = accountMenu.querySelector("[data-account-menu-panel]");

    function setOpen(open) {
      panel.hidden = !open;
      toggle.setAttribute("data-expanded", String(open));
      toggle.setAttribute("aria-expanded", String(open));
    }

    toggle.addEventListener("click", function () {
      setOpen(panel.hidden);
    });

    document.addEventListener("click", function (event) {
      if (!accountMenu.contains(event.target)) {
        setOpen(false);
      }
    });

    accountMenu.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !panel.hidden) {
        setOpen(false);
        toggle.focus();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAccountMenu);
  } else {
    initAccountMenu();
  }
})();
