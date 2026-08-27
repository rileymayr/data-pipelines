"""Browser-facing actions for the survey analysis page."""

import base64
import html
import json
import urllib.parse
import io

import js
import pandas as pd

from analysis.chart_utils import build_plot, get_column_names, get_weekly_column_names
from analysis.data_utils import (
    build_long_dataframe,
    build_student_network,
    process_all_surveys,
)
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

    cached = await js.window.session_cache.load_dataframe()
    if cached:
        cached = cached.to_py() if hasattr(cached, "to_py") else str(cached)
        combined_df = pd.read_csv(io.StringIO(cached))
        _show_columns(combined_df)
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
    long_csv = build_long_dataframe(combined_df).to_csv(index=False)
    await js.window.session_cache.save_dataframe(
        combined_df.to_csv(index=False),
        js.JSON.parse(json.dumps({
            "longCsv": long_csv,
            "columns": get_column_names(combined_df),
            "weeklyColumns": get_weekly_column_names(combined_df),
            "classOptions": sorted(
                combined_df.get("Class Number", pd.Series(dtype=object))
                .dropna().astype(str).str.replace(r"\.0$", "", regex=True).unique()
            ),
        })),
    )
    _show_columns(combined_df)
    return combined_df


def _show_columns(dataframe):
    """Populate the searchable column suggestions after processing."""

    columns = get_column_names(dataframe)
    js.set_column_options(js.JSON.parse(json.dumps(columns)))
    js.set_weekly_column_options(
        js.JSON.parse(json.dumps(get_weekly_column_names(dataframe)))
    )
    js.set_demographics_options(js.JSON.parse(json.dumps(columns)))
    js.document.getElementById("column-count").innerText = str(len(columns))
    js.document.getElementById("chart-section").hidden = False
    class_options = sorted(
        dataframe.get("Class Number", pd.Series(dtype=object))
        .dropna().astype(str).str.replace(r"\.0$", "", regex=True).unique()
    )
    js.document.getElementById("network-classes").innerHTML = "".join(
        f'<option value="{html.escape(value, quote=True)}" selected>{html.escape(value)}</option>'
        for value in class_options
    )
    js.document.getElementById("analysis-tabs").hidden = False
    js.document.getElementById("network-section").hidden = False
    js.document.getElementById("demographics-section").hidden = False
    js.show_analysis_tab("charts")
    js.document.getElementById("upload-details").open = False


async def create_csv(event):
    js.set_status("Processing surveys with Pandas...", "loading")
    try:
        final_df = await get_combined_df()
        wide_csv = final_df.to_csv(index=False)
        long_csv = build_long_dataframe(final_df).to_csv(index=False)
        links = (
            '<button type="button" class="download-btn" '
            'onclick="download_text_file(\'processed_survey_data.csv\', this.dataset.content)" '
            f'data-content="{html.escape(wide_csv, quote=True)}">'
            "Download Combined Dataframe</button>"
            '<button type="button" class="download-btn" '
            'onclick="download_text_file(\'long_format_data.csv\', this.dataset.content)" '
            f'data-content="{html.escape(long_csv, quote=True)}">'
            "Download Long Format Data</button>"
        )
        js.document.getElementById("download-container").innerHTML = links
        js.document.getElementById("combined-download-actions").hidden = False
        js.set_status("Combined and long-format CSVs generated!", "ready")
    except Exception as error:
        js.set_status(f"Error processing files: {error}", "error")


async def download_demographics_zip(event):
    js.set_status("Creating demographic breakdown ZIP...", "loading")
    try:
        final_df = await get_combined_df()
        requested = [str(column) for column in js.get_selected_demographics()]
        group_by = [str(column) for column in js.get_selected_demographic_groups()]
        encoded = base64.b64encode(
            build_demographics_zip(final_df, requested, group_by)
        ).decode("ascii")
        link = js.document.createElement("a")
        link.href = "data:application/zip;base64," + encoded
        link.download = "demographics_breakdowns.zip"
        link.click()
        js.set_status("Demographics breakdown ZIP downloaded!", "ready")
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
        facet_column = str(js.document.getElementById("chart-facet-column").value).strip()
        facet_row = str(js.document.getElementById("chart-facet-row").value).strip()
        share_y = bool(js.document.getElementById("chart-share-y").checked)
        share_x = bool(js.document.getElementById("chart-share-x").checked)
        title = str(js.document.getElementById("chart-title").value).strip()
        aggregation = str(js.document.getElementById("chart-aggregation").value)
        bin_mode = str(js.document.getElementById("chart-bin-mode").value)
        bin_width_value = str(js.document.getElementById("chart-bin-width").value).strip()
        bin_count_value = str(js.document.getElementById("chart-bin-count").value).strip()
        if bin_mode != "width":
            bin_width_value = ""
        if bin_mode != "count":
            bin_count_value = ""
        bin_width = float(bin_width_value) if bin_width_value else None
        bin_count = float(bin_count_value) if bin_count_value else None
        plot = build_plot(
            final_df, plot_type, x_column, y_column, color_column, title,
            aggregation=aggregation,
            bin_width=bin_width,
            bin_count=bin_count,
            facet_row=facet_row,
            facet_column=facet_column,
            share_y=share_y,
            share_x=share_x,
        )
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
        await js.window.persist_chart_state()

        js.set_status(f"Added {plot_type} chart.", "ready")
    except Exception as error:
        js.set_status(f"Error creating chart: {error}", "error")


def _network_plot(network):
    """Create stable force-directed positions, Plotly traces, and week frames."""
    import math

    nodes = network["nodes"]
    positions = {}
    node_ids = [node["id"] for node in nodes]
    count = max(1, len(nodes))

    # Aggregate all weeks for the layout so the graph represents the overall
    # structure while the displayed edges can still change with the slider.
    layout_edges = {}
    for week_edges in network["edges_by_week"].values():
        for edge in week_edges:
            key = tuple(sorted((edge["source"], edge["target"])))
            layout_edges[key] = layout_edges.get(key, 0) + edge["strength"]

    # Small deterministic force-directed layout. This avoids an additional
    # browser package while producing readable clusters for the survey-sized
    # networks this app handles.
    radius = max(1.0, math.sqrt(count) * 1.5)
    for index, node in enumerate(nodes):
        angle = (2 * math.pi * index / count) - math.pi / 2
        positions[node["id"]] = (radius * math.cos(angle), radius * math.sin(angle))

    area = max(25.0, count * 8.0)
    ideal_distance = math.sqrt(area / count)
    for _ in range(140):
        displacement = {node_id: [0.0, 0.0] for node_id in node_ids}
        for left_index, left_id in enumerate(node_ids):
            left_x, left_y = positions[left_id]
            for right_id in node_ids[left_index + 1:]:
                right_x, right_y = positions[right_id]
                dx, dy = left_x - right_x, left_y - right_y
                distance = max(0.05, math.hypot(dx, dy))
                force = (ideal_distance * ideal_distance) / distance
                push_x, push_y = dx / distance * force, dy / distance * force
                displacement[left_id][0] += push_x
                displacement[left_id][1] += push_y
                displacement[right_id][0] -= push_x
                displacement[right_id][1] -= push_y

        for (source, target), strength in layout_edges.items():
            source_x, source_y = positions[source]
            target_x, target_y = positions[target]
            dx, dy = target_x - source_x, target_y - source_y
            distance = max(0.05, math.hypot(dx, dy))
            force = (distance * distance / ideal_distance) * (0.015 + min(strength, 8) * 0.004)
            pull_x, pull_y = dx / distance * force, dy / distance * force
            displacement[source][0] += pull_x
            displacement[source][1] += pull_y
            displacement[target][0] -= pull_x
            displacement[target][1] -= pull_y

        for node_id in node_ids:
            x, y = positions[node_id]
            # Keep the whole layout centered and prevent extreme outliers.
            displacement[node_id][0] -= x * 0.004
            displacement[node_id][1] -= y * 0.004
            step_x, step_y = displacement[node_id]
            step = max(0.05, math.hypot(step_x, step_y))
            limit = 0.28
            positions[node_id] = (
                x + step_x / step * min(step, limit),
                y + step_y / step * min(step, limit),
            )

    # Normalize coordinates for a consistent Plotly viewport.
    max_coordinate = max(
        (max(abs(x), abs(y)) for x, y in positions.values()), default=1.0
    )
    scale = 10.0 / max(1.0, max_coordinate)
    positions = {
        node_id: (x * scale, y * scale)
        for node_id, (x, y) in positions.items()
    }

    classes = sorted({node["class_number"] for node in nodes})
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    class_colors = {value: palette[index % len(palette)] for index, value in enumerate(classes)}
    node_trace = {
        "type": "scatter",
        "mode": "markers+text",
        "x": [positions[node["id"]][0] for node in nodes],
        "y": [positions[node["id"]][1] for node in nodes],
        "text": [node["label"] for node in nodes],
        "textposition": "top center",
        "textfont": {"size": 10},
        "hovertemplate": "%{text}<br>Class: %{customdata}<extra></extra>",
        "customdata": [node["class_number"] for node in nodes],
        "marker": {
            "size": 14,
            "color": [class_colors[node["class_number"]] for node in nodes],
            "line": {"width": 1, "color": "white"},
        },
        "name": "Students",
    }

    all_edge_keys = sorted({
        (edge["source"], edge["target"], edge["group_number"])
        for edges in network["edges_by_week"].values()
        for edge in edges
    }, key=lambda key: (key[0].casefold(), key[1].casefold(), key[2]))
    parallel_pairs = {
        (source, target)
        for source, target, _group_number in all_edge_keys
        if sum(
            1 for edge_source, edge_target, _ in all_edge_keys
            if edge_source == source and edge_target == target
        ) > 1
    }

    def edge_traces(week):
        week_lookup = {
            (edge["source"], edge["target"], edge["group_number"]): edge
            for edge in network["edges_by_week"].get(str(week), [])
        }
        traces = []
        for source, target, group_number in all_edge_keys:
            edge_data = week_lookup.get((source, target, group_number))
            offset = 0.12 if (source, target) in parallel_pairs else 0.0
            if group_number == 1:
                offset = -offset
            source_x, source_y = positions[source]
            target_x, target_y = positions[target]
            dx, dy = target_x - source_x, target_y - source_y
            distance = max(0.05, math.hypot(dx, dy))
            offset_x, offset_y = -dy / distance * offset, dx / distance * offset
            displayed_group = (
                str(edge_data.get("group_number", group_number)).strip()
                if edge_data else str(group_number)
            )
            traces.append({
                "type": "scatter", "mode": "lines",
                "x": [source_x + offset_x, target_x + offset_x, None] if edge_data else [],
                "y": [source_y + offset_y, target_y + offset_y, None] if edge_data else [],
                "line": {
                    "width": min(1 + (edge_data["strength"] if edge_data else 0) * 1.5, 12),
                    "dash": "dash" if displayed_group == "2" else "solid",
                    "color": "#777",
                },
                "hoverinfo": "skip",
                "name": f"Group {group_number}",
            })
        return traces

    weeks = sorted(int(week) for week in network["edges_by_week"])
    traces = edge_traces(weeks[0]) + [node_trace] if weeks else [node_trace]
    frames = [
        {"name": f"W{week}", "data": edge_traces(week) + [node_trace]}
        for week in weeks
    ]
    slider_steps = [
        {"label": f"Week {week}", "method": "animate", "args": [[f"W{week}"], {"mode": "immediate"}]}
        for week in weeks
    ]
    layout = {
        "title": "Student Study-Group Network",
        "showlegend": False,
        "hovermode": "closest",
        "xaxis": {"visible": False}, "yaxis": {"visible": False},
        "margin": {"l": 20, "r": 20, "t": 70, "b": 70},
        "plot_bgcolor": "#fafafa",
        "updatemenus": [{"type": "buttons", "showactive": False, "x": 0, "y": 1.12,
                         "buttons": [{"label": "Play weeks", "method": "animate",
                                      "args": [None, {"fromcurrent": True, "frame": {"duration": 900}}]}]}],
        "sliders": [{"active": 0, "currentvalue": {"prefix": "Displayed: "}, "steps": slider_steps}],
    }
    return {"traces": traces, "frames": frames, "layout": layout}


async def create_network_graph(event):
    """Render the weekly undirected study-group network and offer its edge list."""
    try:
        final_df = await get_combined_df()
        week = int(js.document.getElementById("network-week").value)
        class_select = js.document.getElementById("network-classes")
        classes = [str(option.value) for option in class_select.options if option.selected]
        network = build_student_network(final_df, weeks=[1, 2, 3], class_numbers=classes)
        plot = _network_plot(network)
        plot_id = "student-network-plot"
        js.document.getElementById("network-plot-container").innerHTML = (
            f'<div id="{plot_id}" class="network-plot-area"></div>'
        )
        js.Plotly.newPlot(
            plot_id,
            js.JSON.parse(json.dumps(plot["traces"])),
            js.JSON.parse(json.dumps(plot["layout"])),
            js.JSON.parse(json.dumps({"responsive": True})),
        )
        js.Plotly.addFrames(plot_id, js.JSON.parse(json.dumps(plot["frames"])))
        js.Plotly.animate(plot_id, f"W{week}", {"mode": "immediate", "transition": {"duration": 0}})
        await js.window.session_cache.save_session(js.JSON.parse(json.dumps({
            "network": plot, "networkWeek": week, "networkClasses": classes
        })))

        js.set_status("Student network generated.", "ready")
    except Exception as error:
        js.set_status(f"Error creating student network: {error}", "error")


async def download_network_csv(event):
    """Download the network edge list using the current class selection."""
    try:
        final_df = await get_combined_df()
        class_select = js.document.getElementById("network-classes")
        classes = [str(option.value) for option in class_select.options if option.selected]
        network = build_student_network(final_df, weeks=[1, 2, 3], class_numbers=classes)
        csv_text = (
            pd.DataFrame(network["edges"]).to_csv(index=False)
            if network["edges"] else
            "week,source_class,target_class,source,target,strength,group_number,group_2\n"
        )
        encoded_csv = urllib.parse.quote(csv_text)
        link = js.document.createElement("a")
        link.href = f"data:text/csv;charset=utf-8,{encoded_csv}"
        link.download = "student_network_edges.csv"
        link.click()
        js.set_status("Network CSV downloaded.", "ready")
    except Exception as error:
        js.set_status(f"Error downloading network CSV: {error}", "error")


async def download_network_htmls(event):
    """Prepare one interactive Plotly HTML figure per class for ZIP download."""
    try:
        final_df = await get_combined_df()
        all_network = build_student_network(final_df, weeks=[1, 2, 3])
        figures = {}
        for class_number in all_network["class_numbers"]:
            class_network = build_student_network(
                final_df, weeks=[1, 2, 3], class_numbers=[class_number]
            )
            figures[str(class_number)] = _network_plot(class_network)

        js.window.download_network_html_zip(
            js.JSON.parse(json.dumps(figures))
        )
        js.set_status(
            f"Prepared {len(figures)} class network HTML file(s).", "ready"
        )
    except Exception as error:
        js.set_status(f"Error preparing network HTMLs: {error}", "error")
