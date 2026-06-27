const filterToggle = document.querySelector(".filter-toggle");
const filterPanel = document.querySelector(".filters");
if (filterToggle && filterPanel) {
  filterToggle.addEventListener("click", () => {
    const open = filterPanel.classList.toggle("open");
    filterToggle.setAttribute("aria-expanded", String(open));
    filterToggle.textContent = open ? "필터 닫기 ▴" : "필터 열기 ▾";
  });
}

// Region filter: collapse the geographic regions into a multi-select dropdown so
// the sidebar stays compact as regions grow. "온라인" lives outside this menu.
const regionSelect = document.querySelector("[data-region-select]");
if (regionSelect) {
  const toggle = regionSelect.querySelector("[data-region-toggle]");
  const menu = regionSelect.querySelector("[data-region-menu]");
  const summary = regionSelect.querySelector("[data-region-summary]");

  const renderSummary = () => {
    const checked = [...menu.querySelectorAll('input[type="checkbox"]:checked')];
    if (checked.length === 0) {
      summary.textContent = "지역 전체";
      return;
    }
    const first = checked[0].closest("label").textContent.trim();
    summary.textContent =
      checked.length === 1 ? first : `${first} 외 ${checked.length - 1}`;
  };

  const setOpen = (open) => {
    menu.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
  };

  toggle.addEventListener("click", () => setOpen(menu.hidden));
  menu.addEventListener("change", renderSummary);
  document.addEventListener("click", (event) => {
    if (!regionSelect.contains(event.target)) {
      setOpen(false);
    }
  });
  regionSelect.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !menu.hidden) {
      setOpen(false);
      toggle.focus();
    }
  });

  renderSummary();
}
