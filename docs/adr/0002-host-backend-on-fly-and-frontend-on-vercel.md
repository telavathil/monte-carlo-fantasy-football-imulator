# ADR-0002: Host backend on Fly.io, frontend on Vercel

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

The MVP must be deployed from day one on free-tier infrastructure. The requirements doc assumes a long-running Python backend (FastAPI + NumPy/SciPy for Monte Carlo) plus a React frontend. We need to pick where each runs.

## Decision Drivers

- Free-tier friendly, no credit-card surprises.
- Python backend with NumPy/SciPy available; not a serverless function constrained to 10s timeouts (Monte Carlo simulations run 100ms–several seconds; a Vercel Python Function's 10s cap is a near-miss that will bite).
- Simple deploy — solo developer, no ops team.
- Persistent disk for SQLite and an `nflreadpy` Parquet cache.
- No WebSocket requirement in MVP, so platforms without WebSocket support are fine for now.

## Considered Options

1. **Fly.io (backend) + Vercel (frontend)** — two hosts. Fly runs Python as a long-lived VM with a mounted volume; Vercel serves the static React build.
2. **Fly.io only** — one host. Fly serves both API and static React bundle.
3. **Vercel only, Python serverless** — 10s timeout per request forces trimmed simulation counts and tight latency budgets.
4. **Vercel only, client-side TypeScript simulation** — port the entire sim engine to TypeScript; Vercel handles only data + static assets.
5. **AWS Lambda + RDS** — 15-minute timeout solves compute; heavier ops and a 12-month-limited free tier.
6. **Railway / Render / Modal** — similar category to Fly; evaluated but less popular and / or more limited free tiers than Fly.
7. **All AWS (EC2 + RDS free tier)** — most flexible, most ops burden, 12-month expiry.

## Decision Outcome

**Chosen: Fly.io (backend) + Vercel (frontend)**. Fly runs a `shared-cpu-1x` VM with a 1 GB persistent volume; Vercel serves the static React build with `VITE_API_URL` pointing at the Fly hostname.

### Consequences

- **Good:** keeps Python + NumPy/SciPy architecture intact (matches Requirements v1.2). No serverless timeout pressure — simulations can run as long as they need.
- **Good:** Fly `shared-cpu-1x` + 1 GB volume falls within Fly's current $5/month free credit at single-user scale.
- **Good:** Vercel's deploy ergonomics (preview per branch, `git push` → deploy) retained for the frontend.
- **Good:** forever-free-tier-ish (unlike AWS's 12-month limit).
- **Bad:** two deploy targets and two sets of env vars to manage.
- **Bad:** a small monthly bill could appear if Fly usage exceeds free credit. Mitigation in spec Risk R3: `fly scale count 0` when not in use; periodic billing check.
- **Bad:** if WebSockets or long background jobs become required later, Fly handles them fine but we'd need to revisit whether Vercel still fits the frontend-only role.

## More Information

- [Fly.io pricing](https://fly.io/docs/about/pricing/)
- [Vercel Hobby plan limits](https://vercel.com/docs/limits/usage)
- Supersedes: none.
- Related: [ADR-0006](0006-sqlite-on-fly-volume-with-nflreadpy-cache.md) (storage), [ADR-0007](0007-single-bearer-token-auth.md) (auth over public URLs).
