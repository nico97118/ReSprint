document.querySelectorAll("[data-report-generation-form]").forEach((form) => {
  form.addEventListener("submit", () => {
    const button = form.querySelector("button[type='submit']");
    if (!button) {
      return;
    }

    button.disabled = true;
    button.setAttribute("aria-busy", "true");

    const label = button.querySelector(".button-content span:last-child");
    if (label) {
      label.textContent = button.dataset.loadingLabel || label.textContent;
    }
  });
});
