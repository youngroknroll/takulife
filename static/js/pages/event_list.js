const filterToggle = document.querySelector(".filter-toggle");
const filterPanel = document.querySelector(".filters");
if (filterToggle && filterPanel) {
  filterToggle.addEventListener("click", () => {
    const open = filterPanel.classList.toggle("open");
    filterToggle.setAttribute("aria-expanded", String(open));
    filterToggle.textContent = open ? "필터 닫기 ▴" : "필터 열기 ▾";
  });
}
