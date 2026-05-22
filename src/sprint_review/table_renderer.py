from __future__ import annotations

import html
from dataclasses import dataclass


@dataclass(frozen=True)
class TableColumn:
    key: str
    label: str
    numeric: bool = False
    sortable: bool = True
    sort_type: str = "text"


@dataclass(frozen=True)
class TableCell:
    html: str
    sort_value: str | int | None = None
    class_name: str | None = None


@dataclass(frozen=True)
class TableRow:
    cells: dict[str, TableCell]
    search_text: str = ""


@dataclass(frozen=True)
class DefaultSort:
    column_key: str
    direction: str = "asc"


def render_table_section(
    *,
    section_id: str,
    title: str,
    columns: list[TableColumn],
    rows: list[TableRow],
    searchable: bool = True,
    sortable: bool = True,
    default_sort: DefaultSort | None = None,
    empty_message: str = "Aucun resultat.",
    section_attributes: dict[str, str | None] | None = None,
) -> str:
    attributes = _render_attributes(
        {
            "id": section_id,
            "data-enhanced-table": "",
            **(section_attributes or {}),
        }
    )
    search_tools = _render_search_tools(title) if searchable else ""
    headers = "\n".join(
        _render_header(column, index, sortable=sortable, default_sort=default_sort)
        for index, column in enumerate(columns)
    )
    body_rows = "\n".join(_render_row(row, columns) for row in rows)
    table_attributes = _render_attributes(
        {
            "aria-describedby": f"{section_id}-empty",
            "data-default-sort-column": _default_sort_index(columns, default_sort),
            "data-default-sort-direction": default_sort.direction
            if default_sort
            else None,
        }
    )

    return f"""<section{attributes}>
  <div class="section-header">
    <h2>{_html(title)} <span class="muted">({len(rows)})</span></h2>
    {search_tools}
  </div>
  <div class="table-wrap">
    <table{table_attributes}>
      <thead>
        <tr>
          {headers}
        </tr>
      </thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
    <div class="no-results" id="{_html_attr(section_id)}-empty" data-no-results>
      {_html(empty_message)}
    </div>
  </div>
</section>"""


def table_css() -> str:
    return """
    .section-header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }
    .section-tools {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .search { width: 100%; }
    .table-wrap {
      overflow-x: auto;
      border: 1px solid var(--border);
      background: var(--surface);
    }
    table { width: 100%; border-collapse: collapse; min-width: 1180px; }
    th {
      text-align: left;
      white-space: nowrap;
    }
    th[data-sortable] { padding: 0; }
    .sort-button {
      width: 100%;
      border: 0;
      background: transparent;
      color: inherit;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 10px 12px;
      font: inherit;
      font-weight: 650;
      text-align: left;
      white-space: nowrap;
    }
    th.numeric .sort-button { justify-content: flex-end; }
    .sort-indicator {
      color: var(--muted);
      font-size: 16px;
      line-height: 1;
      min-width: 16px;
    }
    .sort-button:hover
      .sort-indicator:not(.mdi-arrow-up):not(.mdi-arrow-down) {
      opacity: 0.45;
    }
    .sort-button:hover
      .sort-indicator:not(.mdi-arrow-up):not(.mdi-arrow-down)::before {
      content: "\\F005D";
      display: inline-block;
      font: normal normal normal 24px/1 "Material Design Icons";
      font-size: 16px;
      text-rendering: auto;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }
    td.numeric, th.numeric { text-align: right; white-space: nowrap; }
    .no-results { padding: 14px 16px; }
    @media (max-width: 760px) {
      .section-header { display: grid; align-items: start; }
      .section-tools { width: 100%; }
    }
"""


def table_script() -> str:
    return """
    const collator = new Intl.Collator("fr", { numeric: true, sensitivity: "base" });

    document.querySelectorAll("[data-enhanced-table]").forEach((section) => {
      const input = section.querySelector("[data-table-search]");
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

      if (input) {
        input.addEventListener("input", () => {
          const query = input.value.trim().toLocaleLowerCase("fr");
          rows.forEach((row) => {
            row.hidden = query && !row.dataset.search.includes(query);
          });
          updateCount();
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

      updateCount();
    });

    function sortValue(row, column, type) {
      const cell = row.cells[column];
      const value = cell.dataset.sortValue || cell.textContent.trim();
      return type === "number" ? Number(value || 0) : value;
    }
"""


def _render_search_tools(title: str) -> str:
    return f"""<div class="section-tools">
      <div class="search-wrap">
        <span class="mdi mdi-magnify" aria-hidden="true"></span>
        <input
          class="search"
          type="search"
          aria-label="Rechercher dans {_html_attr(title)}"
          placeholder="Rechercher..."
          data-table-search
        >
      </div>
      <span class="row-count" data-row-count></span>
    </div>"""


def _render_header(
    column: TableColumn,
    index: int,
    *,
    sortable: bool,
    default_sort: DefaultSort | None,
) -> str:
    class_name = ' class="numeric"' if column.numeric else ""
    if not sortable or not column.sortable:
        return f"<th{class_name}>{_html(column.label)}</th>"

    direction = _default_direction(column, default_sort)
    indicator_class = "sort-indicator"
    aria_sort = "none"
    if direction == "asc":
        indicator_class = "sort-indicator mdi mdi-arrow-up"
        aria_sort = "ascending"
    elif direction == "desc":
        indicator_class = "sort-indicator mdi mdi-arrow-down"
        aria_sort = "descending"

    return f"""<th{class_name} data-sortable aria-sort="{aria_sort}">
  <button
    class="sort-button"
    type="button"
    data-sort-column="{index}"
    data-sort-type="{_html_attr(column.sort_type)}"
    data-sort-direction="{_html_attr(direction or "none")}"
  >
    <span>{_html(column.label)}</span>
    <span class="{indicator_class}" aria-hidden="true"></span>
  </button>
</th>"""


def _render_row(row: TableRow, columns: list[TableColumn]) -> str:
    cells = "\n".join(_render_cell(row.cells[column.key], column) for column in columns)
    return f"""<tr data-search="{_html_attr(row.search_text.casefold())}">
  {cells}
</tr>"""


def _render_cell(cell: TableCell, column: TableColumn) -> str:
    class_names = [
        name
        for name in (cell.class_name, "numeric" if column.numeric else None)
        if name
    ]
    attributes = _render_attributes(
        {
            "class": " ".join(class_names) or None,
            "data-sort-value": cell.sort_value,
        }
    )
    return f"<td{attributes}>{cell.html}</td>"


def _render_attributes(attributes: dict[str, object | None]) -> str:
    rendered = []
    for name, value in attributes.items():
        if value is None:
            continue
        if value == "":
            rendered.append(_html_attr(name))
        else:
            rendered.append(f'{_html_attr(name)}="{_html_attr(value)}"')
    return f" {' '.join(rendered)}" if rendered else ""


def _default_sort_index(
    columns: list[TableColumn],
    default_sort: DefaultSort | None,
) -> int | None:
    if default_sort is None:
        return None
    for index, column in enumerate(columns):
        if column.key == default_sort.column_key:
            return index
    return None


def _default_direction(
    column: TableColumn,
    default_sort: DefaultSort | None,
) -> str | None:
    if default_sort is None or column.key != default_sort.column_key:
        return None
    return default_sort.direction


def _html(value: object) -> str:
    return html.escape(str(value), quote=False)


def _html_attr(value: object) -> str:
    return html.escape(str(value), quote=True)
