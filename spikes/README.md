# Validation Spikes

Six pre-implementation spikes validate assumptions in the MVP design spec §9.

## Setup

```bash
python3 -m venv spikes/.venv
spikes/.venv/bin/pip install -r spikes/requirements.txt
```

## Running a spike

```bash
cd spikes/<id>-<slug>
../.venv/bin/python <script>.py
```

Each spike produces a `report.md` with pass/fail verdict. `GATING.md` at the top level rolls up.

## Spike directory

| ID | What it validates | Kill criterion |
|---|---|---|
| A1 | Skew-normal fits NFL weekly stats | <50% of (player, stat) pairs show acceptable Q-Q |
| A2 | Mean-shift produces calibrated intervals | Coverage <60% or >95% |
| B1 | Tier 1+3 identity resolution hit rate | <80% resolved |
| B2 | One HTML parser handles QB/RB/WR/TE | Any position needs a 4th strategy |
| C1 | Fly deploy within 512 MB + free credit | Peak RAM >512 MB or cost >$10/mo |
| C2 | `simulate_player` <200 ms on Fly-sized compute | p95 >1 s even at n=1000 |

See [spec §9](../docs/superpowers/specs/2026-04-18-mc-ff-simulator-mvp-design.md) for full detail.
