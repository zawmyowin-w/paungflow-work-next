"""Tests for server-rendered charts."""
from __future__ import annotations

from xml.etree import ElementTree

from app.domain.records import SeriesComparison
from app.web.charts import actual_vs_predicted_chart


def test_actual_vs_predicted_chart_includes_every_point_and_its_data() -> None:
    history = tuple(
        SeriesComparison(
            label=f"2024-01-{day:02d}",
            actual=float(day * 10),
            predicted=float(day * 9) if day > 3 else None,
        )
        for day in range(1, 13)
    )

    svg = ElementTree.fromstring(str(actual_vs_predicted_chart(history, "m³/s")))
    points = svg.findall("circle")
    details = [point.findtext("title") for point in points]

    assert len(points) == len(history)
    assert "Date: 2024-01-01 · Actual inflow: 10 m³/s" in details[0]
    assert "Date: 2024-01-12 · Actual inflow: 120 m³/s · Predicted inflow: 108 m³/s" in details[-1]
