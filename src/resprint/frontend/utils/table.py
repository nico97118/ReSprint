from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal

from resprint.frontend.i18n import t
from resprint.frontend.utils.html import html_attr, html_text
from resprint.frontend.utils.page import asset_url
from resprint.frontend.utils.templates import render_template

TableRowStyle = Literal["success", "warning", "error", "info"]


@dataclass(frozen=True)
class TableColumn:
    key: str
    label: str
    short_label: str | None = None
    hidden: bool = False
    numeric: bool = False
    totalable: bool = False
    sortable: bool = True
    sort_type: str = "text"


@dataclass(frozen=True)
class TableCell:
    # Safe HTML ready for insertion. Prefer text_cell/link_cell/badge_cell helpers.
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
    empty_message: str = "",
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
        headers = (
            f'<th class="row-expander-header" aria-label="{t("table.details")}"></th>\n'
            + headers
        )
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
        "components/table/section.html",
        attributes=attributes,
        title=title,
        row_count=len(rows),
        search_tools=search_tools,
        filter_tools=filter_tools,
        table_attributes=table_attributes,
        headers=headers,
        body_rows=body_rows,
        empty_id=f"{section_id}-empty",
        empty_message=empty_message or t("table.no_results"),
    )


def table_css() -> str:
    return asset_url("min/table.min.css")


def table_script() -> str:
    return asset_url("min/table.min.js")


def text_cell(
    value: object,
    *,
    sort_value: str | int | None = None,
    class_name: str | None = None,
) -> TableCell:
    return TableCell(html_text(value), sort_value=sort_value, class_name=class_name)


def html_cell(
    value: str,
    *,
    sort_value: str | int | None = None,
    class_name: str | None = None,
) -> TableCell:
    return TableCell(value, sort_value=sort_value, class_name=class_name)


def link_cell(
    label: object,
    href: object,
    *,
    sort_value: str | int | None = None,
    class_name: str | None = None,
) -> TableCell:
    return html_cell(
        f'<a href="{html_attr(href)}">{html_text(label)}</a>',
        sort_value=sort_value,
        class_name=class_name,
    )


def badge_cell(
    label: object,
    variant: str | None = None,
    *,
    sort_value: str | int | None = None,
    class_name: str | None = None,
) -> TableCell:
    classes = ["badge"]
    if variant:
        classes.append(f"badge-{variant}")
    if class_name:
        classes.append(class_name)
    return html_cell(
        f'<span class="{html_attr(" ".join(classes))}">{html_text(label)}</span>',
        sort_value=sort_value,
    )


def _render_search_tools(title: str, *, include_count: bool = False) -> str:
    return render_template(
        "components/table/search_tools.html",
        title=title,
        include_count=include_count,
    )


def _render_filter_tools(
    filters: tuple[RenderedFilter, ...],
) -> str:
    if not filters:
        return ""
    return render_template(
        "components/table/filter_tools.html",
        filters=filters,
    )


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
                placeholder=filter_.placeholder or t("table.all"),
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
    label = column.short_label or column.label
    label_attributes = _render_attributes(
        {
            "title": column.label if column.short_label else None,
            "aria-label": column.label if column.short_label else None,
        }
    )
    class_names = [
        name
        for name in (
            "numeric" if column.numeric else None,
            "table-column-hidden" if column.hidden else None,
        )
        if name
    ]
    header_attributes = _render_attributes(
        {
            "class": " ".join(class_names) or None,
            "hidden": "" if column.hidden else None,
            "data-total-column": index if column.totalable else None,
        }
    )
    is_sortable = sortable and column.sortable
    total_html = (
        '<span class="column-total" data-column-total aria-live="polite"></span>'
        if column.totalable
        else ""
    )

    direction = _default_direction(column, default_sort)
    indicator_class = "sort-indicator"
    aria_sort = "none"
    if is_sortable and direction == "asc":
        indicator_class = "sort-indicator mdi mdi-arrow-up"
        aria_sort = "ascending"
    elif is_sortable and direction == "desc":
        indicator_class = "sort-indicator mdi mdi-arrow-down"
        aria_sort = "descending"

    return render_template(
        "components/table/header.html",
        header_attributes=header_attributes,
        label_attributes=label_attributes,
        sortable=is_sortable,
        aria_sort=aria_sort,
        column_index=index,
        sort_type=column.sort_type,
        sort_direction=direction or "none",
        label=label,
        total_html=total_html,
        indicator_class=indicator_class,
    )


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
            "data-row-toggle": "" if row.details_html else None,
        }
    )
    rendered_row = render_template(
        "components/table/row.html",
        attributes=attributes,
        cells=cells,
    )
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
    return render_template(
        "components/table/detail_row.html",
        rendered_row=rendered_row,
        detail_attributes=detail_attributes,
        colspan=colspan,
        details_html=row.details_html,
    )


def _render_expander_cell(row: TableRow, detail_row_id: str) -> str:
    if not row.details_html:
        detail_row_id = ""

    return render_template(
        "components/table/expander_cell.html",
        detail_row_id=detail_row_id,
    )


def _render_cell(cell: TableCell, column: TableColumn) -> str:
    class_names = [
        name
        for name in (
            cell.class_name,
            "numeric" if column.numeric else None,
            "table-column-hidden" if column.hidden else None,
        )
        if name
    ]
    attributes = _render_attributes(
        {
            "class": " ".join(class_names) or None,
            "hidden": "" if column.hidden else None,
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
            rendered.append(html_attr(name))
        else:
            rendered.append(f'{html_attr(name)}="{html_attr(value)}"')
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
