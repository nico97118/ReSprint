import { copyFile, mkdir, readdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const vendorDir = join(root, "src/resprint/frontend/static/vendor");

await vendorChartJs();
await vendorMdi();

async function vendorChartJs() {
  const chartDir = join(vendorDir, "chartjs");
  await mkdir(chartDir, { recursive: true });
  await copyFile(
    join(root, "node_modules/chart.js/dist/chart.umd.js"),
    join(chartDir, "chart.umd.js"),
  );
  await copyFile(
    join(root, "node_modules/chart.js/dist/chart.umd.js.map"),
    join(chartDir, "chart.umd.js.map"),
  );
  await copyFile(
    join(root, "node_modules/chart.js/LICENSE.md"),
    join(chartDir, "LICENSE.md"),
  );
}

async function vendorMdi() {
  const mdiDir = join(vendorDir, "mdi");
  const mdiCssDir = join(mdiDir, "css");
  const mdiFontsDir = join(mdiDir, "fonts");
  await mkdir(mdiCssDir, { recursive: true });
  await mkdir(mdiFontsDir, { recursive: true });
  await copyFile(
    join(root, "node_modules/@mdi/font/css/materialdesignicons.min.css"),
    join(mdiCssDir, "materialdesignicons.min.css"),
  );
  await copyFile(
    join(root, "node_modules/@mdi/font/LICENSE"),
    join(mdiDir, "LICENSE"),
  );

  const sourceFontsDir = join(root, "node_modules/@mdi/font/fonts");
  for (const filename of await readdir(sourceFontsDir)) {
    if (filename.startsWith("materialdesignicons-webfont.")) {
      await copyFile(
        join(sourceFontsDir, filename),
        join(mdiFontsDir, filename),
      );
    }
  }
}
