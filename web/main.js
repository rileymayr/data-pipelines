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
    document.getElementById("chart-section").hidden = showNetwork;
    document.getElementById("network-section").hidden = !showNetwork;
    document.getElementById("tab-charts").classList.toggle("active", !showNetwork);
    document.getElementById("tab-network").classList.toggle("active", showNetwork);
}

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
