# ADR-0007: Auth — single bearer token, no user accounts

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

The API and frontend deploy to public URLs (`*.fly.dev`, `*.vercel.app`). Without any access control, anyone who discovers the URL can read projections, trigger imports, or refresh historical data. We need *some* barrier. The MVP has exactly one user (the author), so full per-user auth is overkill.

## Decision Drivers

- Zero multi-user requirements in MVP.
- Avoid running an identity provider, issuing refresh tokens, or managing sessions.
- Must be trivially rotatable if leaked.

## Considered Options

1. **No auth, public URL.**
2. **HTTP basic auth** — browser prompt, shared user/password.
3. **Single bearer token** — static `API_TOKEN` env var; client sends `Authorization: Bearer $TOKEN`.
4. **Full per-user auth** — OAuth / JWT / sessions.
5. **VPN / Tailscale only** — no public access at all.

## Decision Outcome

**Chosen: Option 3 (single bearer token).**

- `API_TOKEN` is set on the backend via `fly secrets set API_TOKEN=<random>`.
- The matching token is set on Vercel as `VITE_API_TOKEN`, baked into the frontend bundle at build time.
- A FastAPI dependency checks `Authorization: Bearer <token>` on every route except `/api/health`.
- Token rotation: set new secret on Fly + redeploy; set same value on Vercel + redeploy. ~1 minute.

### Consequences

- **Good:** one line of middleware; no user table, no login page, no sessions.
- **Good:** rotating the token is trivial and invalidates all prior access immediately.
- **Good:** `/health` remaining public simplifies external monitoring.
- **Bad:** the token is shipped to the browser and visible in the JS bundle. Anyone who loads the Vercel site can read it with DevTools. Acceptable because the only "user" is the author and the site isn't advertised.
- **Bad:** no audit trail of *who* did something — there's only one actor by design.
- **Bad:** if the project ever adds a second user, this has to be replaced wholesale. A new ADR supersedes this one at that time.

## More Information

- Related: [ADR-0002](0002-host-backend-on-fly-and-frontend-on-vercel.md) (public URLs created the need for auth in the first place).
