let hideTimer;
const STATUS_TIMEOUT_MS = 10000;

export function setStatus(message, kind) {
    const status = document.getElementById("output-status");
    if (!status) return;
    clearTimeout(hideTimer);
    status.innerText = message;
    status.className = "status " + kind;
    hideTimer = setTimeout(() => {
        status.classList.add("status-hidden");
    }, STATUS_TIMEOUT_MS);
}

// Python callbacks access this through the PyScript ``js`` module.
window.set_status = setStatus;

window.addEventListener("py:ready", () => {
    setStatus("Status: Ready to Process", "ready");
});
