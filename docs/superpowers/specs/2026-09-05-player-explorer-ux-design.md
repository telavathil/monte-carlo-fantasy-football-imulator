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
| `p25` | Float | |
| `median_p50` | Float | |
| `p75` | Float | |
| `ceiling_p90` | Float | |
| `mean` | Float | |
| `std` | Float | |
| `skewness` | Float | Empirical skewness of the simulated sample — see §4 |
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
{ "floor_p10": 5.6, "p25": 9.0, "median_p50": 13.2, "p75": 18.4, "ceiling_p90": 24.6,
  "skewness": 0.62, "histogram": {"bin_edges": [...], "counts": [...]},
  "computed_at": "..." }
```

`p25` and `p75` exist because the detail chart flags five percentiles, not three. They
cost one additional `numpy.percentile` call on a sample array already in memory.

`skewness` needs care. The Stitch design labels this `Normal Skew (α=1.18)`, implying a
single shape parameter for the outcome distribution. **No such parameter exists.** Fitting
is per-stat: each stat gets its own family and its own parameters (skew-normal `a` for
continuous yardage, negative-binomial for counts), and the points distribution is the
scored convolution of all of them. There is no global α to report. What we report instead
is the *empirical* skewness of the simulated points sample — one `scipy.stats.skew` call
on the array the runner already produces. Label it in the UI as "Sample skew", never as a
fitted shape parameter.

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
- **Resolved:** token values are fixed by the completed Stitch pass — see Appendix B.
  The design system is `terminal_slate_2` (amber primary, violet secondary).
- **The Stitch screens depict features that do not exist.** Roughly a third of the visible
  surface area is fabricated. Appendix B triages every element into adopt / discard.
  Implementing the screens as drawn would ship false claims about the model.

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

---

## Appendix B — Stitch output: tokens and triage

The Stitch pass is complete. Export: `docs/stitch_mc_sim_fantasy_analytics.zip` (7 screens,
`code.html` + `screen.png` each, plus two design systems). Stitch project
`projects/1837465920748163198`, reachable live via the Stitch MCP connection.

**The chosen design system is `terminal_slate_2`** — amber primary, violet secondary.
`terminal_slate_1` (cyan primary) is the rejected variant and should be ignored.

### B.1 Token set

| Role | Value |
|---|---|
| Canvas / background | `#0B0E14` |
| Card / panel | `#151A23` |
| Elevated (tooltip, dropdown, sticky header) | `#1C2330` |
| Inset well (chart plot area, input field) | `#18202C` |
| Border hairline | `#232A36` |
| Border interactive (hover, focus) | `#3E4C5E` |
| Text primary | `#F1F5F9` |
| Text muted | `#7A8699` |
| Text ghost | `#475569` |
| **Accent primary (amber)** | `#FBBF24` |
| **Accent secondary (violet)** | `#818CF8` |
| Warning / unresolved | `#F59E0B` |
| Error | `#EF4444` |
| Success / connected | `#10B981` |

Type: **Plus Jakarta Sans** for headings (700/600, tracking -0.02em to -0.03em), **Inter**
for body and all numerics. Every numeric value uses `font-variant-numeric: tabular-nums`.
`label-caps` is Inter 10px/600, uppercase, tracking 0.06em, in `#7A8699`.

Radii: 4px base controls, 6-8px panels and containers, 0 on table cells, 2px on position
badges. Elevation is tonal layering plus 1px hairlines — no drop shadows.

Two inconsistencies to settle during implementation, since the export disagrees with
itself: the active nav pill renders cyan `#38BDF8` on six screens but amber on the
Players list; and the position badge palette in `terminal_slate_1`'s DESIGN.md
(QB cyan / RB green / WR amber / TE violet) does not match what the screens render
(QB blue / RB cyan / WR amber / TE green). Pick one of each and apply it uniformly.

### B.2 Adopt

- **Player card anatomy** on the list: avatar initials, name, position badge, muted
  `POS · TEAM · ADP` line, centered distribution curve with median marker and shaded
  p10-p90 band, large amber points value with `PTS / GAME` beneath, and a footer row of
  `FLOOR · MEDIAN · CEILING`. This is exactly the design intent.
- **Color-coded position badges.** Not in the brief; a genuine improvement for scanning.
- **Three stat tiles** on the detail page, with the median tile emphasized in amber.
- **The large distribution chart**: histogram bars with a PDF curve overlaid, percentile
  flags along the top, shaded confidence band, x-axis labelled in points per game.
- **Projected Stats table** with humanized labels and right-aligned tabular figures.
- **Calibration Note** as a bordered callout — *minus its final sentence*, see B.3.
- **Warming panel** copy and layout. The headline and body text came straight from the
  brief and survived intact.
- **Import screen skeleton**: dual drop zones, three count tiles, the progress bar, and
  the unresolved table.

### B.3 Discard — depicts features that do not exist

Grouped by severity. The first group is not cosmetic: shipping it would tell the user the
model does things it does not do.

**Actively false claims about the model**

| Element | Why it must not ship |
|---|---|
| Calibration Note: "Historical correlation coefficients factor Burrow passing volume dynamics" | Directly contradicts Requirements v1.2 §10.3 — simulations assume independence. There is no correlation modeling. |
| `ENGINE TELEMETRY` → "Covariance Shift ±14.2% Norm" | Same. Implies a covariance matrix that does not exist. |
| `Correlations` nav tab | Correlation modeling is a *Phase 5* candidate, not built. |
| `MODEL FIT R² 0.941` | No R² is computed anywhere. |
| `Convergence: ±0.08 pts error` | No convergence diagnostics exist. |
| Import copy: "correlated boom/bust variance", "correlations bound" | Same independence violation. |

**Deferred features drawn as if built**

`TIER 1` badge · `BOOM / BUST 38.2% / 6.1%` · `Target Share 28.4%` (not in the stat
vocabulary at all) · `Est. ~4.2 rec · 35 yds` conditional floor line · "Multi-TD upside
trigger" · `Simulation` nav tab · unresolved-table action buttons (`Match player…`,
`Batch Auto-Map`, `Resolve position…`, `Ignore Remainder`) — §1 non-goals make the
unresolved view read-only · `Revert Last` / `Re-run Full Sync`.

**Fabricated telemetry and chrome**

`Engine Ready 0.14ms` and `Engine latency 0.14ms` — the measured p50 is **179ms**, three
orders of magnitude off · `NODE_AWS_EUC1 #084` — deployment is Fly.io, not AWS ·
`HTTP 204 Waiting` — a cold boot is a hanging connection, not a 204 · `Est. 4-8s` — the
real cold boot is 15-25s · `WASM SIMD: Inactive`, `RNG Xoroshiro128+`, `BATCH SIZE 256`,
`Seed Digest`, `Sample Pool 10,000 Vectors`, `Worker Threads: 8/8 Active`,
`Estimated Time Remaining: 00:03.4s` — simulation runs server-side in NumPy/SciPy;
none of this exists · `Schema Version v2.4.2-rel`, `Session ID`, `V2.4` badge ·
user avatar — single-user bearer token, there is no user concept · the design-system
banner across the top of the Players list ("Tri-Zone Architecture · Topaz Amber…"),
which is Stitch narrating itself inside the mock · `SIM CONTROLS` sidebar's
`Variance Range ±14.2%` — no such parameter exists.

### B.4 Cheap additions worth considering

Not in the approved scope. Each is small, and the design already assumes it — decide
before planning rather than during.

| Addition | Cost |
|---|---|
| P25 / P75 alongside P10 / P50 / P90 | Trivial — same sample array, one more percentile call. Makes the chart's percentile flags real. |
| Surface the skew-normal shape parameter (the design shows `Normal Skew α=1.18`) | Already fitted and stored in `player_distribution_params`; only needs adding to the response. |
| An iterations control bound to the existing `n` query param (100-20,000) | The `SIM CONTROLS` sidebar is otherwise fiction, but `n` is real. Precomputed summaries would still use a fixed `n`. |

**Decision:** P25/P75 and the skew readout are **adopted** and folded into §3 and §4
above. The iterations control is **not** — so the `SIM CONTROLS` sidebar is dropped in
full, and the Players and detail screens reclaim that 320px column. The skew readout ships
as empirical sample skew, not as the fitted `α` the design depicts; see §4.
