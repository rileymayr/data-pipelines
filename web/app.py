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
chart_counter = 0


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
    """Populate the searchable column suggestions after processing."""

    columns = get_column_names(dataframe)
    options = "".join(
        f'<option value="{html.escape(column, quote=True)}"></option>'
        for column in columns
    )
    js.document.getElementById("column-options").innerHTML = options
    js.document.getElementById("column-count").innerText = str(len(columns))
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


async def create_chart(event):
    """Add one configured Plotly chart to the top of the chart stack."""
    global chart_counter

    try:
        final_df = await get_combined_df()
        plot_type = str(js.document.getElementById("plot-type").value)
        x_column = str(js.document.getElementById("chart-x").value).strip()
        y_column = str(js.document.getElementById("chart-y").value).strip()
        color_column = str(js.document.getElementById("chart-color").value).strip()
        title = str(js.document.getElementById("chart-title").value).strip()
        plot = build_plot(final_df, plot_type, x_column, y_column, color_column, title)
        traces = plot["traces"]

        plot_container = js.document.getElementById("plot-container")
        chart_number = chart_counter
        chart_counter += 1
        plot_id = f"plot-{chart_number}"
        card_id = f"chart-card-{chart_number}"
        chart_title = html.escape(str(plot["layout"]["title"]), quote=True)
        plot_container.insertAdjacentHTML(
            "afterbegin",
            f'<section id="{card_id}" class="plot-card" data-chart-title="{chart_title}">'
            f'<div class="chart-toolbar">'
            f'<button type="button" class="btn btn-small" '
            f'onclick="delete_chart(\'{plot_id}\', \'{card_id}\')">'
            "Delete chart</button></div>"
            f'<div id="{plot_id}" class="plot-area"></div></section>',
        )
        config = js.JSON.parse(json.dumps({"responsive": True}))
        # Plotly.js needs native JavaScript objects, not Python dict proxies.
        data = js.JSON.parse(json.dumps(traces))
        layout = js.JSON.parse(json.dumps(plot["layout"]))
        js.Plotly.newPlot(plot_id, data, layout, config)

        js.set_status(f"Added {plot_type} chart.", "ready")
    except Exception as error:
        js.set_status(f"Error creating chart: {error}", "error")
