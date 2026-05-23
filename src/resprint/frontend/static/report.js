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
