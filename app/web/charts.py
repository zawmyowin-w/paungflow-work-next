"""Server-side SVG charts.

The browser receives finished SVG markup, so the interface needs no charting
library and no client-side data loading.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from html import escape

from markupsafe import Markup

from app.domain.records import ForecastRunRecord, SeriesComparison
from app.domain.series import TimeSeriesPoint

MODEL_COLORS: dict[str, str] = {
    "LSTM": "#cf5270",
    "GRU": "#0a947b",
    "RGF-LSTM": "#9159cf",
}
DEFAULT_MODEL_COLOR: str = "#8294a8"
HISTORY_COLOR: str = "#1976c9"
ACTUAL_COLOR: str = "#1976c9"
PREDICTED_COLOR: str = "#c69536"

OVERVIEW_VIEWBOX: str = "0 0 1000 330"
LINE_VIEWBOX: str = "0 0 1160 360"
SCATTER_VIEWBOX: str = "0 0 470 340"

EMPTY_OVERVIEW: str = "Upload a CSV or load the synthetic sample to populate this chart"
EMPTY_LINE: str = "No historical series is available for this run."
EMPTY_SCATTER: str = "No holdout points available."

UNIT_PATTERN: str = r"m3|m³|cms|cumec"
UNIT_LABEL: str = "m³/s"
DEFAULT_UNIT_LABEL: str = "dataset units"


def number(value: float, digits: int = 2) -> str:
    """Return a human readable number without trailing zeros."""

    if not math.isfinite(value):
        return "—"
    text = f"{value:,.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def unit_label(target_column: str) -> str:
    """Return the measurement unit of a target column."""

    lowered = target_column.lower()
    if any(token in lowered for token in ("m3", "m³", "cms", "cumec")):
        return UNIT_LABEL
    return DEFAULT_UNIT_LABEL


def overview_chart(points: Sequence[TimeSeriesPoint], runs: Sequence[ForecastRunRecord]) -> Markup:
    """Return the dashboard chart with the history and the forecast series."""

    if not points:
        return _empty_svg(OVERVIEW_VIEWBOX, EMPTY_OVERVIEW)

    history = list(points)
    forecast_runs = [run for run in runs if run.forecast]
    horizon = max([7, *[len(run.forecast) for run in forecast_runs]])
    values = [point.value for point in history]
    for run in forecast_runs:
        values.extend(point.value for point in run.forecast)
    low, high = min(values), max(values)
    padding = max((high - low) * 0.14, abs(high) * 0.04, 0.1)
    minimum, maximum = low - padding, high + padding
    total = max(2, len(history) + horizon - 1)

    def x_of(index: float) -> float:
        return 66 + (index / (total - 1)) * (970 - 66)

    def y_of(value: float) -> float:
        return 266 - ((value - minimum) / (maximum - minimum or 1)) * (266 - 28)

    parts: list[str] = []
    for step in range(5):
        y = 28 + (step / 4) * (266 - 28)
        value = maximum - (step / 4) * (maximum - minimum)
        parts.append(
            f'<line x1="66" y1="{y:.2f}" x2="970" y2="{y:.2f}" stroke="var(--line)" stroke-dasharray="3 5"/>'
        )
        parts.append(
            f'<text x="57" y="{y + 4:.2f}" text-anchor="end" fill="var(--muted)" font-size="10">'
            f"{number(value, 1)}</text>"
        )

    history_points = " ".join(
        f"{x_of(index):.2f},{y_of(point.value):.2f}" for index, point in enumerate(history)
    )
    parts.append(
        f'<polyline points="{history_points}" fill="none" stroke="{HISTORY_COLOR}" stroke-width="3" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )

    last_index = len(history) - 1
    for run in forecast_runs:
        color = MODEL_COLORS.get(run.model_name, DEFAULT_MODEL_COLOR)
        coordinates = [f"{x_of(last_index):.2f},{y_of(history[-1].value):.2f}"]
        for offset, point in enumerate(run.forecast):
            coordinates.append(f"{x_of(last_index + offset + 1):.2f},{y_of(point.value):.2f}")
        parts.append(
            f'<polyline points="{" ".join(coordinates)}" fill="none" stroke="{color}" stroke-width="3" '
            'stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="7 5"/>'
        )
        end_point = run.forecast[-1]
        parts.append(
            f'<circle cx="{x_of(last_index + len(run.forecast)):.2f}" cy="{y_of(end_point.value):.2f}" '
            f'r="4" fill="{color}"/>'
        )

    if forecast_runs:
        divider = x_of(last_index)
        parts.append(
            f'<line x1="{divider:.2f}" y1="28" x2="{divider:.2f}" y2="266" stroke="var(--muted)" '
            'stroke-dasharray="3 4" opacity=".7"/>'
        )
        parts.append(
            f'<text x="{min(divider + 6, 880):.2f}" y="40" fill="var(--muted)" font-size="9">'
            "forecast →</text>"
        )

    label_positions = [(66, "start"), (x_of((len(history) - 1) / 2), "middle"), (x_of(last_index), "end")]
    label_texts = [history[0].label, history[len(history) // 2].label, history[-1].label]
    for (position, anchor), label in zip(label_positions, label_texts, strict=True):
        parts.append(
            f'<text x="{position:.2f}" y="287" text-anchor="{anchor}" fill="var(--muted)" font-size="9">'
            f"{escape(label[:16])}</text>"
        )

    return Markup(
        f'<svg viewBox="{OVERVIEW_VIEWBOX}" role="img" '
        f'aria-label="Historical inflow and forecast series">{"".join(parts)}</svg>'
    )


def actual_vs_predicted_chart(history: Sequence[SeriesComparison], unit: str) -> Markup:
    """Return the actual-versus-predicted line chart of the result page."""

    if not history:
        return _empty_svg(LINE_VIEWBOX, EMPTY_LINE)

    height = 360
    left, right, top, bottom = 75, 24, 24, 62
    width = max(1160, left + right + (len(history) - 1) * 20)
    chart_width = width - left - right
    chart_height = height - top - bottom
    values: list[float] = []
    for row in history:
        values.append(row.actual)
        if row.predicted is not None:
            values.append(row.predicted)
    low, high = min(values), max(values)
    padding = max((high - low) * 0.1, abs(high) * 0.06, 0.1)
    low -= padding
    high += padding

    def x_of(index: float) -> float:
        return left + (index / max(1, len(history) - 1)) * chart_width

    def y_of(value: float) -> float:
        return top + chart_height - ((value - low) / (high - low or 1)) * chart_height

    parts: list[str] = []
    for tick in range(5):
        y = top + (tick / 4) * chart_height
        value = high - (tick / 4) * (high - low)
        parts.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" stroke="var(--line)"/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" fill="var(--muted)" font-size="11">'
            f"{number(value, 1)}</text>"
        )

    actual_points = " ".join(f"{x_of(index):.2f},{y_of(row.actual):.2f}" for index, row in enumerate(history))
    predicted_points = " ".join(
        f"{x_of(index):.2f},{y_of(row.predicted):.2f}"
        for index, row in enumerate(history)
        if row.predicted is not None
    )
    parts.append(
        f'<polyline points="{actual_points}" fill="none" stroke="{ACTUAL_COLOR}" stroke-width="2.7" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
    )
    parts.append(
        f'<polyline points="{predicted_points}" fill="none" stroke="{PREDICTED_COLOR}" stroke-width="2.7" '
        'stroke-dasharray="8 5" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    tick_count = min(len(history), max(1, chart_width // 100 + 1))
    label_indices = (
        [round(step * (len(history) - 1) / (tick_count - 1)) for step in range(tick_count)]
        if tick_count > 1
        else [0]
    )
    for index, row in enumerate(history):
        details = f"Date: {row.label} · Actual inflow: {number(row.actual)} {unit}"
        if row.predicted is not None:
            details += f" · Predicted inflow: {number(row.predicted)} {unit}"
        parts.append(
            f'<circle cx="{x_of(index):.2f}" cy="{y_of(row.actual):.2f}" r="2.5" '
            f'fill="{ACTUAL_COLOR}"><title>{escape(details)}</title></circle>'
        )

    for index in dict.fromkeys(label_indices):
        anchor = "start" if index == 0 else "end" if index == len(history) - 1 else "middle"
        parts.append(
            f'<text x="{x_of(index):.2f}" y="{height - 26}" text-anchor="{anchor}" fill="var(--muted)" '
            f'font-size="10">{escape(str(history[index].label)[:20])}</text>'
        )

    parts.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_height}" stroke="var(--muted)"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{top + chart_height}" x2="{width - right}" y2="{top + chart_height}" '
        'stroke="var(--muted)"/>'
    )
    parts.append(
        f'<text x="20" y="{top + chart_height / 2:.2f}" '
        f'transform="rotate(-90 20 {top + chart_height / 2:.2f})" '
        f'text-anchor="middle" fill="var(--ink)" font-size="12">Inflow ({escape(unit)})</text>'
    )
    parts.append(
        f'<text x="{left + chart_width / 2:.2f}" y="{height - 3}" text-anchor="middle" fill="var(--ink)" '
        'font-size="12">Date</text>'
    )

    return Markup(
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="width:{width}px;height:{height}px;max-width:none;min-height:0" role="img" '
        f'aria-label="Actual and predicted inflow over time">{"".join(parts)}</svg>'
    )


def scatter_chart(rows: Sequence[SeriesComparison], unit: str, r2: float | None) -> Markup:
    """Return the holdout scatter plot of the result page."""

    if not rows:
        return _empty_svg(SCATTER_VIEWBOX, EMPTY_SCATTER)

    width, height = 470, 340
    left, right, top, bottom = 64, 19, 23, 58
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [value for row in rows for value in (row.actual, row.predicted or 0.0)]
    maximum = max(1.0, *values) * 1.08

    def x_of(value: float) -> float:
        return left + (value / maximum) * plot_width

    def y_of(value: float) -> float:
        return top + plot_height - (value / maximum) * plot_height

    parts: list[str] = []
    for tick in range(5):
        value = maximum * tick / 4
        parts.append(
            f'<line x1="{left}" y1="{y_of(value):.2f}" x2="{width - right}" y2="{y_of(value):.2f}" '
            'stroke="var(--line)"/>'
        )
        parts.append(
            f'<line x1="{x_of(value):.2f}" y1="{top}" x2="{x_of(value):.2f}" y2="{top + plot_height}" '
            'stroke="var(--line)"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y_of(value) + 4:.2f}" text-anchor="end" fill="var(--muted)" '
            f'font-size="10">{number(value, 0)}</text>'
        )
        parts.append(
            f'<text x="{x_of(value):.2f}" y="{top + plot_height + 17}" text-anchor="middle" '
            f'fill="var(--muted)" font-size="10">{number(value, 0)}</text>'
        )

    for row in rows:
        predicted = row.predicted or 0.0
        parts.append(
            f'<circle cx="{x_of(row.actual):.2f}" cy="{y_of(predicted):.2f}" r="3.6" fill="{ACTUAL_COLOR}" '
            'fill-opacity=".78">'
            f"<title>Actual {escape(number(row.actual))} · Predicted {escape(number(predicted))}</title>"
            "</circle>"
        )

    parts.append(
        f'<line x1="{x_of(0):.2f}" y1="{y_of(0):.2f}" x2="{x_of(maximum):.2f}" y2="{y_of(maximum):.2f}" '
        'stroke="var(--ink)" stroke-dasharray="7 5" stroke-width="1.5"/>'
    )
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="var(--muted)"/>')
    parts.append(
        f'<line x1="{left}" y1="{top + plot_height}" x2="{width - right}" y2="{top + plot_height}" '
        'stroke="var(--muted)"/>'
    )
    parts.append(
        f'<text x="{left + plot_width / 2:.2f}" y="{height - 5}" text-anchor="middle" fill="var(--ink)" '
        f'font-size="11">Actual Inflow ({escape(unit)})</text>'
    )
    parts.append(
        f'<text x="16" y="{top + plot_height / 2:.2f}" '
        f'transform="rotate(-90 16 {top + plot_height / 2:.2f})" '
        f'text-anchor="middle" fill="var(--ink)" font-size="11">Predicted Inflow ({escape(unit)})</text>'
    )
    r2_text = number(r2, 3) if r2 is not None and math.isfinite(r2) else "—"
    parts.append(
        f'<rect x="{width - 90}" y="{top + 10}" width="70" height="25" rx="5" fill="var(--blue-soft)" '
        'stroke="var(--line)"/>'
    )
    parts.append(
        f'<text x="{width - 55}" y="{top + 27}" text-anchor="middle" fill="var(--blue)" font-size="11" '
        f'font-weight="700">R² = {escape(r2_text)}</text>'
    )

    return Markup(
        f'<svg viewBox="{SCATTER_VIEWBOX}" role="img" '
        f'aria-label="Scatter plot comparing actual and predicted inflow">{"".join(parts)}</svg>'
    )


def _empty_svg(viewbox: str, message: str) -> Markup:
    """Return an SVG placeholder that explains why the chart is empty."""

    width = int(viewbox.split()[2])
    height = int(viewbox.split()[3])
    return Markup(
        f'<svg viewBox="{viewbox}" role="img" aria-label="{escape(message)}">'
        f'<text x="{width / 2:.0f}" y="{height / 2:.0f}" text-anchor="middle" fill="currentColor" '
        f'font-size="14">{escape(message)}</text></svg>'
    )
