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
  // WR, not QB: QB scoring never depends on the scoring preset (a QB's
  // projected stat line has no receptions, the only preset-varying
  // multiplier — see app/scoring/presets.py), and the preset-switch
  // assertion below needs a player whose score IS preset-dependent.
  const fixture = path.resolve(__dirname, "../../../tests/fixtures/fantasypros_wr.html");
  // The page has two upload cards (stats and ADP), each with its own file
  // input and "Upload" button — the stats card renders first in the DOM.
  await page.locator("#stats-position").selectOption("WR");
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

  // Switching the preset must actually change what's displayed — this is
  // the single most-revised mechanism on this branch (shared PresetContext,
  // three rulings, two fix rounds) and had zero E2E coverage until now.
  // Every imported player here is a WR, so the score IS preset-dependent —
  // no need to discriminate between cards.
  const medianTile = page.locator("text=MEDIAN (P50)").locator("..");
  const beforeSwitch = await medianTile.textContent();
  await page.getByRole("combobox").selectOption("full_ppr");
  await expect(medianTile).not.toHaveText(beforeSwitch ?? "");

  // The engine assumes player independence; the UI must never claim otherwise.
  await expect(page.getByText(/correlation/i)).toHaveCount(0);
});
