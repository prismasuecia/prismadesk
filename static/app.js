const updateButton = document.querySelector("[data-update-button]");

if (updateButton) {
  updateButton.closest("form").addEventListener("submit", () => {
    updateButton.disabled = true;
    updateButton.textContent = "STARTAR...";
  });
}

const runStatusPanel = document.querySelector("[data-run-status-panel]");

if (runStatusPanel) {
  const statusUrl = runStatusPanel.dataset.runStatusUrl;
  const statusText = document.querySelector("[data-run-status-text]");
  const statusDetail = document.querySelector("[data-run-status-detail]");
  let sawActiveRun = false;

  const updateRunStatus = async () => {
    try {
      const response = await fetch(statusUrl, { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      const status = data.status || "UNKNOWN";
      const active = Boolean(data.active || status === "RUNNING");
      if (statusText) statusText.textContent = active ? "RUNNING" : status;
      if (statusDetail) {
        statusDetail.textContent = active
          ? `Uppdatering körs: ${data.sources_attempted || 0}/${data.sources_configured || 0} källor startade.`
          : `Senaste körning: ${data.sources_attempted || 0}/${data.sources_configured || 0} källor, ${data.sources_failed || 0} fel, ${data.items_found || 0} fynd.`;
      }
      if (active) {
        sawActiveRun = true;
      } else if (sawActiveRun) {
        window.location.reload();
      }
    } catch (error) {
      // Statuspollning får aldrig störa själva dashboarden.
    }
  };

  updateRunStatus();
  window.setInterval(updateRunStatus, 4000);
}
