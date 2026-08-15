import {setStatus} from "./status.js";

const chartColumnInputs = ["chart-x", "chart-y", "chart-color"];
let chartColumns = [];

export function updateChartFields() {
    const chartType = document.getElementById("plot-type").value;
    document.getElementById("y-field").hidden = chartType === "histogram";
}

function renderColumnOptions(input, showAll = false) {
    const options = document.getElementById(input.getAttribute("aria-controls"));
    if (!options) return;
    const query = input.value.trim().toLowerCase();
    const matches = chartColumns.filter((column) =>
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
        option.textContent = column;
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

export function initializeChartMaker() {
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
}

export function clearAllCharts() {
    document.querySelectorAll("#plot-container .plot-area").forEach((plot) => {
        if (window.Plotly) window.Plotly.purge(plot);
    });
    document.getElementById("plot-container").innerHTML = "";
}

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
