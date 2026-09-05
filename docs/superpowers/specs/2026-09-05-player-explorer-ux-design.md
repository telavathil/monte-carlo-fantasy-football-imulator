# Player Explorer UX & Performance Pass — Design

- **Date:** 2026-09-05
- **Status:** Draft (pending review)
- **Builds on:** [MVP design](2026-04-18-mc-ff-simulator-mvp-design.md), shipped as PR #2 (`7764d04`)
- **Requirements source:** Requirements v1.2 §6.1 (UI features), §7.3 (performance targets), §8 (viewports)

---

## 1. Overview

The MVP proved the pipeline: import a stat-level CSV, resolve identity, fit per-stat
distributions, run a Monte Carlo simulation, show a histogram. What it did not do is make
that pipeline pleasant to use. The frontend is four unstyled pages built on the stock Vite
template CSS; the player detail page does not display the player's name; a first visit
after idle hangs for 15-25 seconds with no explanation; and rows that fail identity
resolution disappear without trace.

This pass closes that gap. It adds no new analytical capability — no tiers, no boom/bust
grades, no comparison, no draft tooling. It makes the existing capability legible, fast,
and honest about its own failure modes.

### Goals

1. A designed interface, replacing template CSS and ad-hoc inline styles with a coherent
   token set and a small component library.
2. Distribution summaries available for every listed player without a per-player wait,
   so the list can show uncertainty rather than just a point estimate.
3. Every failure state — cold boot, no history, unsupported position, unresolved import
   row, bad token — surfaced as a designed message rather than a stringified exception.

### Non-goals

Deliberately deferred, and generated designs or code for any of these should be discarded:

- Tier clustering, boom/bust profile, consistency grade, stat-contribution waterfall,
  side-by-side player comparison (Requirements v1.2 §6.1, deferred to a later pass).
- Scoring rule editor. The three presets stay fixed; only the selector moves.
- Manual identity re-mapping. Unresolved rows become visible, not fixable.
- Rookie support. Players with fewer than `MIN_GAMES` (4) career games continue to
  return 422; the message just stops looking like a crash.
- Draft simulator, live draft assistant, weekly/season management.
- Mobile phone layouts. Desktop primary, tablet secondary.
- Any new runtime dependency beyond Tailwind CSS v4 and its Vite plugin.

---

## 2. What exists today

Backend, `api/app/` (~1,500 lines, 8 tables): `import_pipeline/`, `identity/`, `scoring/`,
`historical/`, `sim/`, and six routers. Frontend, `web/src/` (~300 lines): four page
components, one `Histogram` built on recharts, one `apiFetch` wrapper.

Three facts about the current implementation drive most of this design:

- `player_distribution_params` already caches the expensive per-stat fits, keyed by
  `player_id`. Fits are scoring-preset-independent, since they are derived from historical
  game logs. This table is correct and does not change.
- `GET /api/players` returns `player_id`, `name`, `team`, `position`, `projected_points`,
  `adp_snake` — no distribution data of any kind.
- `api/fly.toml:19-21` sets `auto_stop_machines = 'stop'` with `min_machines_running = 0`.
  This stays: the cold boot is masked in the UI rather than paid for. See §8.

---

## 3. Data model change

One new table.

### `player_distribution_summary`

| Column | Type | Notes |
|---|---|---|
| `player_id` | Integer | FK `player.mfl_id`, composite PK |
| `scoring_preset` | String | composite PK; `standard` / `half_ppr` / `full_ppr` |
| `floor_p10` | Float | |
| `median_p50` | Float | |
| `ceiling_p90` | Float | |
| `mean` | Float | |
| `std` | Float | |
| `histogram` | Text | JSON `{bin_edges, counts}` |
| `computed_points` | Float | deterministic score of the projection under the preset |
| `n_samples` | Integer | |
| `source_projection_id` | Integer | FK `player_projection.id` — the exact projection summarized |
| `computed_at` | String | ISO timestamp |

Keyed by `(player_id, scoring_preset)` because the summary is points-denominated and
therefore preset-dependent, while `player_distribution_params` is not. Switching presets
does not invalidate anything; it selects a different row, computing it on demand if absent.

Summaries are deterministic: the simulation seed stays fixed at 42, as it already is at
`api/app/routers/players.py:164`.

### Invalidation

| Trigger | Action |
|---|---|
| New `PlayerProjection` row for player X | Delete all summaries for X, every preset |
| `POST /api/historical/refresh` | Delete all `player_distribution_params` and all summaries |
| `POST /api/admin/refresh-players` | Delete all summaries whose `player_id` changed identity |
| Preset change in `LeagueConfig` | No deletion — different composite key |

The third row closes a gap flagged during the MVP's final review: `refresh-players` is a
second code path that can leave cached derivations pointing at stale identity, and the
MVP fix wave only covered `stats_importer.py`.

---

## 4. API surface changes

Four changes, no new routers.

### `GET /api/players` — extended

Each `PlayerRow` gains an optional `distribution` object, populated from
`player_distribution_summary` for the currently configured preset when a row exists,
`null` otherwise:

```json
{ "floor_p10": 5.6, "median_p50": 13.2, "ceiling_p90": 24.6,
  "histogram": {"bin_edges": [...], "counts": [...]}, "computed_at": "..." }
```

Fetched as a single batched query keyed by player id, following the batching pattern
already established for projections and ADP in `list_players` (`players.py:41`). It must
not reintroduce the N+1 that pass removed.

### `POST /api/players/precompute?limit=25` — new

Computes summaries for the next `limit` players that have a projection but no summary
under the current preset. Returns:

```json
{ "computed": 25, "done": 125, "total": 312, "remaining": 187 }
```

Idempotent and resumable: a player with an existing valid summary is skipped, so a
repeated or interrupted call is safe. Bounded work per request keeps every call well
inside proxy timeouts.

### `GET /api/imports/{batch_id}/unresolved` — new

Read-only. Returns rows from `import_unresolved` (`orm.py:85`) — `parsed_name`,
`parsed_team`, `resolution`, and the raw `csv_row` — with `position` taken from the
parent `ImportBatch.position`, since `import_unresolved` has no position column.

### `GET /api/players/{id}/distribution` — extended

`DistributionResponse` gains `name`, `team`, `position`, and `adp_snake`. This is the
reason the detail page currently renders `<h1>Player 42</h1>` — the data was never there.

---

## 5. Why precompute is chunked and visible

A full FantasyPros import is roughly 250-350 players across four positions. At the
measured ~250ms per player fit (spike C2: p50 179ms, p95 311ms), computing every summary
is 60-90 seconds of work.

Three options were considered:

1. **Synchronously inside the import request.** Rejected: a 90-second upload request is
   both a bad experience and a proxy-timeout risk.
2. **A background task after the import response returns.** Rejected: it fights
   `auto_stop_machines = 'stop'`. Fly stops the machine on idle, and a detached task is
   not a reliable keep-alive. Work would silently truncate.
3. **Client-driven chunked precompute.** Chosen. The frontend loops
   `POST /api/players/precompute` until `remaining == 0`, rendering a progress bar. Each
   call is a real request holding the machine awake, work is resumable across
   interruptions, and progress is honest rather than hidden.

The trade is that the user watches a progress bar after import. Given that it replaces an
unexplained per-player stall discovered later while browsing, visible cost beats hidden
cost here.

---

## 6. Frontend architecture

**Tailwind CSS v4** via `@tailwindcss/vite`. Delete `web/src/App.css` (184 lines, never
imported — dead Vite starter). Replace `web/src/index.css` with the Tailwind import plus
an `@theme` block holding the token set from the visual design (Appendix A).

New components under `web/src/components/`, each small and single-purpose per the
project's file-organization rules:

| Component | Responsibility |
|---|---|
| `Card` | Bordered surface, the one elevation primitive |
| `Skeleton` | Shimmer block; composes into skeleton cards for the warming state |
| `StatTile` | Uppercase muted label over a large value |
| `PositionTabs` | Segmented All/QB/RB/WR/TE control |
| `SearchInput` | Debounced text filter |
| `Sparkline` | Inline SVG distribution curve from histogram bins |
| `PresetSelector` | Reads and writes `LeagueConfig.scoring_preset` |
| `EmptyState` / `ErrorState` | Designed non-happy paths |

`Sparkline` is deliberately hand-rolled inline SVG rather than recharts. The Players list
renders one per card across hundreds of rows, and that many recharts instances would
dominate render time. Recharts stays for the single large histogram on the detail page,
where it already works.

---

## 7. Screens

**Players list.** Sticky header with nav and preset selector. Search, position tabs, sort
control. A stack of wide cards, each showing name, `POS · TEAM · ADP`, a sparkline with a
median marker and a shaded p10-p90 band, the projected points as the dominant number, and
floor/median/ceiling along the bottom edge. Cards without a summary render a compute
affordance rather than a blank region. Skeleton cards while loading.

**Player detail.** Real title from the new response fields. Three stat tiles
(floor/median/ceiling) above the large histogram, which gains an x-axis labelled in
fantasy points, a median marker, and a shaded percentile band. Projected stats become a
two-column table with humanized labels — "Receiving yards", not `receiving_yards`. Fit
provenance and the calibration caveat move into a designed callout.

**Import.** Two labelled drop zones with source selectors, a post-import count panel, the
precompute progress bar, and the unresolved-rows table.

**Settings.** Token field with a connection status row, and the preset segmented control
with helper text noting that changing it triggers a recompute pass.

Every points value on every screen is **per game**, and every label must say so. The MVP
shipped a bug about exactly this wording (fixed in `adbe655`); the design must not
reintroduce the ambiguity.

---

## 8. Warming, loading, and errors

`apiFetch` gains a request timeout, retry with backoff, and a "slow first request" signal
emitted when a request exceeds ~2s without responding. That signal drives a warming
screen: skeleton cards behind a panel reading "Waking the server up…", an indeterminate
progress bar, and body text explaining that the API sleeps when idle to stay on the free
tier and that this happens only on first load.

`min_machines_running` stays at 0. The 15-25s wait is not eliminated, it is explained.

Typed error mapping replaces `<pre>{String(e)}</pre>`:

| Condition | Message |
|---|---|
| `401` | "Check your API token in Settings" |
| `422 insufficient_history` | "Only N career games — not enough history to model" |
| `422 not_supported_mvp` | "Kickers and defenses aren't modeled yet" |
| `404` no projection | "No projection imported for this player" |
| Network failure | Inline retry button |

---

## 9. Testing

- **Unit:** summary computation and each invalidation trigger; sparkline bin-to-path math;
  the error-mapping utility; humanized stat labels.
- **Integration:** precompute chunking — resumability, idempotency, correct `remaining`
  arithmetic, and skip-if-present; players list with summaries present, absent, and mixed;
  batched summary fetch issues a bounded number of queries; distribution response carries
  identity fields; unresolved endpoint against a batch with known failures.
- **E2E (Playwright):** extend the happy path to import → precompute to completion →
  cards render with distributions → open detail → switch preset → values change.

The 80% coverage gate holds (currently 84.60%).

---

## 10. Risks and open questions

- **Preset switching costs a precompute pass.** The first switch to a preset with no
  summaries triggers a visible recompute of every player. Accepted: precomputing all three
  presets at import would triple import time for two presets that may never be used.
- **Summary staleness across identity changes.** `refresh-players` can remap identity;
  §3's third invalidation rule addresses it, and it needs a dedicated integration test
  since it closes a previously-shipped gap rather than a new one.
- **Stitch output is a visual target, not source.** Generated markup is decorative and not
  data-bound. Translating it into the §6 components is real work and must not be
  underestimated in planning as "paste the export".
- **Open:** exact token values (color scale, type scale, radii, accent) come from the
  Appendix A design pass and are not fixed by this spec.

---

## Appendix A — Visual design brief

The visual design is produced in Google Stitch and implemented as the §6 components. This
brief is the input.

### A.1 Global direction

> A dark, data-dense fantasy football analytics web app for a single expert user.
> Near-black slate surfaces (#0B0E14 background, #151A23 cards), hairline borders
> (#232A36), subtle elevation, no heavy drop shadows. Typography: a geometric sans (Inter
> or similar), tight tracking on headings, tabular figures for all numbers. Numbers are the
> hero — projected points render very large and high-contrast; labels are small, uppercase,
> muted (#7A8699). Generous spacing, one clear focus per screen. Desktop primary (1440px),
> tablet secondary (834px). Use the full width; never centered-narrow. Charts are the
> second hero: distribution curves are filled area shapes in the accent color at ~30%
> opacity with a solid 2px stroke.
>
> Propose three accent color candidates rather than committing to one. Render the Players
> list screen once per candidate so they can be compared in context, not as isolated
> swatches. Each must reach at least 4.5:1 contrast against #0B0E14 at large-number size;
> must stay legible as a filled chart area at 30% opacity over #151A23; and must not read
> as gain/loss semantics — avoid pure reds and any green-red pairing, since nothing here is
> directional. Keep all other tokens identical across the three variants.
>
> Every number on screen is **per game**, not a season total. Labels must say "pts / game".

### A.2 Screen priority

Players list (×3 accent variants) → Player detail → the three states → Import → Settings.
Everything after the first two inherits their tokens, so quality matters most there.

### A.3 Screen prompts

**Players list.** Sticky top bar: app name "MC Sim" left; nav Settings / Import / Players
with Players active; scoring preset dropdown reading "Half PPR" right. Below: full-width
search input, placeholder "Search players…". Then segmented filter tabs — All, QB, RB, WR,
TE — with All active, and a right-aligned sort dropdown reading "Sort: Projected". Then a
single-column stack of wide player cards, about 8 visible. Each card has three zones.
Left: player name large semibold, with a small muted line "WR · CIN · ADP 1.2" beneath.
Center: a wide right-skewed distribution curve, filled accent, roughly 220×56px, with a
thin vertical marker at the median and a lighter shaded band spanning the 10th to 90th
percentile. Right: projected points as a very large accent number with a small muted
"pts / game" beneath. Along the card's bottom edge, three small labelled figures evenly
spaced: "FLOOR 5.6", "MEDIAN 13.2", "CEILING 24.6" — labels uppercase and muted, values
white. Page footer: muted "47 players".

**Player detail.** Back link "← Players". Title "Ja'Marr Chase" very large, subtitle
"WR · CIN · ADP 1.2" muted beneath, preset dropdown "Half PPR" right-aligned on the title
row. Three equal stat tiles side by side, each bordered with a small uppercase muted label
over a large value: "FLOOR (P10) 5.6", "MEDIAN (P50) 13.2", "CEILING (P90) 24.6" — median
value in the accent, others white. Beneath, a large histogram roughly 900×320px: filled
accent bars, x-axis labelled "Fantasy points per game" with ticks, a solid vertical line
at the median labelled "13.2", a lighter shaded region spanning floor to ceiling, no
y-axis labels. Below the chart, two columns. Left: "Projected stats" as a clean two-column
table — Receptions 7.1, Receiving yards 96.3, Receiving TDs 0.8, Rushing attempts 0.1,
Rushing yards 0.7, Fumbles lost 0.0. Right: muted provenance "Fit from 51 games · seasons
2023–2025", and beneath it a bordered callout with an info icon: "Calibration note —
distributions reflect uncertainty around the imported projection. Treat intervals as
informed bounds, not guarantees."

**Import.** Two side-by-side dashed-border drop zones with upload icons: "Stat projections
(CSV)" and "ADP (CSV)", each with a small source dropdown beneath reading "FantasyPros".
Below, a results panel with three count tiles — "IMPORTED 312", "RESOLVED 289",
"UNRESOLVED 23" — the unresolved count in amber. Beneath that, a progress section: label
"Computing distributions", a horizontal accent progress bar about 40% filled, muted text
"125 / 312 players". At the bottom, an "Unresolved players" table with columns Name, Team,
Position, Reason and an amber left border, showing rows like "Cam Skattebo · ARI · RB ·
No canonical match".

**Settings.** Single column, max 720px, left-aligned. Section "Connection": a
password-style "API token" input with a Save button, and a status row with a small green
dot: "Connected · database ready · seasons 2023–2025". Section "Scoring": a segmented
control — Standard, Half PPR, Full PPR — with Half PPR selected in the accent, and muted
helper text "Changing this recomputes every player's distribution."

**Warming state.** A centered panel on the dark background. Heading "Waking the server
up…", an indeterminate accent progress bar, muted body "The API sleeps when idle to stay
on the free tier. This only happens on the first load." Behind and below, four skeleton
player cards using the list card geometry, every text and chart region replaced by a dim
rounded grey block with a subtle shimmer.

**Empty state.** Centered: a muted outline icon, heading "No projections yet", body
"Import a stat projection CSV to get started", and a primary accent button "Go to Import".

**Error state.** An inline bordered card with an amber left edge and a warning icon, bold
line "Not enough history to model", muted body "Only 2 career games found. This player
needs at least 4."

### A.4 Content pack

| Player | Pos | Team | Proj (pts/g) | ADP | Floor | Median | Ceiling |
|---|---|---|---|---|---|---|---|
| Jalen Hurts | QB | PHI | 23.1 | 18.6 | 13.4 | 22.5 | 34.1 |
| Lamar Jackson | QB | BAL | 22.4 | 21.2 | 12.9 | 21.8 | 33.0 |
| Saquon Barkley | RB | PHI | 17.8 | 1.4 | 8.2 | 16.9 | 29.4 |
| Bijan Robinson | RB | ATL | 15.7 | 2.4 | 7.1 | 14.8 | 26.3 |
| Ja'Marr Chase | WR | CIN | 14.2 | 1.2 | 5.6 | 13.2 | 24.6 |
| Justin Jefferson | WR | MIN | 13.0 | 3.8 | 5.1 | 12.1 | 22.9 |
| CeeDee Lamb | WR | DAL | 11.6 | 5.1 | 4.4 | 10.8 | 20.7 |
| Brock Bowers | TE | LV | 9.2 | 14.3 | 3.2 | 8.5 | 16.8 |

Projected points and stat lines are real, taken from `tests/fixtures/fantasypros_*.html`.
ADP and the floor/median/ceiling columns are illustrative placeholders shaped to match the
engine's output (right-skewed, long upper tail) — not ground truth.

### A.5 Out of scope for the visual design

No draft board, roster, lineup, or matchup views. No player comparison, tier badges, or
boom/bust and consistency grades. No news feed, no login screen, no phone layout, no
scoring rule editor beyond the three-way preset control. Discard generated screens for any
of these — they are deferred scope, and designing them pulls implementation off-plan.

### A.6 What carries over, and what does not

Carry over: layout, spacing rhythm, type scale, color token values, card anatomy, chart
proportions, and the state treatments. Rebuild rather than paste: the components
themselves, as the §6 React pieces — especially `Sparkline`, which must be data-bound to
real histogram bins.
