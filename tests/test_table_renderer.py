from importlib.resources import files

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
            TableColumn(
                "time",
                "Temps",
                numeric=True,
                totalable=True,
                sort_type="number",
            ),
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
    assert 'data-total-column="1"' in html
    assert "data-column-total" in html
    assert 'data-default-sort-column="1"' in html
    assert 'data-default-sort-direction="desc"' in html
    assert 'aria-sort="descending"' in html
    assert "mdi-arrow-down" in html
    assert 'class="table-row-warning" data-table-row data-search="abc-1"' in html
    assert 'class="numeric" data-sort-value="7200"' in html
    assert "<strong>ABC-1</strong>" in html


def test_render_table_section_supports_short_column_labels() -> None:
    html = render_table_section(
        section_id="tickets",
        title="Tickets",
        columns=[
            TableColumn(
                "time",
                "Temps total consommé",
                short_label="Total",
                numeric=True,
                sort_type="number",
            ),
        ],
        rows=[TableRow(cells={"time": TableCell("2.00 h", sort_value=7200)})],
    )

    assert 'title="Temps total consommé"' in html
    assert 'aria-label="Temps total consommé"' in html
    assert "<span>Total</span>" in html
    assert "<span>Temps total consommé</span>" not in html


def test_table_css_contains_supported_row_styles() -> None:
    from resprint.frontend.utils.table import table_css

    css_url = table_css()
    css = (
        files("resprint.frontend.static")
        .joinpath("min/table.min.css")
        .read_text(encoding="utf-8")
    )

    assert css_url == "/assets/min/table.min.css"
    assert "position:sticky" in css
    assert "min-width:860px" in css
    assert "tr[data-row-toggle]" in css
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
    assert "<span>Issue key</span>" in html


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
    assert "data-filter-selected-label=" in html
    assert "<span>Type</span>" in html
    assert "Tous les types" in html
    assert 'value="bug"' in html
    assert 'value="story"' in html
    assert "data-filter-option" in html


def test_render_table_section_supports_hidden_filter_columns() -> None:
    html = render_table_section(
        section_id="tickets",
        title="Tickets",
        columns=[
            TableColumn("key", "Issue key"),
            TableColumn("project_key", "Project", hidden=True, sortable=False),
            TableColumn("issue_type", "Type"),
        ],
        rows=[
            TableRow(
                cells={
                    "key": TableCell("ABC-1"),
                    "project_key": TableCell("ABC"),
                    "issue_type": TableCell("Story"),
                },
            ),
            TableRow(
                cells={
                    "key": TableCell("XYZ-2"),
                    "project_key": TableCell("XYZ"),
                    "issue_type": TableCell("Bug"),
                },
            ),
        ],
        filters=[TableFilter("project_key", "Project", "All projects")],
    )

    assert 'class="table-column-hidden" hidden' in html
    assert 'data-filter-column="1"' in html
    assert "All projects" in html
    assert 'value="abc"' in html
    assert 'value="xyz"' in html
    assert "data-filter-option" in html
    assert 'data-sort-column="1"' not in html


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

    assert '<th class="row-expander-header" aria-label="Détails"></th>' in html
    assert "data-row-toggle" in html
    assert "data-row-toggle-button" in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="tickets-detail-0"' in html
    assert (
        'data-table-row data-search data-detail-row-id="tickets-detail-0" '
        "data-row-toggle"
    ) in html
    assert 'id="tickets-detail-0"' in html
    assert "data-table-detail-row" in html
    assert 'colspan="3"' in html
    assert "<strong>Details</strong>" in html
    assert 'data-sort-column="1"' in html
    assert 'data-default-sort-column="1"' in html
    assert 'data-filter-column="2"' in html


def test_filters_ignore_unknown_columns_and_placeholder_rows():
    html = render_table_section(
        section_id="partial",
        title="Partial data",
        columns=[TableColumn("key", "Key"), TableColumn("owner", "Owner")],
        rows=[
            TableRow(cells={"key": TableCell("A-2"), "owner": TableCell("-")}),
            TableRow(cells={"key": TableCell("A-3"), "owner": TableCell(" ")}),
            TableRow(cells={"key": TableCell("A-4"), "owner": TableCell("Alice")}),
        ],
        filters=[TableFilter("missing", "Unknown"), TableFilter("owner", "Owner")],
    )
    assert html.count("data-table-filter") == 1
    assert 'value="alice"' in html
    assert 'value="-"' not in html
    assert 'value=""' not in html
    assert "Unknown" not in html
    for key in ("A-2", "A-3", "A-4"):
        assert key in html


def test_empty_filter_options_and_stale_default_sort_are_omitted():
    html = render_table_section(
        section_id="empty",
        title="Empty",
        columns=[TableColumn("owner", "Owner")],
        rows=[TableRow(cells={"owner": TableCell("-")})],
        filters=[TableFilter("owner", "Owner")],
        default_sort=DefaultSort("removed-column"),
    )
    assert "data-table-filter" not in html
    assert "data-default-sort-column" not in html
    assert "<td>-</td>" in html


def test_mixed_detail_rows_only_offer_expansion_where_details_exist():
    html = render_table_section(
        section_id="mixed",
        title="Mixed",
        columns=[TableColumn("key", "Key")],
        rows=[
            TableRow(cells={"key": TableCell("A-1")}, details_html="<p>Details</p>"),
            TableRow(cells={"key": TableCell("A-2")}),
        ],
    )
    assert html.count("data-row-toggle-button") == 1
    assert html.count("data-table-detail-row") == 1
    assert 'aria-controls="mixed-detail-0"' in html
    assert 'aria-controls="mixed-detail-1"' not in html
    assert 'colspan="2"' in html
    assert "A-2" in html


def test_badge_labels_and_custom_classes_are_escaped():
    from html.parser import HTMLParser

    from resprint.frontend.utils.table import badge_cell

    cell = badge_cell("<script>unsafe</script>", class_name='custom" onclick="bad')
    assert "&lt;script&gt;unsafe&lt;/script&gt;" in cell.html

    class Tags(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert tag == "span"
            assert dict(attrs) == {"class": 'badge custom" onclick="bad'}

    Tags().feed(cell.html)
