import {setStatus} from "./status.js";

export async function downloadNetworkHtmlZip(figures) {
    try {
        const zip = new JSZip();
        const usedNames = new Set();
        const entries = Object.entries(figures);
        for (const [classNumber, figure] of entries) {
            const baseName = `student-network-class-${String(classNumber)}`
                .replace(/[<>:"/\\|?*]+/g, "-").replace(/\s+/g, "-");
            let fileName = `${baseName}.html`;
            let copyNumber = 2;
            while (usedNames.has(fileName.toLowerCase())) fileName = `${baseName}-${copyNumber++}.html`;
            usedNames.add(fileName.toLowerCase());

            const dataJson = JSON.stringify(figure.traces).replace(/</g, "\\u003c");
            const layoutJson = JSON.stringify(figure.layout).replace(/</g, "\\u003c");
            const framesJson = JSON.stringify(figure.frames).replace(/</g, "\\u003c");
            const html = [
                "<!doctype html>", "<html lang=\"en\"><head>", "<meta charset=\"utf-8\">",
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
                `<title>${baseName}</title>`,
                "<scr" + "ipt src=\"https://cdn.plot.ly/plotly-2.35.2.min.js\"></scr" + "ipt>",
                "</head><body>", "<div id=\"plot\" style=\"width:100%;height:95vh;\"></div>",
                "<scr" + "ipt>", `const data = ${dataJson};`, `const layout = ${layoutJson};`,
                `const frames = ${framesJson};`,
                "Plotly.newPlot(\"plot\", data, layout, {responsive: true}).then(() => Plotly.addFrames(\"plot\", frames));",
                "<" + "/script>", "</body></html>"
            ].join("\n");
            zip.file(fileName, html);
        }
        const blob = await zip.generateAsync({type: "blob"});
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "student_networks_by_class.zip";
        link.click();
        URL.revokeObjectURL(link.href);
        setStatus(`Downloaded ${entries.length} class network HTML file(s).`, "ready");
    } catch (error) {
        setStatus(`Error downloading network HTMLs: ${error}`, "error");
    }
}

window.download_network_html_zip = downloadNetworkHtmlZip;
