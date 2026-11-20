import { test as base, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

// A rendered page alone cannot catch a broken script or missing minified asset.
const test = base.extend({
  page: async ({ page }, use) => {
    const failures = [];
    page.on('pageerror', (error) => failures.push(error.message));
    page.on('response', (response) => {
      if (response.url().includes('/assets/') && response.status() >= 400) {
        failures.push(`${response.status()} ${response.url()}`);
      }
    });
    await use(page);
    expect(failures, 'Browser errors and broken assets').toEqual([]);
  },
});
const reportURL = '/report?sprint_id=456&tempo_team_id=42';

async function completedPanel(page) {
  await page.goto(reportURL);
  const tab = page.getByRole('tab', { name: /Tickets terminés/ });
  await expect(tab).toHaveAttribute('aria-selected', 'true');
  return page.locator(`#${await tab.getAttribute('data-target-panel')}`);
}

test('sprint selection and selected workers reach the generated report', async ({ page }) => {
  await page.goto('/');
  await page.locator('form[action="/participants"]').first().getByRole('button').click();
  await expect(page).toHaveURL(/\/participants\?sprint_id=456/);
  const generate = page.getByRole('button', { name: 'Générer le rapport', exact: true });
  await expect(generate).toBeDisabled();
  await page.getByRole('combobox', { name: 'Équipe Tempo' }).selectOption('42');
  const workers = page.locator('input[name="tempo_worker"][type="checkbox"]');
  await expect(workers).toHaveCount(3);
  for (const worker of await workers.all()) await worker.uncheck();
  await expect(generate).toBeDisabled();
  await page.getByRole('checkbox', { name: 'Bob Leroy' }).check();
  await expect(generate).toBeEnabled();
  await generate.click();
  await expect(page).toHaveURL(/\/report\?/);
  const params = new URL(page.url()).searchParams;
  expect(params.getAll('tempo_worker')).toEqual(['bob']);
  await expect(page.locator('.report-participant')).toHaveText(['Bob Leroy']);
});

test('period form preserves dates, JQL and report name through team selection', async ({ page }) => {
  await page.goto('/');
  await page.getByText('Analyse par période et JQL', { exact: true }).click();
  const form = page.locator('#period-report-form');
  await form.locator('[name="sprint_name"]').fill('Période de validation');
  await form.locator('[name="start_date"]').fill('2026-05-01');
  await form.locator('[name="end_date"]').fill('2026-05-15');
  await form.locator('[name="jql"]').fill('project = ABC');
  await form.getByRole('button', { name: 'Continuer' }).click();
  await page.getByRole('combobox', { name: 'Équipe Tempo' }).selectOption('42');
  await page.getByRole('button', { name: 'Générer le rapport', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Période de validation');
  await expect(page.locator('[data-jql-text]')).toHaveText('project = ABC');
  const params = new URL(page.url()).searchParams;
  expect(params.get('start_date')).toBe('2026-05-01');
  expect(params.get('end_date')).toBe('2026-05-15');
  expect(params.getAll('tempo_worker')).toEqual(['alice', 'bob', 'carol']);
});

test('tabs select exactly one panel and charts initialize', async ({ page }) => {
  await page.goto(reportURL);
  for (const tab of await page.getByRole('tab').all()) {
    await tab.click();
    await expect(tab).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('[data-report-panel]:visible')).toHaveCount(1);
    await expect(page.locator(`#${await tab.getAttribute('data-target-panel')}`)).toBeVisible();
  }
  await expect.poll(() => page.locator('canvas[data-chart-config]').evaluateAll(
    (canvases) => canvases.length > 0 && canvases.every((canvas) => !!window.Chart.getChart(canvas)),
  )).toBe(true);
});

test('search updates rows, totals and empty state and collapses hidden details', async ({ page }) => {
  const panel = await completedPanel(page);
  const row = panel.locator('[data-table-row]').filter({ has: page.getByRole('link', { name: 'ABC-12', exact: true, includeHidden: true }) });
  const toggle = row.locator('[data-row-toggle-button]');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  const detail = page.locator(`#${await row.getAttribute('data-detail-row-id')}`);
  await expect(detail).toBeVisible();
  const search = panel.getByRole('searchbox');
  await search.fill('ABC-12');
  await expect(panel.locator('[data-table-row]:visible')).toHaveCount(1);
  await expect(panel.locator('[data-row-count]')).toHaveText('1 / 4');
  for (const header of await panel.locator('[data-total-column]').all()) {
    const column = Number(await header.getAttribute('data-total-column'));
    await expect(header.locator('[data-column-total]')).toHaveText(
      (await row.locator('td').nth(column).innerText()).trim(),
    );
  }
  await search.fill('no-matching-ticket');
  await expect(panel.locator('[data-no-results]')).toBeVisible();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await search.clear();
  await expect(panel.locator('[data-table-row]:visible')).toHaveCount(4);
  await expect(detail).toBeHidden();
  await expect(panel.locator('[data-no-results]')).toBeHidden();
});

test('numeric ticket sorting preserves row-detail association', async ({ page }) => {
  const panel = await completedPanel(page);
  const keys = panel.locator('[data-table-row] a').filter({ hasText: /^ABC-\d+$/ });
  await expect(keys).toHaveText(['ABC-1', 'ABC-4', 'ABC-10', 'ABC-12']);
  const sort = panel.locator('[data-sort-column]').filter({ hasText: 'Clé' });
  await sort.click();
  await expect(keys).toHaveText(['ABC-12', 'ABC-10', 'ABC-4', 'ABC-1']);
  await expect(sort.locator('..')).toHaveAttribute('aria-sort', 'descending');
  for (const row of await panel.locator('[data-table-row]').all()) {
    expect(await row.evaluate((element) => element.nextElementSibling.id)).toBe(await row.getAttribute('data-detail-row-id'));
  }
});

test('table filters combine with search and Escape dismisses the menu', async ({ page }) => {
  const panel = await completedPanel(page);
  const filter = panel.locator('[data-table-filter]').filter({ hasText: 'Responsable' });
  await filter.locator('summary').click();
  await filter.getByRole('checkbox', { name: 'Alice Martin', exact: true }).check();
  const rows = panel.locator('[data-table-row]:visible');
  await expect(rows).not.toHaveCount(0);
  const column = Number(await filter.getAttribute('data-filter-column'));
  for (const row of await rows.all()) await expect(row.locator('td').nth(column)).toHaveText('Alice Martin');
  await page.keyboard.press('Escape');
  await expect(filter.locator('details')).not.toHaveAttribute('open', '');
  await panel.getByRole('searchbox').fill('no-matching-ticket');
  await expect(rows).toHaveCount(0);
  await panel.getByRole('searchbox').clear();
  await expect(rows).not.toHaveCount(0);
  await filter.locator('summary').click();
  await filter.getByRole('checkbox', { name: 'Alice Martin', exact: true }).uncheck();
  await expect(rows).toHaveCount(4);
});

for (const [format, extension] of [['JSON', 'json'], ['Markdown', 'md']]) {
  test(`${format} export downloads actual report content`, async ({ page }) => {
    await page.goto(reportURL);
    await page.locator('[data-report-export] summary').click();
    const pending = page.waitForEvent('download');
    await page.getByRole('button', { name: format, exact: true }).click();
    const download = await pending;
    expect(download.suggestedFilename()).toMatch(new RegExp(`\\.${extension}$`));
    const content = await readFile(await download.path(), 'utf8');
    if (format === 'JSON') {
      expect(JSON.parse(content).completed.map((item) => item.key).sort()).toEqual(['ABC-1', 'ABC-10', 'ABC-12', 'ABC-4']);
    } else {
      expect(content).toContain('ABC-12');
      expect(content).toContain('Sprint de démonstration');
    }
    await expect(page.locator('[data-report-export]')).not.toHaveAttribute('open', '');
  });
}

test('theme switch persists across reloads and navigation', async ({ page }) => {
  await page.goto('/');
  const toggle = page.getByRole('switch');
  await expect(toggle).toHaveAttribute('aria-checked', 'false');
  await toggle.click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(toggle).toHaveAttribute('aria-checked', 'true');
  await page.goto(reportURL);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await toggle.click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});

test('duration sorting compares seconds numerically in both directions', async ({ page }) => {
  const panel = await completedPanel(page);
  const header = panel.locator('[data-total-column]').last();
  const column = Number(await header.getAttribute('data-total-column'));
  const sort = header.locator('[data-sort-column]');
  const values = () => panel.locator('[data-table-row]').evaluateAll(
    (rows, index) => rows.map((row) => Number(row.cells[index].dataset.sortValue)), column,
  );
  await sort.click();
  const ascending = await values();
  expect(new Set(ascending).size).toBeGreaterThan(1);
  expect(ascending).toEqual([...ascending].sort((a, b) => a - b));
  await sort.click();
  expect(await values()).toEqual([...ascending].reverse());
});

test('review search and detail expansion display reviewer decisions', async ({ page }) => {
  await page.goto(reportURL);
  await page.locator('.reviews-group > summary').click();
  const reviews = page.locator('#code-reviews');
  await reviews.getByRole('searchbox').fill('D103');
  await expect(reviews.locator('[data-table-row]:visible')).toHaveCount(1);
  const row = reviews.locator('[data-table-row]:visible');
  await expect(row).toContainText('D103');
  await row.locator('[data-row-toggle-button]').click();
  const detail = page.locator(`#${await row.getAttribute('data-detail-row-id')}`);
  await expect(detail).toBeVisible();
  await expect(detail).toContainText('Équipe architecture');
  await expect(detail.locator('.review-decision-required_pending')).toBeVisible();
  await reviews.getByRole('searchbox').fill('D104');
  const rejectedRow = reviews.locator('[data-table-row]:visible');
  await expect(rejectedRow).toContainText('D104');
  await rejectedRow.locator('[data-row-toggle-button]').click();
  const rejectedDetail = page.locator(`#${await rejectedRow.getAttribute('data-detail-row-id')}`);
  await expect(rejectedDetail.locator('.review-decision-changes_requested')).toBeVisible();
  await expect(rejectedDetail).toContainText('Bob Leroy');
  await reviews.getByRole('searchbox').clear();
  await expect(reviews.locator('[data-table-row]:visible')).toHaveCount(8);
});
