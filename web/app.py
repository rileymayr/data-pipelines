"""Browser-facing actions for the survey analysis page."""

import base64
import html
import json
import urllib.parse

import js

from analysis.chart_utils import build_plot, get_column_names
from analysis.data_utils import load_static_columns, process_all_surveys
from analysis.demographics import create_demographics_zip as build_demographics_zip


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
    _show_columns(combined_df)
    return combined_df


def _show_columns(dataframe):
    """Populate the visible column list and chart selector after processing."""

    columns = get_column_names(dataframe)
    items = "".join(
        "<li data-column=\"{0}\">"
        '<label><input type="checkbox" name="chart-column" value="{0}"> {1}</label>'
        "</li>".format(
            html.escape(column, quote=True),
            html.escape(column),
        )
        for column in columns
    )
    js.document.getElementById("column-list").innerHTML = items
    js.document.getElementById("chart-section").hidden = False


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
        encoded = base64.b64encode(
            build_demographics_zip(final_df, requested)
        ).decode("ascii")
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


async def create_selected_plots(event):
    """Render Plotly charts for the checked columns and selected plot type."""

    try:
        final_df = await get_combined_df()
        checkboxes = js.document.querySelectorAll(
            '#column-list input[name="chart-column"]:checked'
        )
        selected_columns = [
            str(checkboxes.item(index).value)
            for index in range(checkboxes.length)
        ]
        plot_type = str(js.document.getElementById("plot-type").value)
        plot = build_plot(final_df, plot_type, selected_columns)
        traces = plot.get("traces", [plot["trace"]])

        plot_container = js.document.getElementById("plot-container")
        plot_container.innerHTML = "".join(
            f'<div id="plot-{index}" class="plot-card"></div>'
            for index in range(len(traces))
        )
        config = js.JSON.parse(json.dumps({"responsive": True}))
        for index, trace in enumerate(traces):
            # Plotly.js needs native JavaScript objects, not Python dict proxies.
            data = js.JSON.parse(json.dumps([trace]))
            layout = js.JSON.parse(json.dumps(plot["layout"]))
            js.Plotly.newPlot(f"plot-{index}", data, layout, config)

        js.set_status(f"Created {len(traces)} {plot_type} chart(s).", "ready")
    except Exception as error:
        js.set_status(f"Error creating bar chart: {error}", "error")
