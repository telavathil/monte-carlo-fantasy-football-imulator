import { test, expect } from "@playwright/test";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("happy path: settings → import QB → players → detail", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h1")).toHaveText("Settings");
  await page.getByRole("button", { name: "half_ppr" }).click();

  await page.goto("/import");
  const fixture = path.resolve(__dirname, "../../../tests/fixtures/fantasypros_qb.html");
  await page.setInputFiles("input[type=file]", fixture);
  // Selecting source is already "fantasypros" by default.
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.locator("pre")).toContainText("matched_rows");

  await page.goto("/players");
  await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 5000 });
  // At least one linked row — click through to the detail page.
  const firstLink = page.locator("table tbody tr td a").first();
  await expect(firstLink).toBeVisible();
  await firstLink.click();
  // Histogram SVG present
  await expect(page.locator("svg.recharts-surface")).toBeVisible();
  await expect(page.getByText(/Calibration note/)).toBeVisible();
});
