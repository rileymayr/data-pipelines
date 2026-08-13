"""Build Plotly-compatible chart payloads from processed survey data."""

import re

import pandas as pd


GENERATED_COLUMN_PATTERN = re.compile(r"(?:_W\d+|_\d+)$")


def get_column_names(dataframe: pd.DataFrame) -> list[str]:
    """Return columns intended for interactive chart configuration."""

    return [
        str(column)
        for column in dataframe.columns
        if not GENERATED_COLUMN_PATTERN.search(str(column))
    ]


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


def build_plot(
    dataframe: pd.DataFrame,
    plot_type: str,
    x_column: str | None = None,
    y_column: str | None = None,
    color_column: str | None = None,
    title: str | None = None,
) -> dict:
    """Build traces and layout for one configured chart."""

    plot_type = plot_type.lower()
    x_column = x_column or None
    y_column = y_column or None
    color_column = color_column or None
    if color_column:
        _require_column(dataframe, color_column, "group/color")

    traces = []
    if plot_type == "bar":
        x_column = _require_column(dataframe, x_column, "X-axis")
        for group_name, frame in _groups(dataframe, color_column):
            if y_column:
                _require_column(dataframe, y_column, "Y-axis")
                values = _numeric_series(frame, y_column)
                clean = frame.assign(__chart_value__=values).dropna(subset=["__chart_value__"])
                summary = clean.groupby(x_column, sort=False)["__chart_value__"].mean()
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
        default_title = f"Distribution of {x_column}"
        layout = _layout(title or default_title, x_column, y_column or "Count")

    elif plot_type == "histogram":
        x_column = _require_column(dataframe, x_column, "X-axis")
        for group_name, frame in _groups(dataframe, color_column):
            values = _numeric_series(frame, x_column).dropna()
            trace = {
                "type": "histogram",
                "x": _python_values(values),
            }
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
