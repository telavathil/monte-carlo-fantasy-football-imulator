# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-04-18
- **Deciders:** Tobin Elavathil

## Context and Problem Statement

This project has a detailed Requirements Specification (v1.2) but no running code yet. Architectural choices made during MVP brainstorming — hosting, data source libraries, scoping cuts — have been discussed conversationally. Conversational context decays and is invisible to future contributors (including future-self). We need a durable record of *why* each load-bearing choice was made, separate from *what* the code does.

## Decision Drivers

- The requirements doc describes ambitious scope; the implementation will make many reducing decisions. Each reduction needs a record.
- Solo-developer project today; the choice of format should stay lightweight.
- Must survive `grep` and code review. No proprietary tooling.

## Considered Options

1. **MADR 3.0** — structured Markdown with named sections (Status, Context, Drivers, Options, Outcome, Consequences).
2. **Nygard's original lightweight ADR** — free-form Markdown with `Context`, `Decision`, `Consequences`.
3. **Comments in code / commit messages only** — no separate ADR documents.
4. **A wiki or Notion page** — external from the repo.

## Decision Outcome

**Chosen: MADR 3.0**, stored as `docs/adr/NNNN-slug.md`, with an index in `docs/adr/README.md`.

### Consequences

- **Good:** structure is explicit (Decision Drivers force articulation of *why*; Consequences force articulation of *tradeoffs*). Widely recognized format. Tooling exists (adr-tools, VS Code extensions) if needed later.
- **Good:** ADRs live in the repo, travel with the code, survive forks and clones.
- **Good:** Spec documents can cross-link to ADRs for each load-bearing decision without restating the reasoning.
- **Bad:** slightly more ceremony than Nygard's original. Worth the clarity.

## More Information

- [MADR](https://adr.github.io/madr/)
- [adr.github.io](https://adr.github.io/) — ADR community hub.
