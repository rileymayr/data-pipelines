"""Utilities for exporting pandas describe() demographic summaries."""

import io
import zipfile

import pandas as pd


_DESCRIBE_HEADERS = {
    "count": "Grouping Count",
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
    group_by: list[str],
) -> pd.DataFrame:
    """Return one describe() row per grouping value."""

    grouped_data = dataframe.copy()
    for group_column in group_by:
        group_values = grouped_data[group_column].astype("object")
        grouped_data[group_column] = group_values.where(group_values.notna(), "Missing")
    summary = grouped_data.groupby(group_by, dropna=False)[column].describe(include="all")
    summary = summary.reset_index()
    summary = summary.rename(columns={
        group_column: f"Group: {group_column}" for group_column in group_by
    } | _DESCRIBE_HEADERS)

    # Add an overall reference row for comparison with the full dataset.
    total = _describe_column(dataframe, column).drop(columns=["Column"])
    for group_column in reversed(group_by):
        total.insert(0, f"Group: {group_column}", f"All Groups - {group_column}")
    summary = pd.concat([summary, total], ignore_index=True, sort=False)
    return summary


def create_demographics_zip(
    dataframe: pd.DataFrame,
    requested_columns: list[str],
    group_by: list[str] | None = None,
) -> bytes:
    """Return a ZIP containing the combined pandas describe() CSV only."""

    selected = list(dict.fromkeys(
        column for column in requested_columns if column in dataframe.columns
    ))
    if not selected:
        raise ValueError("Select at least one demographic column.")
    group_by = list(dict.fromkeys(group_by or []))
    missing_group_columns = [column for column in group_by if column not in dataframe.columns]
    if missing_group_columns:
        raise ValueError(
            "Grouping column(s) were not found: " + ", ".join(missing_group_columns)
        )

    archive_bytes = io.BytesIO()
    combined = []
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        for column in selected:
            if group_by:
                breakdown = _describe_grouped(dataframe, column, group_by)
            else:
                breakdown = _describe_column(dataframe, column)
            if group_by:
                combined_part = breakdown.assign(
                    Column=column, **{"Group By": ", ".join(group_by)}
                )
            else:
                combined_part = breakdown.assign(**{"Group By": ""})
            combined.append(combined_part)

        all_breakdowns = pd.concat(combined, ignore_index=True, sort=False)
        if group_by:
            group_headers = [f"Group: {group}" for group in group_by]
            all_breakdowns = all_breakdowns[["Column", "Group By"] + group_headers + [
                column for column in all_breakdowns.columns
                if column not in {"Column", "Group By", *group_headers}
            ]]
        else:
            all_breakdowns = all_breakdowns[["Column", "Group By"] + [
                column for column in all_breakdowns.columns
                if column not in {"Column", "Group By"}
            ]]
        archive.writestr("Demographics.csv", all_breakdowns.to_csv(index=False))

    return archive_bytes.getvalue()
