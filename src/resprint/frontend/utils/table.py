from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Literal

from resprint.frontend.utils.page import static_text
from resprint.frontend.utils.templates import render_template

TableRowStyle = Literal["success", "warning", "error", "info"]


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
    style: TableRowStyle | None = None


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

    return render_template(
        "table_section.html",
        attributes=attributes,
        title=title,
        row_count=len(rows),
        search_tools=search_tools,
        table_attributes=table_attributes,
        headers=headers,
        body_rows=body_rows,
        empty_id=f"{section_id}-empty",
        empty_message=empty_message,
    )


def table_css() -> str:
    return static_text("table.css")


def table_script() -> str:
    return static_text("table.js")


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
    attributes = _render_attributes(
        {
            "class": f"table-row-{row.style}" if row.style else None,
            "data-search": row.search_text.casefold(),
        }
    )
    return f"""<tr{attributes}>
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
