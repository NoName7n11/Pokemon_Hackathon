# Competition Data Retention and Deletion Checklist

## Status

Current status: retain pending final manual rules review. No automated deletion
has been performed. No deletion deadline is asserted because the official rules
page did not expose one in machine-readable form on 2026-08-14.

## Inventory

| Data class | Representative locations | Current action |
|---|---|---|
| Competition card and deck data | `dataset/`, `Decs/`, `No_Name_Decks/` | Retain pending rules review |
| Competition simulator and SDK | `sample_submission/sample_submission/cg/` | Retain pending rules review |
| Raw battle and matchup output | `plan_1/artifacts/phase*/`, sub-agent result directories | Retain through judging and reproducibility window |
| Derived trajectories and replay corpora | `plan_1/artifacts/trajectories/` | Retain through judging; review whether derived data is in scope |
| Learned checkpoints | `plan_1/artifacts/checkpoints/`, Phase 8/10 checkpoint directories | Retain through judging; review whether derived models are in scope |
| Aggregate reports and manifests | `plan_1/artifacts/reports/`, `plan_1/artifacts/manifests/`, Phase 12 archive | Preserve if rules permit; these support the report claims |
| Submission packages | active submission and `plan_1/artifacts/phase11/` | Retain through final validation and judging |
| External card images | `Pokemon_Dataset` outside this repository | Review separately under its source/license terms |

## Before Strategy submission

- [ ] Open the current Simulation and Strategy rules while signed in.
- [ ] Record the exact rule version or retrieval date.
- [ ] Record any mandatory deletion trigger, deadline, and data categories.
- [ ] Confirm whether derived trajectories, checkpoints, and aggregate reports
  are included in the deletion requirement.
- [ ] Confirm whether winning teams have longer solution-transfer or audit
  retention duties.
- [ ] Confirm licenses for external deck lists, card images, notebooks, and code.
- [ ] Remove credentials, private tokens, browser state, and unrelated personal
  files from every submission/report artifact.
- [ ] Verify the final Strategy report contains no opponent hidden data or
  private participant information.

## At competition close or organizer notice

- [ ] Re-read the final rules because organizers may update the timeline.
- [ ] Freeze a final inventory with file counts, byte counts, and SHA-256 hashes.
- [ ] Separate files that must be deleted from files explicitly permitted for
  research, audit, or solution-transfer retention.
- [ ] Back up only material that the rules permit retaining.
- [ ] Delete in-scope raw data, copies, temporary files, caches, and archives.
- [ ] Delete or retrain derived checkpoints if the rules place them in scope.
- [ ] Verify deletion by rescanning every listed path and external storage.
- [ ] Record completion date, operator, rule clause, deleted categories, and
  verification result in a new append-only progress entry.

## Safety rule

Do not run a broad recursive deletion from this checklist. Resolve and inspect
every target against the final rule clause first. Deletion should be explicit,
recoverable where practical, and independently verified.

Official pages to review:

- https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/overview/description
- https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/rules
- The linked Pokemon TCG AI Battle Challenge Strategy rules page available to
  the signed-in competition account.
