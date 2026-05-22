from resprint.presentation.table_renderer import (
    DefaultSort,
    TableCell,
    TableColumn,
    TableRow,
    render_table_section,
)


def test_render_table_section_supports_search_sort_and_default_sort() -> None:
    html = render_table_section(
        section_id="tickets",
        title="Tickets",
        columns=[
            TableColumn("key", "Issue key"),
            TableColumn("time", "Temps", numeric=True, sort_type="number"),
        ],
        rows=[
            TableRow(
                cells={
                    "key": TableCell("<strong>ABC-1</strong>"),
                    "time": TableCell("2.00 h", sort_value=7200),
                },
                search_text="ABC-1",
                style="warning",
            )
        ],
        default_sort=DefaultSort("time", "desc"),
        section_attributes={"data-report-table": ""},
    )

    assert 'id="tickets"' in html
    assert "data-enhanced-table" in html
    assert "data-report-table" in html
    assert "data-table-search" in html
    assert 'data-sort-column="1"' in html
    assert 'data-default-sort-column="1"' in html
    assert 'data-default-sort-direction="desc"' in html
    assert 'aria-sort="descending"' in html
    assert "mdi-arrow-down" in html
    assert 'class="table-row-warning" data-search="abc-1"' in html
    assert 'class="numeric" data-sort-value="7200"' in html
    assert "<strong>ABC-1</strong>" in html


def test_table_css_contains_supported_row_styles() -> None:
    from resprint.presentation.table_renderer import table_css

    css = table_css()

    assert "tr.table-row-success" in css
    assert "tr.table-row-warning" in css
    assert "tr.table-row-error" in css
    assert "tr.table-row-info" in css
    assert 'html[data-theme="dark"] tr.table-row-warning' in css


def test_render_table_section_can_disable_search_and_sort() -> None:
    html = render_table_section(
        section_id="plain",
        title="Plain",
        columns=[TableColumn("key", "Issue key")],
        rows=[TableRow(cells={"key": TableCell("ABC-1")})],
        searchable=False,
        sortable=False,
    )

    assert "data-table-search" not in html
    assert "data-sort-column" not in html
    assert "<th>Issue key</th>" in html
