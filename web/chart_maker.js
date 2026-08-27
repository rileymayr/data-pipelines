import {setStatus} from "./status.js";
import {saveSession} from "./session_cache.js";

const chartColumnInputs = ["chart-x", "chart-y", "chart-color", "chart-facet-column", "chart-facet-row"];
let chartColumns = [];
let weeklyColumns = [];

export function updateChartFields() {
    const chartType = document.getElementById("plot-type").value;
    const xField = document.getElementById("x-field");
    const yLabel = document.querySelector("#y-field > .field-label");
    document.getElementById("y-field").hidden = chartType === "histogram" || chartType === "line";
    xField.hidden = false;
    document.getElementById("aggregation-field").hidden = chartType !== "bar" && chartType !== "line";
    document.getElementById("histogram-bins-field").hidden = chartType !== "histogram";
    if (yLabel) yLabel.textContent = "Y-axis";
    const xLabel = document.querySelector("#x-field > .field-label");
    if (xLabel) xLabel.textContent = chartType === "line" ? "Weekly measure" : "X-axis";
}

function updateHistogramBinMode() {
    const mode = document.getElementById("chart-bin-mode")?.value;
    document.getElementById("chart-bin-count").hidden = mode !== "count";
    document.getElementById("chart-bin-width").hidden = mode !== "width";
}

function renderColumnOptions(input, showAll = false) {
    const options = document.getElementById(input.getAttribute("aria-controls"));
    if (!options) return;
    const query = input.value.trim().toLowerCase();
    const sourceColumns = document.getElementById("plot-type").value === "line"
        && input.id === "chart-x" ? weeklyColumns : chartColumns;
    const matches = sourceColumns.filter((column) =>
        showAll || !query || column.toLowerCase().includes(query)
    );
    options.innerHTML = "";
    if (!matches.length) {
        options.innerHTML = '<div class="combobox-empty">No matching columns</div>';
        return;
    }
    matches.forEach((column) => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "combobox-option";
        option.setAttribute("role", "option");
        option.textContent = weeklyColumns.includes(column) ? `${column} (Weekly)` : column;
        option.addEventListener("mousedown", (event) => event.preventDefault());
        option.addEventListener("click", () => {
            input.value = column;
            closeColumnOptions(input);
        });
        options.appendChild(option);
    });
}

function openColumnOptions(input, showAll = false) {
    renderColumnOptions(input, showAll);
    const options = document.getElementById(input.getAttribute("aria-controls"));
    options.hidden = false;
    input.setAttribute("aria-expanded", "true");
}

function closeColumnOptions(input) {
    const options = document.getElementById(input.getAttribute("aria-controls"));
    if (options) options.hidden = true;
    input.setAttribute("aria-expanded", "false");
}

// Called from Python after the processed dataframe supplies its columns.
export function setColumnOptions(columns) {
    chartColumns = Array.from(columns || [], String);
    chartColumnInputs.forEach((id) => {
        const input = document.getElementById(id);
        if (input && input.getAttribute("aria-expanded") === "true") {
            openColumnOptions(input);
        }
    });
}

export function setWeeklyColumnOptions(columns) {
    weeklyColumns = Array.from(columns || [], String);
}

export function initializeChartMaker() {
    document.getElementById("chart-bin-mode")
        .addEventListener("change", updateHistogramBinMode);
    updateHistogramBinMode();
    chartColumnInputs.forEach((id) => {
        const input = document.getElementById(id);
        const toggle = input.closest(".combobox").querySelector(".combobox-toggle");
        input.addEventListener("input", () => openColumnOptions(input));
        input.addEventListener("focus", () => openColumnOptions(input));
        input.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeColumnOptions(input);
            if (event.key === "ArrowDown") {
                event.preventDefault();
                openColumnOptions(input);
                const firstOption = document.getElementById(input.getAttribute("aria-controls"))
                    .querySelector(".combobox-option");
                if (firstOption) firstOption.focus();
            }
        });
        toggle.addEventListener("click", () => {
            input.value = "";
            input.focus();
            openColumnOptions(input, true);
        });
    });
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".combobox")) {
            chartColumnInputs.forEach((id) => closeColumnOptions(document.getElementById(id)));
        }
    });
}

export function deleteChart(plotId, cardId) {
    if (window.Plotly) window.Plotly.purge(plotId);
    const card = document.getElementById(cardId);
    if (card) card.remove();
    persistCharts();
}

export function clearAllCharts() {
    document.querySelectorAll("#plot-container .plot-area").forEach((plot) => {
        if (window.Plotly) window.Plotly.purge(plot);
    });
    document.getElementById("plot-container").innerHTML = "";
    persistCharts();
}

export function getChartState() {
    return Array.from(document.querySelectorAll("#plot-container .plot-area")).map(plot => ({
        data: plot.data, layout: plot.layout,
        title: plot.parentElement?.dataset.chartTitle || ""
    }));
}

export async function restoreCharts(charts) {
    clearAllCharts();
    for (const [index, chart] of (charts || []).entries()) {
        const id = `restored-plot-${index}`;
        const cardId = `restored-chart-card-${index}`;
        const section = document.createElement("section");
        section.id = cardId; section.className = "plot-card";
        section.dataset.chartTitle = chart.title || "";
        const toolbar = document.createElement("div"); toolbar.className = "chart-toolbar";
        const deleteButton = document.createElement("button");
        deleteButton.type = "button"; deleteButton.className = "btn btn-small";
        deleteButton.textContent = "Delete This Chart";
        deleteButton.addEventListener("click", () => deleteChart(id, cardId));
        toolbar.append(deleteButton);
        const area = document.createElement("div"); area.id = id; area.className = "plot-area";
        section.append(toolbar, area); document.getElementById("plot-container").append(section);
        await Plotly.newPlot(id, chart.data, chart.layout, {responsive: true});
    }
}

async function persistCharts() {
    const old = await window.session_cache?.load_session();
    if (old) { old.charts = getChartState(); await saveSession(old); }
}
window.persist_chart_state = persistCharts;

export async function downloadAllCharts() {
    const plots = Array.from(document.querySelectorAll("#plot-container .plot-area"));
    if (!plots.length) {
        setStatus("There are no charts to download.", "error");
        return;
    }

    try {
        const zip = new JSZip();
        const usedNames = new Set();
        for (let index = 0; index < plots.length; index++) {
            const plot = plots[index];
            let title = plot.parentElement && plot.parentElement.dataset.chartTitle;
            if (!title) title = plot.layout && plot.layout.title;
            if (title && typeof title === "object") title = title.text;
            let baseName = String(title || `chart-${index + 1}`)
                .trim().replace(/[<>:"/\\|?*]+/g, "-").replace(/\s+/g, "-")
                .replace(/-+/g, "-").replace(/^-|-$/g, "").slice(0, 100)
                || `chart-${index + 1}`;
            const firstTraceType = plot.data && plot.data[0] && plot.data[0].type;
            const figureType = firstTraceType === "scatter" ? "scatterplot" : (firstTraceType || "chart");
            let fileName = `${baseName}-${figureType}`;
            let copyNumber = 2;
            while (usedNames.has(fileName.toLowerCase())) fileName = `${baseName}-${figureType}-${copyNumber++}`;
            usedNames.add(fileName.toLowerCase());

            const image = await Plotly.toImage(plot, {format: "png", width: 1200, height: 700, scale: 2});
            zip.file(`${fileName}.png`, image.split(",")[1], {base64: true});
            const dataJson = JSON.stringify(plot.data).replace(/</g, "\\u003c");
            const layoutJson = JSON.stringify(plot.layout).replace(/</g, "\\u003c");
            const html = [
                "<!doctype html>", "<html lang=\"en\"><head>", "<meta charset=\"utf-8\">",
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
                `<title>${fileName}</title>`,
                "<scr" + "ipt src=\"https://cdn.plot.ly/plotly-2.35.2.min.js\"></scr" + "ipt>",
                "</head><body>", "<div id=\"plot\" style=\"width:100%;height:95vh;\"></div>",
                "<scr" + "ipt>", `const data = ${dataJson};`, `const layout = ${layoutJson};`,
                "Plotly.newPlot(\"plot\", data, layout, {responsive: true});", "<" + "/script>",
                "</body></html>"
            ].join("\n");
            zip.file(`${fileName}.html`, html);
        }
        const blob = await zip.generateAsync({type: "blob"});
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "charts.zip";
        link.click();
        URL.revokeObjectURL(link.href);
        setStatus(`Downloaded ${plots.length} chart(s).`, "ready");
    } catch (error) {
        setStatus(`Error downloading charts: ${error}`, "error");
    }
}
