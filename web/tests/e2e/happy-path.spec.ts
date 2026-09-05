import { test, expect } from "@playwright/test";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("happy path: settings → import → precompute → players → detail", async ({ page }) => {
  test.setTimeout(180_000); // two stat imports (QB + WR) means precompute runs twice

  await page.goto("/");
  await expect(page.locator("h1")).toHaveText("Settings");
  await page.getByRole("button", { name: /half ppr/i }).click();

  await page.goto("/import");
  const qbFixture = path.resolve(__dirname, "../../../tests/fixtures/fantasypros_qb.html");
  // The page has two upload cards (stats and ADP), each with its own file
  // input and "Upload" button — the stats card renders first in the DOM.
  await page.locator("input[type=file]").first().setInputFiles(qbFixture);
  await page.getByRole("button", { name: "Upload" }).first().click();

  // Counts land, then the precompute bar runs to completion and hides.
  await expect(page.getByText(/IMPORTED/i)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Computing distributions/)).toBeVisible();
  await expect(page.getByText(/Computing distributions/)).toBeHidden({ timeout: 90_000 });

  // QB scoring never depends on the scoring preset (a QB's projected stat
  // line has no receptions, the only preset-varying multiplier — see
  // app/scoring/presets.py), so proving further down that a preset switch
  // actually changes a displayed value requires at least one player whose
  // score IS preset-dependent. Import a receiving position too.
  const wrFixture = path.resolve(__dirname, "../../../tests/fixtures/fantasypros_wr.html");
  await page.locator("#stats-position").selectOption("WR");
  await page.locator("input[type=file]").first().setInputFiles(wrFixture);
  await page.getByRole("button", { name: "Upload" }).first().click();
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
  // three rulings, two fix rounds) and had zero E2E coverage until now. Use
  // a WR player specifically (filtered via the position tabs, restricted to
  // a card that already has a computed distribution) since the player
  // landed on above may well be the QB just imported, whose score can't
  // change with the preset.
  await page.goto("/players");
  await page.getByRole("button", { name: "WR" }).click();
  const wrCard = page.getByTestId("player-card").filter({ hasText: /FLOOR/i }).first();
  await expect(wrCard).toBeVisible({ timeout: 15_000 });
  await wrCard.click();

  const medianTile = page.locator("text=MEDIAN (P50)").locator("..");
  await expect(medianTile).toBeVisible();
  const beforeSwitch = await medianTile.textContent();
  await page.getByRole("combobox").selectOption("full_ppr");
  await expect(medianTile).not.toHaveText(beforeSwitch ?? "");

  // The engine assumes player independence; the UI must never claim otherwise.
  await expect(page.getByText(/correlation/i)).toHaveCount(0);
});
