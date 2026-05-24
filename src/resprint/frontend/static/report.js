const tabButtons = Array.from(document.querySelectorAll("[data-report-tab]"));
const tabPanels = Array.from(document.querySelectorAll("[data-report-panel]"));

function activateTab(targetId) {
  tabButtons.forEach((button) => {
    const active = button.dataset.targetPanel === targetId;
    button.setAttribute("aria-selected", String(active));
  });
  tabPanels.forEach((panel) => {
    panel.hidden = panel.id !== targetId;
  });
}

tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    activateTab(button.dataset.targetPanel);
  });
});
if (tabButtons.length) {
  activateTab(tabButtons[0].dataset.targetPanel);
}

const exportForm = document.querySelector("[data-report-export]");

if (exportForm) {
  exportForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const format = exportForm.querySelector("[data-export-format]").value;
    if (format !== "json") {
      return;
    }

    const source = document.getElementById("report-export-json");
    if (!source) {
      return;
    }

    const blob = new Blob([source.textContent], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${exportForm.dataset.exportBasename}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });
}
