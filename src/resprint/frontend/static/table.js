const collator = new Intl.Collator("fr", { numeric: true, sensitivity: "base" });

document.querySelectorAll("[data-enhanced-table]").forEach((section) => {
  const input = section.querySelector("[data-table-search]");
  const filters = Array.from(section.querySelectorAll("[data-table-filter]"));
  const table = section.querySelector("table");
  const tbody = section.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));
  const count = section.querySelector("[data-row-count]");
  const noResults = section.querySelector("[data-no-results]");

  function updateCount() {
    const visibleRows = rows.filter((row) => !row.hidden).length;
    if (count) {
      count.textContent = `${visibleRows} / ${rows.length}`;
    }
    noResults.style.display = visibleRows === 0 ? "block" : "none";
  }

  function applyTableFilters() {
    const query = input ? input.value.trim().toLocaleLowerCase("fr") : "";
    rows.forEach((row) => {
      const matchesSearch = !query || row.dataset.search.includes(query);
      const matchesFilters = filters.every((filter) => {
        if (!filter.value) {
          return true;
        }
        const cell = row.cells[Number(filter.dataset.filterColumn)];
        return cell.textContent.trim().toLocaleLowerCase("fr") === filter.value;
      });
      row.hidden = !(matchesSearch && matchesFilters);
    });
    updateCount();
  }

  if (input) {
    input.addEventListener("input", applyTableFilters);
  }

  if (filters.length) {
    filters.forEach((filter) => {
      filter.addEventListener("change", applyTableFilters);
    });
  }

  function applySort(button, forcedDirection) {
    const column = Number(button.dataset.sortColumn);
    const type = button.dataset.sortType || "text";
    const current = button.dataset.sortDirection || "none";
    const direction = forcedDirection || (current === "asc" ? "desc" : "asc");

    section.querySelectorAll("[data-sort-column]").forEach((other) => {
      other.dataset.sortDirection = "none";
      other.querySelector(".sort-indicator").className = "sort-indicator";
      other.closest("th").setAttribute("aria-sort", "none");
    });

    button.dataset.sortDirection = direction;
    button.querySelector(".sort-indicator").className =
      direction === "asc"
        ? "sort-indicator mdi mdi-arrow-up"
        : "sort-indicator mdi mdi-arrow-down";
    button.closest("th").setAttribute(
      "aria-sort",
      direction === "asc" ? "ascending" : "descending",
    );

    rows
      .sort((left, right) => {
        const leftValue = sortValue(left, column, type);
        const rightValue = sortValue(right, column, type);
        const comparison = type === "number"
          ? leftValue - rightValue
          : collator.compare(leftValue, rightValue);
        return direction === "asc" ? comparison : -comparison;
      })
      .forEach((row) => tbody.appendChild(row));
  }

  section.querySelectorAll("[data-sort-column]").forEach((button) => {
    button.addEventListener("click", () => {
      applySort(button);
    });
  });

  if (table.dataset.defaultSortColumn) {
    const defaultButton = section.querySelector(
      `[data-sort-column="${table.dataset.defaultSortColumn}"]`,
    );
    if (defaultButton) {
      applySort(defaultButton, table.dataset.defaultSortDirection || "asc");
    }
  }

  applyTableFilters();
});

function sortValue(row, column, type) {
  const cell = row.cells[column];
  const value = cell.dataset.sortValue || cell.textContent.trim();
  return type === "number" ? Number(value || 0) : value;
}
