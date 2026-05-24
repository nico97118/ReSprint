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
const exportFormats = {
  json: {
    extension: "json",
    sourceId: "report-export-json",
    type: "application/json;charset=utf-8",
  },
  markdown: {
    extension: "md",
    sourceId: "report-export-markdown",
    type: "text/markdown;charset=utf-8",
  },
};

if (exportForm) {
  exportForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const format = exportForm.querySelector("[data-export-format]").value;
    const exportConfig = exportFormats[format];
    if (!exportConfig) {
      return;
    }

    const source = document.getElementById(exportConfig.sourceId);
    if (!source) {
      return;
    }

    const blob = new Blob([source.textContent], {
      type: exportConfig.type,
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${exportForm.dataset.exportBasename}.${exportConfig.extension}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });
}

const copyJqlButton = document.querySelector("[data-copy-jql]");

if (copyJqlButton) {
  copyJqlButton.addEventListener("click", async () => {
    const source = document.querySelector("[data-jql-text]");
    if (!source || !navigator.clipboard) {
      return;
    }

    await navigator.clipboard.writeText(source.textContent.trim());
  });
}
