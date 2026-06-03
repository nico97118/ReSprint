document.querySelectorAll("[data-auto-submit-on-change]").forEach((form) => {
  form.querySelectorAll("select").forEach((select) => {
    select.addEventListener("change", () => {
      form.requestSubmit();
    });
  });
});

document.querySelectorAll("[data-report-generation-form]").forEach((form) => {
  form.addEventListener("submit", () => {
    form
      .querySelectorAll("[data-synced-tempo-worker]")
      .forEach((input) => input.remove());

    document
      .querySelectorAll(".tempo-member-option input[name='tempo_worker']:checked")
      .forEach((workerInput) => {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "tempo_worker";
        input.value = workerInput.value;
        input.dataset.syncedTempoWorker = "true";
        form.appendChild(input);
      });

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
