function parseChartConfig(canvas) {
  const rawConfig = canvas.dataset.chartConfig;
  if (!rawConfig) {
    return null;
  }

  try {
    return JSON.parse(rawConfig);
  } catch {
    canvas.dataset.chartError = "invalid-config";
    return null;
  }
}

function compactBarTooltip({ chart, tooltip }) {
  const frame = chart.canvas.parentElement;
  let element = frame.querySelector(".chart-tooltip");
  if (!element) {
    element = document.createElement("div");
    element.className = "chart-tooltip";
    element.setAttribute("role", "tooltip");
    frame.appendChild(element);
  }

  element.hidden = tooltip.opacity === 0;
  if (element.hidden) {
    return;
  }

  element.replaceChildren();
  for (const title of tooltip.title || []) {
    const heading = document.createElement("div");
    heading.className = "chart-tooltip-title";
    heading.textContent = title;
    element.appendChild(heading);
  }
  for (const [index, body] of (tooltip.body || []).entries()) {
    const row = document.createElement("div");
    row.className = "chart-tooltip-row";
    const swatch = document.createElement("span");
    swatch.className = "chart-tooltip-swatch";
    swatch.style.backgroundColor = tooltip.labelColors[index].backgroundColor;
    const label = document.createElement("span");
    label.textContent = [...body.before, ...body.lines, ...body.after].join("\n");
    row.append(swatch, label);
    element.appendChild(row);
  }

  // Keep Chart.js's content, but let the tooltip escape the compact canvas.
  const anchor = chart.canvas.offsetLeft + tooltip.caretX;
  const left = Math.max(0, Math.min(anchor - element.offsetWidth / 2, frame.clientWidth - element.offsetWidth));
  element.style.left = `${left}px`;
  element.style.setProperty("--tooltip-caret-left", `${anchor - left}px`);
}

function renderCharts() {
  if (!window.Chart) {
    return;
  }

  document.querySelectorAll("canvas[data-chart-config]").forEach((canvas) => {
    if (canvas.dataset.chartInitialized === "true") {
      return;
    }

    const config = parseChartConfig(canvas);
    if (!config) {
      return;
    }

    if (canvas.matches(".time-ratio-chart, .ticket-progress-chart")) {
      config.options.plugins.tooltip = { enabled: false, external: compactBarTooltip };
    }

    new window.Chart(canvas, config);
    canvas.dataset.chartInitialized = "true";
  });
}

renderCharts();
