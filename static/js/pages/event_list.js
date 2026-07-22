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

// Sort menu (results head): a native <details>, so open/close, keyboard
// operation, and the no-JS fallback all come from the element itself. The only
// thing <details> lacks for a dropdown is dismissal when attention moves
// elsewhere — that is all this block adds.
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
      // Return focus to the control that opened the panel; without this the
      // keyboard user is left on a removed subtree and falls back to <body>.
      sortMenu.querySelector("summary").focus();
    }
  });
  // Focus leaving the panel entirely (Tab past the last option) closes it too.
  sortMenu.addEventListener("focusout", (event) => {
    if (!sortMenu.contains(event.relatedTarget)) {
      closeSortMenu();
    }
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
    toggle.setAttribute("data-expanded", String(open));
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
