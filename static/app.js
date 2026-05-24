const updateButton = document.querySelector("[data-update-button]");

if (updateButton) {
  updateButton.closest("form").addEventListener("submit", () => {
    updateButton.disabled = true;
    updateButton.textContent = "UPPDATERAR...";
  });
}
