"""Build Plotly-compatible chart payloads from processed survey data."""

import re

import pandas as pd


GENERATED_COLUMN_PATTERN = re.compile(r"(?:_W\d+|_\d+)$")


def get_column_names(dataframe: pd.DataFrame) -> list[str]:
    """Return columns intended for interactive chart configuration."""

    columns = [
        str(column)
        for column in dataframe.columns
        if not GENERATED_COLUMN_PATTERN.search(str(column))
    ]
    # Weekly values are stored wide (for example, Trust_W1, Trust_W2, ...).
    # Expose the logical measure once so the line chart can resolve its weeks.
    visible = set(columns)
    for column in dataframe.columns:
        match = re.match(r"^(?P<measure>.+)_W\d+$", str(column), re.IGNORECASE)
        if match and match.group("measure") not in visible:
            columns.append(match.group("measure"))
            visible.add(match.group("measure"))
    return columns


def get_weekly_column_names(
    dataframe: pd.DataFrame, weeks: tuple[int, ...] = (1, 2, 3)
) -> list[str]:
    """Return logical measures that have every requested wide weekly column."""

    weekly_columns = {str(column) for column in dataframe.columns}
    measures = []
    seen = set()
    for column in dataframe.columns:
        match = re.match(r"^(?P<measure>.+)_W(?P<week>\d+)$", str(column), re.IGNORECASE)
        if not match:
            continue
        measure = match.group("measure")
        if measure in seen:
            continue
        expected = {f"{measure}_W{week}" for week in weeks}
        if expected.issubset(weekly_columns):
            measures.append(measure)
            seen.add(measure)
    return measures


def _require_column(dataframe: pd.DataFrame, column: str | None, label: str) -> str:
    if not column or column not in dataframe.columns:
        raise ValueError(f"Choose a valid {label} column.")
    return column


def _numeric_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(dataframe[column], errors="coerce")
    if values.notna().sum() == 0:
        raise ValueError(f"Column '{column}' does not contain numeric values.")
    return values


def _python_values(values) -> list:
    """Convert Pandas/NumPy scalar values into JSON-serializable Python values."""

    return [value.item() if hasattr(value, "item") else value for value in list(values)]


def _groups(dataframe: pd.DataFrame, color_column: str | None):
    if color_column:
        grouped = dataframe.copy()
        grouped["__chart_color__"] = grouped[color_column].fillna("Missing").astype(str)
        return grouped.groupby("__chart_color__", sort=False, dropna=False)
    return [(None, dataframe)]


def _layout(title: str, x_title: str | None = None, y_title: str | None = None) -> dict:
    return {
        "title": title,
        "xaxis": {"title": x_title or ""},
        "yaxis": {"title": y_title or ""},
        "margin": {"l": 60, "r": 20, "t": 60, "b": 80},
    }


def _weekly_columns(dataframe: pd.DataFrame, measure: str) -> list[tuple[int, str]]:
    """Return available wide-form weekly columns for a logical measure."""

    measure = str(measure)
    columns = []
    for column in dataframe.columns:
        match = re.match(r"^(?P<measure>.+)_W(?P<week>\d+)$", str(column), re.IGNORECASE)
        if match and match.group("measure") == measure:
            columns.append((int(match.group("week")), str(column)))
    return sorted(columns)


_BAR_AGGREGATIONS = {
    "count": ("count", "Count"),
    "sum": ("sum", "Sum"),
    "mean": ("mean", "Average"),
    "average": ("mean", "Average"),
}


def _build_single_plot(
    dataframe: pd.DataFrame,
    plot_type: str,
    x_column: str | None = None,
    y_column: str | None = None,
    color_column: str | None = None,
    title: str | None = None,
    aggregation: str = "mean",
    bin_width: float | None = None,
    bin_count: float | None = None,
) -> dict:
    """Build traces and layout for one configured, non-faceted chart."""

    plot_type = plot_type.lower()
    x_column = x_column or None
    y_column = y_column or None
    color_column = color_column or None
    if plot_type == "histogram":
        if bin_width is not None and bin_count is not None:
            raise ValueError("Choose either a histogram bin width or bin count, not both.")
        if bin_width is not None and bin_width <= 0:
            raise ValueError("Histogram bin width must be greater than zero.")
        if bin_count is not None and (bin_count <= 0 or int(bin_count) != bin_count):
            raise ValueError("Histogram bin count must be a positive whole number.")
    if color_column:
        _require_column(dataframe, color_column, "group/color")

    traces = []
    if plot_type == "line":
        measure = x_column or y_column
        if not measure:
            raise ValueError("Choose a weekly measure column.")
        weekly_columns = [
            item for item in _weekly_columns(dataframe, measure) if item[0] in (1, 2, 3)
        ]
        if not weekly_columns:
            raise ValueError(
                f"No weekly columns found for '{measure}'. Expected names such as '{measure}_W1'."
            )
        aggregation_key = str(aggregation or "mean").lower()
        if aggregation_key not in _BAR_AGGREGATIONS:
            raise ValueError("Choose Count, Sum, or Average for line aggregation.")
        pandas_aggregation, aggregation_label = _BAR_AGGREGATIONS[aggregation_key]
        for group_name, frame in _groups(dataframe, color_column):
            values = []
            for _week, column in weekly_columns:
                numeric = pd.to_numeric(frame[column], errors="coerce").dropna()
                if numeric.empty:
                    values.append(None)
                else:
                    values.append(float(getattr(numeric, pandas_aggregation)()))
            if any(value is not None for value in values):
                trace = {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": [f"Week {week}" for week, _column in weekly_columns],
                    "y": values,
                }
                if group_name is not None:
                    trace["name"] = str(group_name)
                traces.append(trace)
        default_title = f"{measure} progression by week"
        layout = _layout(title or default_title, "Week", f"{aggregation_label} {measure}")

    elif plot_type == "bar":
        x_column = _require_column(dataframe, x_column, "X-axis")
        aggregation_key = str(aggregation or "mean").lower()
        if aggregation_key not in _BAR_AGGREGATIONS:
            raise ValueError("Choose Count, Sum, or Average for bar aggregation.")
        pandas_aggregation, aggregation_label = _BAR_AGGREGATIONS[aggregation_key]
        for group_name, frame in _groups(dataframe, color_column):
            if y_column:
                _require_column(dataframe, y_column, "Y-axis")
                values = _numeric_series(frame, y_column)
                clean = frame.assign(__chart_value__=values).dropna(subset=["__chart_value__"])
                summary = clean.groupby(x_column, sort=False)["__chart_value__"].agg(pandas_aggregation)
                trace = {
                    "type": "bar",
                    "x": summary.index.astype(str).tolist(),
                    "y": _python_values(summary),
                }
            else:
                summary = frame[x_column].fillna("Missing").astype(str).value_counts()
                trace = {
                    "type": "bar",
                    "x": summary.index.tolist(),
                    "y": _python_values(summary),
                }
            if group_name is not None:
                trace["name"] = str(group_name)
            traces.append(trace)
        default_title = f"{aggregation_label} of {y_column} by {x_column}" if y_column else f"Distribution of {x_column}"
        layout = _layout(title or default_title, x_column, y_column or "Count")

    elif plot_type == "histogram":
        x_column = _require_column(dataframe, x_column, "X-axis")
        for group_name, frame in _groups(dataframe, color_column):
            values = _numeric_series(frame, x_column).dropna()
            trace = {
                "type": "histogram",
                "x": _python_values(values),
            }
            if bin_width is not None:
                trace["xbins"] = {"size": float(bin_width)}
            elif bin_count is not None:
                trace["nbinsx"] = int(bin_count)
            if group_name is not None:
                trace["name"] = str(group_name)
            traces.append(trace)
        default_title = f"Distribution of {x_column}"
        layout = _layout(title or default_title, x_column, "Count")
        if color_column:
            layout["barmode"] = "stack"

    elif plot_type == "scatterplot":
        x_column = _require_column(dataframe, x_column, "X-axis")
        y_column = _require_column(dataframe, y_column, "Y-axis")
        clean = dataframe[[x_column, y_column] + ([color_column] if color_column else [])].copy()
        clean[x_column] = pd.to_numeric(clean[x_column], errors="coerce")
        clean[y_column] = pd.to_numeric(clean[y_column], errors="coerce")
        clean = clean.dropna(subset=[x_column, y_column])
        x_range = [float(clean[x_column].min()), float(clean[x_column].max())]
        colorway = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3"]
        for group_index, (group_name, frame) in enumerate(_groups(clean, color_column)):
            group_color = colorway[group_index % len(colorway)]
            trace = {
                "type": "scatter",
                "mode": "markers",
                "x": _python_values(frame[x_column]),
                "y": _python_values(frame[y_column]),
                "marker": {"color": group_color},
            }
            if group_name is not None:
                trace["name"] = str(group_name)
            traces.append(trace)

            # Add a separate least-squares line for each color/group.
            x_values = frame[x_column]
            y_values = frame[y_column]
            x_mean = x_values.mean()
            y_mean = y_values.mean()
            denominator = ((x_values - x_mean) ** 2).sum()
            if denominator != 0 and len(frame) > 1:
                slope = ((x_values - x_mean) * (y_values - y_mean)).sum() / denominator
                intercept = y_mean - slope * x_mean
                traces.append(
                    {
                        "type": "scatter",
                        "mode": "lines",
                        "x": x_range,
                        "y": [float(slope * value + intercept) for value in x_range],
                        "line": {"color": group_color, "width": 3},
                        "showlegend": False,
                        "hoverinfo": "skip",
                    }
                )
        default_title = f"{y_column} vs {x_column}"
        layout = _layout(title or default_title, x_column, y_column)
        layout["xaxis"]["range"] = x_range

    elif plot_type == "violin":
        y_column = _require_column(dataframe, y_column, "Y-axis")
        for group_name, frame in _groups(dataframe, color_column):
            values = _numeric_series(frame, y_column).dropna()
            trace = {
                "type": "violin",
                "y": _python_values(values),
                "box": {"visible": True},
                "meanline": {"visible": True},
            }
            if x_column:
                _require_column(dataframe, x_column, "X-axis")
                trace["x"] = frame.loc[values.index, x_column].fillna("Missing").astype(str).tolist()
            if group_name is not None:
                trace["name"] = str(group_name)
            traces.append(trace)
        default_title = f"Distribution of {y_column}"
        layout = _layout(title or default_title, x_column, y_column)

    else:
        raise ValueError(f"Unsupported plot type: {plot_type}")

    if not traces:
        raise ValueError("The selected fields do not contain data to plot.")
    return {"traces": traces, "layout": layout}


def build_plot(
    dataframe: pd.DataFrame,
    plot_type: str,
    x_column: str | None = None,
    y_column: str | None = None,
    color_column: str | None = None,
    title: str | None = None,
    aggregation: str = "mean",
    facet_row: str | None = None,
    facet_column: str | None = None,
    share_x: bool = False,
    share_y: bool = False,
    bin_width: float | None = None,
    bin_count: float | None = None,
) -> dict:
    """Build a Plotly-compatible chart, optionally split into facet panels."""

    facet_row = facet_row or None
    facet_column = facet_column or None
    if facet_row:
        _require_column(dataframe, facet_row, "vertical facet")
    if facet_column:
        _require_column(dataframe, facet_column, "horizontal facet")
    if facet_row and facet_column and facet_row == facet_column:
        raise ValueError("Choose different columns for horizontal and vertical facets.")

    if not facet_row and not facet_column:
        return _build_single_plot(
            dataframe, plot_type, x_column, y_column, color_column, title, aggregation,
            bin_width, bin_count
        )

    def facet_values(column):
        return dataframe[column].fillna("Missing").astype(str).drop_duplicates().tolist()

    row_values = facet_values(facet_row) if facet_row else [None]
    column_values = facet_values(facet_column) if facet_column else [None]
    row_count, column_count = len(row_values), len(column_values)
    facet_gap = 0.04
    panel_width = (1 - facet_gap * (column_count - 1)) / column_count
    panel_height = (1 - facet_gap * (row_count - 1)) / row_count
    traces = []
    annotations = []
    combined_layout = {
        "title": title or "",
        "margin": {"l": 60, "r": 20, "t": 80, "b": 60},
        "showlegend": bool(color_column),
    }

    for row_index, row_value in enumerate(row_values):
        for column_index, column_value in enumerate(column_values):
            frame = dataframe
            if facet_row:
                frame = frame[frame[facet_row].fillna("Missing").astype(str) == row_value]
            if facet_column:
                frame = frame[frame[facet_column].fillna("Missing").astype(str) == column_value]
            if frame.empty:
                continue

            single = _build_single_plot(
                frame, plot_type, x_column, y_column, color_column, "", aggregation,
                bin_width, bin_count
            )
            panel_number = row_index * column_count + column_index + 1
            axis_suffix = "" if panel_number == 1 else str(panel_number)
            for trace in single["traces"]:
                trace = dict(trace)
                trace["xaxis"] = "x" + axis_suffix
                trace["yaxis"] = "y" + axis_suffix
                traces.append(trace)

            horizontal_start = column_index * (panel_width + facet_gap)
            horizontal_end = horizontal_start + panel_width
            vertical_end = 1 - row_index * (panel_height + facet_gap)
            vertical_start = vertical_end - panel_height
            combined_layout["xaxis" + axis_suffix] = {
                "domain": [horizontal_start, horizontal_end],
                "anchor": "y" + axis_suffix,
                "title": single["layout"].get("xaxis", {}).get("title", "") if row_index == row_count - 1 else "",
            }
            combined_layout["yaxis" + axis_suffix] = {
                "domain": [vertical_start, vertical_end],
                "anchor": "x" + axis_suffix,
                "title": single["layout"].get("yaxis", {}).get("title", "") if column_index == 0 else "",
            }
            if share_x and facet_row and panel_number > 1:
                combined_layout["xaxis" + axis_suffix]["matches"] = "x"
            if share_y and facet_column and panel_number > 1:
                combined_layout["yaxis" + axis_suffix]["matches"] = "y"
            if facet_column:
                annotations.append({
                    "text": str(column_value), "x": (horizontal_start + horizontal_end) / 2,
                    "y": 1.02, "xref": "paper", "yref": "paper", "showarrow": False,
                })
            if facet_row:
                annotations.append({
                    "text": str(row_value), "x": -0.02, "y": (vertical_start + vertical_end) / 2,
                    "xref": "paper", "yref": "paper", "showarrow": False, "textangle": -90,
                })

    if not traces:
        raise ValueError("The selected fields do not contain data to plot.")
    if not combined_layout["title"]:
        combined_layout["title"] = "Faceted chart"
    combined_layout["annotations"] = annotations
    return {"traces": traces, "layout": combined_layout}
