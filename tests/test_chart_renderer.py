from resprint.frontend.utils.charts import render_chart


def test_render_chart_outputs_canvas_with_serialized_config() -> None:
    html = render_chart(
        "ticket-chart",
        {
            "type": "bar",
            "data": {"labels": ["Termines"], "datasets": [{"data": [3]}]},
        },
        label="Repartition des tickets",
    )

    assert html.startswith('<canvas id="ticket-chart"')
    assert 'class="chart-canvas"' in html
    assert 'role="img"' in html
    assert 'aria-label="Repartition des tickets"' in html
    assert "data-chart-config=" in html
    assert "&#34;type&#34;:&#34;bar&#34;" in html


def test_render_chart_escapes_attributes_and_config() -> None:
    html = render_chart(
        'chart-"x"',
        {"data": {"labels": ['A "quoted" label']}},
        label='Label "quoted"',
        class_name='chart "custom"',
    )

    assert 'id="chart-&#34;x&#34;"' in html
    assert 'class="chart &#34;custom&#34;"' in html
    assert 'aria-label="Label &#34;quoted&#34;"' in html
    assert "A \\&#34;quoted\\&#34; label" in html
