"""Utilities for exporting demographic data and frequency tables."""

import io
import re
import zipfile

import pandas as pd


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_") or "field"


def create_demographics_zip(
    dataframe: pd.DataFrame,
    requested_columns: list[str],
) -> bytes:
    """Return a ZIP containing demographic rows and one count table per column."""

    demographic_columns = [
        column for column in requested_columns if column in dataframe.columns
    ]
    export_columns = ["Name"] + [
        column for column in demographic_columns if column != "Name"
    ]

    if len(export_columns) == 1:
        raise ValueError("No demographic columns were found in the combined dataframe.")

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "demographics.csv",
            dataframe[export_columns].to_csv(index=False),
        )
        for column in demographic_columns:
            counts = (
                dataframe[column]
                .fillna("Missing")
                .astype(str)
                .value_counts()
                .rename_axis(column)
                .reset_index(name="Count")
            )
            archive.writestr(
                f"counts_by_{_safe_filename(column)}.csv",
                counts.to_csv(index=False),
            )

    return archive_bytes.getvalue()
