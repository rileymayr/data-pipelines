"""Utilities for exporting grouped demographic summaries."""

import io
import re
import zipfile

import pandas as pd


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_") or "field"


def _as_group_values(series: pd.Series) -> pd.Series:
    """Use stable, readable values in summaries, including missing values."""

    return series.fillna("Missing").astype(str)


def _breakdown(dataframe: pd.DataFrame, column: str, group_by: str | None) -> pd.DataFrame:
    values = _as_group_values(dataframe[column])
    if not group_by:
        counts = values.value_counts(dropna=False).rename("Count").rename_axis("Value").reset_index()
        counts["Percent"] = counts["Count"] / counts["Count"].sum() * 100
        return counts[["Value", "Count", "Percent"]]

    groups = _as_group_values(dataframe[group_by])
    counts = (
        pd.DataFrame({"Group": groups, "Value": values})
        .groupby(["Group", "Value"], dropna=False)
        .size()
        .rename("Count")
        .reset_index()
    )
    counts["Group Total"] = counts.groupby("Group")["Count"].transform("sum")
    counts["Percent"] = counts["Count"] / counts["Group Total"] * 100
    return counts[["Group", "Value", "Count", "Percent", "Group Total"]]


def create_demographics_zip(
    dataframe: pd.DataFrame,
    requested_columns: list[str],
    group_by: str | None = None,
) -> bytes:
    """Return per-column demographic breakdowns and one combined long-format CSV."""

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
            breakdown = _breakdown(dataframe, column, group_by)
            if group_by:
                filename = f"{_safe_filename(column)}_grouped-by_{_safe_filename(group_by)}.csv"
                combined_part = breakdown.assign(Column=column, **{"Group By": group_by})
            else:
                filename = f"{_safe_filename(column)}.csv"
                combined_part = breakdown.assign(Column=column, **{"Group By": ""})
            archive.writestr(filename, breakdown.to_csv(index=False))
            combined.append(combined_part)

        combined_columns = ["Column", "Group By"]
        if group_by:
            combined_columns += ["Group", "Value", "Count", "Percent", "Group Total"]
        else:
            combined_columns += ["Value", "Count", "Percent"]
        all_breakdowns = pd.concat(combined, ignore_index=True)[combined_columns]
        archive.writestr("all_breakdowns.csv", all_breakdowns.to_csv(index=False))

    return archive_bytes.getvalue()
