"""Utilities for exporting pandas describe() demographic summaries."""

import io
import re
import zipfile

import pandas as pd


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_") or "field"


_DESCRIBE_HEADERS = {
    "count": "Non-missing Count",
    "unique": "Unique Value Count",
    "top": "Most Common Value",
    "freq": "Most Common Value Count",
    "mean": "Mean",
    "std": "Standard Deviation",
    "min": "Minimum",
    "25%": "25th Percentile",
    "50%": "Median (50th Percentile)",
    "75%": "75th Percentile",
    "max": "Maximum",
}


def _describe_column(dataframe: pd.DataFrame, column: str) -> pd.DataFrame:
    """Return one clearly labeled row from pandas' all-types describe output."""

    summary = dataframe[[column]].describe(include="all").T.reset_index()
    summary = summary.rename(columns={"index": "Column", **_DESCRIBE_HEADERS})
    return summary


def _describe_grouped(
    dataframe: pd.DataFrame,
    column: str,
    group_by: str,
) -> pd.DataFrame:
    """Return one describe() row per grouping value."""

    grouped_data = dataframe.copy()
    group_values = grouped_data[group_by].astype("object")
    grouped_data[group_by] = group_values.where(group_values.notna(), "Missing")
    summary = grouped_data.groupby(group_by, dropna=False)[column].describe(include="all")
    summary = summary.reset_index()
    summary = summary.rename(columns={group_by: "Group", **_DESCRIBE_HEADERS})
    return summary


def create_demographics_zip(
    dataframe: pd.DataFrame,
    requested_columns: list[str],
    group_by: str | None = None,
) -> bytes:
    """Return per-column pandas describe() summaries and one combined CSV."""

    selected = list(dict.fromkeys(
        column for column in requested_columns if column in dataframe.columns
    ))
    if not selected:
        raise ValueError("Select at least one demographic column.")
    if group_by and group_by not in dataframe.columns:
        raise ValueError(f"Grouping column was not found: {group_by}")

    archive_bytes = io.BytesIO()
    combined = []
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        for column in selected:
            if group_by:
                breakdown = _describe_grouped(dataframe, column, group_by)
            else:
                breakdown = _describe_column(dataframe, column)
            if group_by:
                filename = f"{_safe_filename(column)}_grouped-by_{_safe_filename(group_by)}.csv"
                combined_part = breakdown.assign(Column=column, **{"Group By": group_by})
            else:
                filename = f"{_safe_filename(column)}.csv"
                combined_part = breakdown.assign(**{"Group By": ""})
            archive.writestr(filename, breakdown.to_csv(index=False))
            combined.append(combined_part)

        all_breakdowns = pd.concat(combined, ignore_index=True, sort=False)
        if group_by:
            all_breakdowns = all_breakdowns[["Column", "Group By", "Group"] + [
                column for column in all_breakdowns.columns
                if column not in {"Column", "Group By", "Group"}
            ]]
        else:
            all_breakdowns = all_breakdowns[["Column", "Group By"] + [
                column for column in all_breakdowns.columns
                if column not in {"Column", "Group By"}
            ]]
        archive.writestr("all_breakdowns.csv", all_breakdowns.to_csv(index=False))

    return archive_bytes.getvalue()
