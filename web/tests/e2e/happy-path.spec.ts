import { test, expect } from "@playwright/test";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("happy path: settings → import → precompute → players → detail", async ({ page }) => {
  test.setTimeout(120_000); // precompute is genuinely slow on a cold machine

  await page.goto("/");
  await expect(page.locator("h1")).toHaveText("Settings");
  await page.getByRole("button", { name: /half ppr/i }).click();

  await page.goto("/import");
  const fixture = path.resolve(__dirname, "../../../tests/fixtures/fantasypros_qb.html");
  // The page has two upload cards (stats and ADP), each with its own file
  // input and "Upload" button — the stats card renders first in the DOM.
  await page.locator("input[type=file]").first().setInputFiles(fixture);
  await page.getByRole("button", { name: "Upload" }).first().click();

  // Counts land, then the precompute bar runs to completion and hides.
  await expect(page.getByText(/IMPORTED/i)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Computing distributions/)).toBeVisible();
  await expect(page.getByText(/Computing distributions/)).toBeHidden({ timeout: 90_000 });

  await page.goto("/players");
  const firstCard = page.getByTestId("player-card").first();
  await expect(firstCard).toBeVisible({ timeout: 15_000 });
  // The card must show a real distribution, not just a point estimate.
  await expect(firstCard.getByText(/FLOOR/i)).toBeVisible();
  await expect(firstCard.locator("svg")).toBeVisible();

  await firstCard.click();
  await expect(page.getByText(/MEDIAN \(P50\)/)).toBeVisible();
  await expect(page.locator("svg.recharts-surface")).toBeVisible();
  await expect(page.getByText(/treat intervals as informed bounds/i)).toBeVisible();

  // The engine assumes player independence; the UI must never claim otherwise.
  await expect(page.getByText(/correlation/i)).toHaveCount(0);
});
