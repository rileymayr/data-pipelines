"""Browser-facing actions for the survey analysis page."""

import base64
import io
import re
import urllib.parse
import zipfile

import js

from analysis.data_utils import load_static_columns, process_all_surveys


combined_df = None


def _file(element_id):
    return js.document.getElementById(element_id).files.item(0)


async def get_combined_df():
    """Process the uploads once and reuse the result for all page actions."""
    global combined_df

    if combined_df is not None:
        return combined_df

    file1 = _file("csv1")
    file2 = _file("csv2")
    if not file1 or not file2:
        raise ValueError("Please select at least Baseline and Weekly CSV files.")

    combined_df = await process_all_surveys(
        file1,
        file2,
        _file("csv3"),
        static_cols_file=_file("csv-static"),
    )
    return combined_df


def _safe_filename(value):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_") or "field"


async def create_csv(event):
    js.set_status("Processing surveys with Pandas...", "loading")
    try:
        final_df = await get_combined_df()
        encoded_csv = urllib.parse.quote(final_df.to_csv(index=False))
        link = (
            f'<a href="data:text/csv;charset=utf-8,{encoded_csv}" '
            'download="processed_survey_data.csv" class="download-btn">'
            "Download Processed CSV</a>"
        )
        js.document.getElementById("download-container").innerHTML = link
        js.set_status("Combined CSV Generated!", "ready")
    except Exception as error:
        js.set_status(f"Error processing files: {error}", "error")


async def create_demographics_zip(event):
    js.set_status("Creating demographics ZIP...", "loading")
    try:
        final_df = await get_combined_df()
        requested = await load_static_columns(_file("csv-static"))
        demographic_cols = [column for column in requested if column in final_df.columns]
        export_cols = ["Name"] + [column for column in demographic_cols if column != "Name"]

        if len(export_cols) == 1:
            raise ValueError("No demographic columns were found in the combined dataframe.")

        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("demographics.csv", final_df[export_cols].to_csv(index=False))
            for column in demographic_cols:
                counts = (
                    final_df[column].fillna("Missing").astype(str).value_counts()
                    .rename_axis(column).reset_index(name="Count")
                )
                archive.writestr(
                    f"counts_by_{_safe_filename(column)}.csv",
                    counts.to_csv(index=False),
                )

        encoded = base64.b64encode(archive_bytes.getvalue()).decode("ascii")
        link = (
            '<a href="data:application/zip;base64,' + encoded + '" '
            'download="demographics_exports.zip" class="download-btn">'
            "Download Demographics ZIP</a>"
        )
        js.document.getElementById("download-container").innerHTML += link
        js.set_status("Demographics ZIP Generated!", "ready")
    except Exception as error:
        js.set_status(f"Error creating demographics ZIP: {error}", "error")


async def generate_report(event):
    js.set_status("Generating Analysis Report...", "loading")
    try:
        final_df = await get_combined_df()
        js.document.getElementById("report-container").innerHTML = f"""
            <h3>Summary Analysis</h3>
            <p>Total Unique Participants: <b>{len(final_df):,}</b></p>
            <p>Total Processed Columns: <b>{len(final_df.columns):,}</b></p>
        """
        js.set_status("Summary Report Generated!", "ready")
    except Exception as error:
        js.set_status(f"Error generating report: {error}", "error")
