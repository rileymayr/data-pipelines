import {
    clearAllCharts,
    deleteChart,
    downloadAllCharts,
    initializeChartMaker,
    setColumnOptions,
    setWeeklyColumnOptions,
    updateChartFields,
} from "./chart_maker.js";
import {downloadNetworkHtmlZip} from "./network_visualizer.js";
import {clearSession, loadSession} from "./session_cache.js";
import {restoreCharts} from "./chart_maker.js";

export function showAnalysisTab(tab) {
    const showNetwork = tab === "network";
    const showDemographics = tab === "demographics";
    document.getElementById("chart-section").hidden = showNetwork || showDemographics;
    document.getElementById("network-section").hidden = !showNetwork;
    document.getElementById("demographics-section").hidden = !showDemographics;
    document.getElementById("tab-charts").classList.toggle("active", !showNetwork && !showDemographics);
    document.getElementById("tab-network").classList.toggle("active", showNetwork);
    document.getElementById("tab-demographics").classList.toggle("active", showDemographics);
}

let demographicsColumns = [];
const selectedDemographics = new Set();
const selectedDemographicGroups = new Set();

function updateDemographicsSelectedCount() {
    const count = selectedDemographics.size;
    document.getElementById("demographics-selected-count").textContent =
        `${count} column${count === 1 ? "" : "s"} selected`;
}

function renderDemographicsColumns() {
    const query = document.getElementById("demographics-search").value.trim().toLowerCase();
    const container = document.getElementById("demographics-columns");
    container.innerHTML = "";
    demographicsColumns
        .filter((column) => !query || column.toLowerCase().includes(query))
        .forEach((column) => {
            const label = document.createElement("label");
            label.className = "checkbox-option";
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = column;
            checkbox.checked = selectedDemographics.has(column);
            checkbox.addEventListener("change", () => {
                if (checkbox.checked) selectedDemographics.add(column);
                else selectedDemographics.delete(column);
                updateDemographicsSelectedCount();
            });
            label.append(checkbox, document.createTextNode(column));
            container.appendChild(label);
        });
    updateDemographicsSelectedCount();
}

function updateDemographicsGroupCount() {
    const count = selectedDemographicGroups.size;
    document.getElementById("demographics-group-selected-count").textContent =
        `${count} grouping column${count === 1 ? "" : "s"} selected`;
}

function renderDemographicsGroupColumns() {
    const query = document.getElementById("demographics-group-search").value.trim().toLowerCase();
    const container = document.getElementById("demographics-group-columns");
    container.innerHTML = "";
    demographicsColumns
        .filter((column) => !query || column.toLowerCase().includes(query))
        .forEach((column) => {
            const label = document.createElement("label");
            label.className = "checkbox-option";
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = column;
            checkbox.checked = selectedDemographicGroups.has(column);
            checkbox.addEventListener("change", () => {
                if (checkbox.checked) selectedDemographicGroups.add(column);
                else selectedDemographicGroups.delete(column);
                updateDemographicsGroupCount();
            });
            label.append(checkbox, document.createTextNode(column));
            container.appendChild(label);
        });
    updateDemographicsGroupCount();
}

export function setDemographicsOptions(columns) {
    demographicsColumns = Array.from(columns || [], String);
    renderDemographicsColumns();
    renderDemographicsGroupColumns();
}

function getSelectedDemographics() {
    return Array.from(selectedDemographics);
}

function getSelectedDemographicGroups() {
    return Array.from(selectedDemographicGroups);
}

Object.assign(window, {
    get_selected_demographics: getSelectedDemographics,
    get_selected_demographic_groups: getSelectedDemographicGroups,
    set_demographics_options: setDemographicsOptions,
});

// Keep these names global for PyScript callbacks and the small inline HTML hooks.
Object.assign(window, {
    clear_all_charts: clearAllCharts,
    delete_chart: deleteChart,
    download_all_charts: downloadAllCharts,
    download_network_html_zip: downloadNetworkHtmlZip,
    set_column_options: setColumnOptions,
    set_weekly_column_options: setWeeklyColumnOptions,
    show_analysis_tab: showAnalysisTab,
    update_chart_fields: updateChartFields,
    clear_cached_session: async () => { await clearSession(); location.reload(); },
    download_text_file: (name, content) => {
        const blob = new Blob([content], {type: "text/csv;charset=utf-8"});
        const url = URL.createObjectURL(blob); const link = document.createElement("a");
        link.href = url; link.download = name; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
});

initializeChartMaker();
updateChartFields();
document.getElementById("demographics-search").addEventListener("input", renderDemographicsColumns);
document.getElementById("demographics-group-search").addEventListener("input", renderDemographicsGroupColumns);
loadSession().then(async session => {
    if (!session) return;
    document.getElementById("analysis-tabs").hidden = false;
    document.getElementById("chart-section").hidden = false;
    document.getElementById("combined-download-actions").hidden = false;
    if (session.charts) await restoreCharts(session.charts);
    if (session.network) {
        document.getElementById("network-section").hidden = false;
        document.getElementById("network-plot-container").innerHTML = '<div id="student-network-plot" class="network-plot-area"></div>';
        await Plotly.newPlot("student-network-plot", session.network.traces, session.network.layout, {responsive: true});
        await Plotly.addFrames("student-network-plot", session.network.frames || []);
        if (session.networkWeek) Plotly.animate("student-network-plot", `W${session.networkWeek}`, {mode: "immediate", transition: {duration: 0}});
    }
}).catch(() => {});
for (const id of ["csv1", "csv2", "csv3", "csv-static"]) {
    document.getElementById(id).addEventListener("change", () => clearSession().catch(() => {}));
}
window.addEventListener("beforeunload", () => {
    // The Python side writes the dataframe; chart/network modules write figures.
});
