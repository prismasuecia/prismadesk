const updateButton = document.querySelector("[data-update-button]");
const runStatusPanel = document.querySelector("[data-run-status-panel]");
const statusText = document.querySelector("[data-run-status-text]");
const statusDetail = document.querySelector("[data-run-status-detail]");
let sawActiveRun = false;

const setUpdateButtonState = (active) => {
  if (!updateButton) return;
  updateButton.disabled = active;
  updateButton.textContent = active ? "UPPDATERING KÖR..." : "UPPDATERA DESK";
};

const setStatus = (text, detail) => {
  if (statusText) statusText.textContent = text;
  if (statusDetail) statusDetail.textContent = detail;
};

if (runStatusPanel) {
  const statusUrl = runStatusPanel.dataset.runStatusUrl;

  var updateRunStatus = async () => {
    try {
      const response = await fetch(statusUrl, { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      const status = data.status || "UNKNOWN";
      const active = Boolean(data.active || status === "RUNNING");
      setUpdateButtonState(active);
      setStatus(
        active ? "RUNNING" : status,
        active
          ? `Uppdatering körs: ${data.sources_attempted || 0}/${data.sources_configured || 0} källor startade.`
          : `Senaste körning: ${data.sources_attempted || 0}/${data.sources_configured || 0} källor, ${data.sources_failed || 0} fel, ${data.items_found || 0} fynd.`
      );
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

if (updateButton) {
  updateButton.closest("form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    setUpdateButtonState(true);
    setStatus("STARTAR", "Uppdatering startas. Vänta kvar på sidan.");

    try {
      const response = await fetch(form.action, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Accept": "application/json",
          "X-Requested-With": "fetch"
        }
      });
      const data = await response.json().catch(() => ({}));
      if (response.status === 409) {
        sawActiveRun = true;
        setUpdateButtonState(true);
        setStatus("RUNNING", data.message || "Uppdatering kör redan.");
      } else if (!response.ok || data.started === false) {
        setUpdateButtonState(false);
        setStatus("FEL", data.message || "Kunde inte starta uppdateringen.");
      } else {
        sawActiveRun = true;
        setStatus("RUNNING", data.message || "Uppdatering startad.");
      }
      if (typeof updateRunStatus === "function") {
        updateRunStatus();
      }
    } catch (error) {
      setUpdateButtonState(false);
      setStatus("FEL", "Kunde inte nå servern. Ladda om sidan och försök igen.");
    }
  });
}
