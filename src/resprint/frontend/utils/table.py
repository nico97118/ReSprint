from __future__ import annotations

import html
from dataclasses import dataclass
from html.parser import HTMLParser
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
    details_html: str | None = None


@dataclass(frozen=True)
class DefaultSort:
    column_key: str
    direction: str = "asc"


@dataclass(frozen=True)
class TableFilter:
    column_key: str
    label: str
    placeholder: str | None = None


@dataclass(frozen=True)
class FilterOption:
    value: str
    label: str


@dataclass(frozen=True)
class RenderedFilter:
    label: str
    placeholder: str
    column_index: int
    options: tuple[FilterOption, ...]


def render_table_section(
    *,
    section_id: str,
    title: str,
    columns: list[TableColumn],
    rows: list[TableRow],
    searchable: bool = True,
    sortable: bool = True,
    default_sort: DefaultSort | None = None,
    filters: list[TableFilter] | None = None,
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
    has_expandable_rows = any(row.details_html for row in rows)
    column_offset = 1 if has_expandable_rows else 0
    rendered_filters = _rendered_filters(columns, rows, filters or [], column_offset)
    search_tools = _render_search_tools(title, include_count=True) if searchable else ""
    filter_tools = _render_filter_tools(rendered_filters)
    headers = "\n".join(
        _render_header(
            column,
            index + column_offset,
            sortable=sortable,
            default_sort=default_sort,
        )
        for index, column in enumerate(columns)
    )
    if has_expandable_rows:
        headers = f'<th class="row-expander-header">Details</th>\n{headers}'
    body_rows = "\n".join(
        _render_row(
            row,
            columns,
            expandable=has_expandable_rows,
            row_index=index,
            section_id=section_id,
        )
        for index, row in enumerate(rows)
    )
    table_attributes = _render_attributes(
        {
            "aria-describedby": f"{section_id}-empty",
            "data-default-sort-column": _default_sort_index(
                columns, default_sort, column_offset
            ),
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
        filter_tools=filter_tools,
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


def _render_search_tools(title: str, *, include_count: bool = False) -> str:
    count = '<span class="row-count" data-row-count></span>' if include_count else ""
    return f"""<div class="search-wrap">
      <span class="mdi mdi-magnify" aria-hidden="true"></span>
      <input
        class="search"
        type="search"
        aria-label="Rechercher dans {_html_attr(title)}"
        placeholder="Rechercher..."
        data-table-search
      >
      {count}
    </div>"""


def _render_filter_tools(
    filters: tuple[RenderedFilter, ...],
) -> str:
    if not filters:
        return ""
    tools = [_render_filter(filter_) for filter_ in filters]
    return f"""<div class="section-tools">
      {"".join(tools)}
    </div>"""


def _render_filter(filter_: RenderedFilter) -> str:
    options = "\n".join(
        f'<option value="{_html_attr(option.value)}">{_html(option.label)}</option>'
        for option in filter_.options
    )
    return f"""<label class="table-filter">
      <span>{_html(filter_.label)}</span>
      <select data-table-filter data-filter-column="{filter_.column_index}">
        <option value="">{_html(filter_.placeholder)}</option>
        {options}
      </select>
    </label>"""


def _rendered_filters(
    columns: list[TableColumn],
    rows: list[TableRow],
    filters: list[TableFilter],
    column_offset: int = 0,
) -> tuple[RenderedFilter, ...]:
    rendered = []
    for filter_ in filters:
        column_index = _column_index(columns, filter_.column_key)
        if column_index is None:
            continue
        options_by_value: dict[str, str] = {}
        for row in rows:
            cell = row.cells.get(filter_.column_key)
            if cell is None:
                continue
            label = _plain_text(cell.html).strip()
            if not label or label == "-":
                continue
            value = label.casefold()
            options_by_value.setdefault(value, label)
        options = tuple(
            FilterOption(value=value, label=label)
            for value, label in sorted(
                options_by_value.items(),
                key=lambda item: item[1].casefold(),
            )
        )
        if not options:
            continue
        rendered.append(
            RenderedFilter(
                label=filter_.label,
                placeholder=filter_.placeholder or "Tous",
                column_index=column_index + column_offset,
                options=options,
            )
        )
    return tuple(rendered)


def _column_index(columns: list[TableColumn], column_key: str) -> int | None:
    for index, column in enumerate(columns):
        if column.key == column_key:
            return index
    return None


def _plain_text(value: str) -> str:
    class PlainTextParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.fragments: list[str] = []

        def handle_data(self, data: str) -> None:
            self.fragments.append(data)

    parser = PlainTextParser()
    parser.feed(value)
    return " ".join("".join(parser.fragments).split())


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


def _render_row(
    row: TableRow,
    columns: list[TableColumn],
    *,
    expandable: bool,
    row_index: int,
    section_id: str,
) -> str:
    cells = "\n".join(_render_cell(row.cells[column.key], column) for column in columns)
    detail_row_id = f"{section_id}-detail-{row_index}"
    if expandable:
        cells = f"{_render_expander_cell(row, detail_row_id)}\n{cells}"
    attributes = _render_attributes(
        {
            "class": f"table-row-{row.style}" if row.style else None,
            "data-table-row": "",
            "data-search": row.search_text.casefold(),
            "data-detail-row-id": detail_row_id if row.details_html else None,
        }
    )
    rendered_row = f"""<tr{attributes}>
  {cells}
</tr>"""
    if not row.details_html:
        return rendered_row

    detail_attributes = _render_attributes(
        {
            "id": detail_row_id,
            "class": "table-detail-row",
            "data-table-detail-row": "",
            "hidden": "",
        }
    )
    colspan = len(columns) + (1 if expandable else 0)
    return f"""{rendered_row}
<tr{detail_attributes}>
  <td colspan="{colspan}">
    <div class="table-detail-content">{row.details_html}</div>
  </td>
</tr>"""


def _render_expander_cell(row: TableRow, detail_row_id: str) -> str:
    if not row.details_html:
        return '<td class="row-expander-cell"></td>'

    return f"""<td class="row-expander-cell">
  <button
    class="row-expander-button"
    type="button"
    aria-label="Afficher les details"
    aria-expanded="false"
    aria-controls="{_html_attr(detail_row_id)}"
    data-row-toggle
  >
    <span class="mdi mdi-chevron-down" aria-hidden="true"></span>
  </button>
</td>"""


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
    column_offset: int = 0,
) -> int | None:
    if default_sort is None:
        return None
    for index, column in enumerate(columns):
        if column.key == default_sort.column_key:
            return index + column_offset
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
