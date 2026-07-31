const filterToggle = document.querySelector(".filter-toggle");
const filterPanel = document.querySelector(".filters");
if (filterToggle && filterPanel) {
  filterToggle.addEventListener("click", () => {
    const open = filterPanel.classList.toggle("open");
    filterToggle.setAttribute("data-expanded", String(open));
    filterToggle.setAttribute("aria-expanded", String(open));
    filterToggle.textContent = open ? "필터 닫기 ▴" : "필터 열기 ▾";
  });
}

// 정렬 메뉴는 <details> 요소라 열고 닫기, 키보드 조작, JS 없이도 동작하는 것까지
// 브라우저가 기본 제공한다. 여기서는 포커스가 다른 곳으로 이동했을 때 닫는
// 동작만 추가한다.
const sortMenu = document.querySelector("[data-sort-menu]");
if (sortMenu) {
  const closeSortMenu = () => sortMenu.removeAttribute("open");

  document.addEventListener("click", (event) => {
    if (sortMenu.hasAttribute("open") && !sortMenu.contains(event.target)) {
      closeSortMenu();
    }
  });
  sortMenu.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && sortMenu.hasAttribute("open")) {
      closeSortMenu();
      // 이 처리가 없으면 키보드 사용자의 포커스가 사라진 요소에 남아 body로 밀려난다.
      sortMenu.querySelector("summary").focus();
    }
  });
  // Tab으로 마지막 항목을 지나 포커스가 패널을 완전히 벗어나도 닫는다.
  sortMenu.addEventListener("focusout", (event) => {
    if (!sortMenu.contains(event.relatedTarget)) {
      closeSortMenu();
    }
  });
}
