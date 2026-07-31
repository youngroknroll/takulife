/**
 * 모바일 햄버거 메뉴 토글. 넓은 화면에서는 CSS가 메뉴를 항상 보여주므로
 * 이 토글은 아무 동작도 하지 않는다.
 * 계정 드롭다운(account_menu.js)과 달리 바깥 클릭으로는 닫히지 않는다 —
 * 펼쳐진 메뉴는 떠 있는 오버레이가 아니라 헤더를 늘리는 블록이라 "바깥"이라는
 * 개념이 없고, Escape나 토글 재클릭·페이지 이동으로만 닫힌다.
 */
(function () {
  "use strict";

  function initNavMenu() {
    var toggle = document.querySelector("[data-nav-menu-toggle]");
    var nav = document.getElementById("primary-nav");
    if (!toggle || !nav) {
      return;
    }

    function setOpen(open) {
      nav.setAttribute("data-expanded", String(open));
      toggle.setAttribute("data-expanded", String(open));
      toggle.setAttribute("aria-expanded", String(open));
    }

    toggle.addEventListener("click", function () {
      setOpen(nav.getAttribute("data-expanded") !== "true");
    });

    // 열린 직후 포커스가 메뉴 밖의 토글 버튼에 있어 document 전체에 리스너를 건다.
    // 열림 상태와 포커스 위치를 함께 확인해, 계정 드롭다운 등 다른 위젯을 향한
    // Escape가 이 메뉴까지 닫아버리고 포커스를 가로채지 않도록 막는다.
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || nav.getAttribute("data-expanded") !== "true") {
        return;
      }
      if (!nav.contains(document.activeElement) && document.activeElement !== toggle) {
        return;
      }
      setOpen(false);
      toggle.focus();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initNavMenu);
  } else {
    initNavMenu();
  }
})();
