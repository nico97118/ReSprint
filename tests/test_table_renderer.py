from resprint.frontend.utils.table import (
    DefaultSort,
    TableCell,
    TableColumn,
    TableFilter,
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
    assert 'class="table-row-warning" data-table-row data-search="abc-1"' in html
    assert 'class="numeric" data-sort-value="7200"' in html
    assert "<strong>ABC-1</strong>" in html


def test_table_css_contains_supported_row_styles() -> None:
    from resprint.frontend.utils.table import table_css

    css = table_css()

    assert "position: sticky" in css
    assert "tr.table-row-success" in css
    assert "tr.table-row-warning" in css
    assert "tr.table-row-error" in css
    assert "tr.table-row-info" in css
    assert ".table-detail-row" in css
    assert 'html[data-theme="dark"] tbody tr.table-row-warning' in css


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


def test_render_table_section_supports_column_filters() -> None:
    html = render_table_section(
        section_id="tickets",
        title="Tickets",
        columns=[
            TableColumn("key", "Issue key"),
            TableColumn("issue_type", "Type"),
        ],
        rows=[
            TableRow(
                cells={
                    "key": TableCell("ABC-1"),
                    "issue_type": TableCell("<strong>Story</strong>"),
                },
            ),
            TableRow(
                cells={
                    "key": TableCell("ABC-2"),
                    "issue_type": TableCell("Bug"),
                },
            ),
        ],
        filters=[TableFilter("issue_type", "Type", "Tous les types")],
    )

    assert "data-table-filter" in html
    assert 'data-filter-column="1"' in html
    assert "<span>Type</span>" in html
    assert '<option value="">Tous les types</option>' in html
    assert '<option value="bug">Bug</option>' in html
    assert '<option value="story">Story</option>' in html


def test_render_table_section_supports_expandable_rows() -> None:
    html = render_table_section(
        section_id="tickets",
        title="Tickets",
        columns=[
            TableColumn("key", "Issue key"),
            TableColumn("issue_type", "Type"),
        ],
        rows=[
            TableRow(
                cells={
                    "key": TableCell("ABC-1"),
                    "issue_type": TableCell("Story"),
                },
                details_html="<strong>Details</strong>",
            )
        ],
        filters=[TableFilter("issue_type", "Type")],
        default_sort=DefaultSort("key"),
    )

    assert 'class="row-expander-header"' in html
    assert "data-row-toggle" in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="tickets-detail-0"' in html
    assert 'data-table-row data-search data-detail-row-id="tickets-detail-0"' in html
    assert 'id="tickets-detail-0"' in html
    assert "data-table-detail-row" in html
    assert 'colspan="3"' in html
    assert "<strong>Details</strong>" in html
    assert 'data-sort-column="1"' in html
    assert 'data-default-sort-column="1"' in html
    assert 'data-filter-column="2"' in html
