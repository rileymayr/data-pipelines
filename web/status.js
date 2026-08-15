export function setStatus(message, kind) {
    const status = document.getElementById("output-status");
    if (!status) return;
    status.innerText = message;
    status.className = "status " + kind;
}

// Python callbacks access this through the PyScript ``js`` module.
window.set_status = setStatus;

window.addEventListener("py:ready", () => {
    setStatus("Status: Ready to Process", "ready");
});
