# WDG Proposals Dashboard

Static site, deployed via Spacefast from this repo. Two pages:

- `index.html` — partner-facing status overview. Sanitized: no owner names, pricing, or internal notes.
- `internal/index.html` — full internal detail: owners, dates, notes, this week's tasks, open decisions.
  Not password-protected. Treat the link as "unlisted," not "private."

## How this gets updated

Both pages are generated from the same data that drives `WDG_Proposals_In_Flux.xlsx`.

1. Updates the shared tracker state (`state.json`, not committed here).
2. Regenerates `index.html` and `internal/index.html` from it.
3. Pushes the regenerated HTML to this repo's default branch.

A push to the default branch triggers a Spacefast rebuild automatically (if auto-deploy is on in the
Space's Build settings). No manual redeploy step should be needed.

