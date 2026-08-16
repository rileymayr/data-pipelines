import {
    clearAllCharts,
    deleteChart,
    downloadAllCharts,
    initializeChartMaker,
    setColumnOptions,
    updateChartFields,
} from "./chart_maker.js";
import {downloadNetworkHtmlZip} from "./network_visualizer.js";

export function showAnalysisTab(tab) {
    const showNetwork = tab === "network";
    const showDemographics = tab === "demographics";
    document.getElementById("chart-section").hidden = showNetwork || showDemographics;
    document.getElementById("network-section").hidden = showNetwork || showDemographics;
    document.getElementById("demographics-section").hidden = !showDemographics;
    document.getElementById("tab-charts").classList.toggle("active", !showNetwork && !showDemographics);
    document.getElementById("tab-network").classList.toggle("active", showNetwork);
    document.getElementById("tab-demographics").classList.toggle("active", showDemographics);
}

let demographicsColumns = [];
const selectedDemographics = new Set();

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

export function setDemographicsOptions(columns) {
    demographicsColumns = Array.from(columns || [], String);
    const groupBy = document.getElementById("demographics-group-by");
    groupBy.innerHTML = '<option value="">No grouping</option>';
    demographicsColumns.forEach((column) => {
        const option = document.createElement("option");
        option.value = column;
        option.textContent = column;
        groupBy.appendChild(option);
    });
    renderDemographicsColumns();
}

function getSelectedDemographics() {
    return Array.from(selectedDemographics);
}

Object.assign(window, {
    get_selected_demographics: getSelectedDemographics,
    set_demographics_options: setDemographicsOptions,
});

// Keep these names global for PyScript callbacks and the small inline HTML hooks.
Object.assign(window, {
    clear_all_charts: clearAllCharts,
    delete_chart: deleteChart,
    download_all_charts: downloadAllCharts,
    download_network_html_zip: downloadNetworkHtmlZip,
    set_column_options: setColumnOptions,
    show_analysis_tab: showAnalysisTab,
    update_chart_fields: updateChartFields,
});

initializeChartMaker();
updateChartFields();
document.getElementById("demographics-search").addEventListener("input", renderDemographicsColumns);
