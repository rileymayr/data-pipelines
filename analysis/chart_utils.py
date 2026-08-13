"""Small, browser-friendly helpers for building Plotly chart payloads."""

import re

import pandas as pd


GENERATED_COLUMN_PATTERN = re.compile(r"(?:_W\d+|_\d+)$")


def get_column_names(dataframe: pd.DataFrame) -> list[str]:
    """Return chartable columns, excluding generated weekly/suffixed columns."""

    return [
        str(column)
        for column in dataframe.columns
        if not GENERATED_COLUMN_PATTERN.search(str(column))
    ]


def build_bar_chart(dataframe: pd.DataFrame, column: str) -> dict:
    """Build a value-counts bar chart for one column."""

    if column not in dataframe.columns:
        raise ValueError(f"Column not found in the processed dataframe: {column}")

    counts = (
        dataframe[column]
        .fillna("Missing")
        .astype(str)
        .value_counts()
    )
    labels = counts.index.tolist()
    values = counts.tolist()

    return {
        "trace": {
            "type": "bar",
            "x": labels,
            "y": values,
            "hovertemplate": "%{x}<br>Count: %{y}<extra></extra>",
        },
        "layout": {
            "title": f"Distribution of {column}",
            "xaxis": {"title": column, "automargin": True},
            "yaxis": {"title": "Count"},
            "margin": {"l": 60, "r": 20, "t": 60, "b": 100},
        },
    }


def _numeric_values(dataframe: pd.DataFrame, column: str) -> list:
    """Return usable numeric values for histogram, scatter, and violin plots."""

    values = pd.to_numeric(dataframe[column], errors="coerce").dropna()
    if values.empty:
        raise ValueError(f"Column '{column}' does not contain numeric values.")
    return values.tolist()


def build_plot(dataframe: pd.DataFrame, plot_type: str, columns: list[str]) -> dict:
    """Build a Plotly trace and layout for the requested chart type."""

    plot_type = plot_type.lower()
    if plot_type == "bar":
        if not columns:
            raise ValueError("Select at least one column to chart.")
        charts = [build_bar_chart(dataframe, column) for column in columns]
        return charts[0] if len(charts) == 1 else {
            "traces": [chart["trace"] for chart in charts],
            "layout": {"title": "Selected column distributions", "yaxis": {"title": "Count"}},
        }

    if plot_type == "scatterplot":
        if len(columns) != 2:
            raise ValueError("Select exactly two columns for a scatterplot (X, then Y).")
        x_column, y_column = columns
        return {
            "trace": {
                "type": "scatter",
                "mode": "markers",
                "x": _numeric_values(dataframe, x_column),
                "y": _numeric_values(dataframe, y_column),
                "name": f"{y_column} vs {x_column}",
            },
            "layout": {
                "title": f"{y_column} vs {x_column}",
                "xaxis": {"title": x_column},
                "yaxis": {"title": y_column},
            },
        }

    if plot_type in {"histogram", "violin"}:
        if not columns:
            raise ValueError("Select at least one column to chart.")
        traces = []
        for column in columns:
            values = _numeric_values(dataframe, column)
            traces.append(
                {
                    "type": plot_type,
                    "x": values if plot_type == "histogram" else None,
                    "y": values if plot_type == "violin" else None,
                    "name": column,
                }
            )
        return {
            "traces": traces,
            "layout": {
                "title": f"{plot_type.title()} of selected columns",
                "barmode": "overlay" if plot_type == "histogram" else None,
                "xaxis": {"title": "Value"},
                "yaxis": {"title": "Count" if plot_type == "histogram" else "Value"},
            },
        }

    raise ValueError(f"Unsupported plot type: {plot_type}")
