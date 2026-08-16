# Development Agent Contract

## Purpose

A development agent improves one private deck-agent pair through bounded,
measurable experiments. It is not the battle-time agent and has no authority to
change or promote the active submission.

## File Ownership

The worker may write only inside its assigned directory under
`sub-agents/specialists/`. It must never modify:

- `sample_submission/sample_submission/main.py`
- `sample_submission/sample_submission/deck.csv`
- another specialist directory
- shared benchmark policy, schemas, or tournament results
- the root `PROGRESS.md`

Shared files may be read for context. Changes to shared tooling require the
Plan_2 coordinator.

## Experiment Rules

1. Begin from the current accepted private `main.py`.
2. State one concrete gameplay weakness and a falsifiable hypothesis.
3. Prefer one strategic mechanism per experiment.
4. Snapshot the accepted implementation before editing.
5. Keep a syntactically valid, self-contained battle agent.
6. Run configured validation and benchmark stages.
7. Record sample sizes, seeds, failures, confidence intervals, and comparison
   tests. Do not report only the favorable summary statistic.
8. Run ablations before attributing a bundled gain to one mechanism.
9. Check at least the configured cross-deck opponents before accepting a gain.
10. Record rejected experiments; do not silently erase negative evidence.
11. Stop when the configured experiment or runtime budget is reached.

## Human Review Gates

- `AUTOMATIC`: static checks, smoke games, benchmarks, trace extraction, and
  report generation may run automatically.
- `REVIEW_REQUIRED`: strategic behavior changed materially or evidence is
  ambiguous. The worker pauses before accepting the candidate.
- `PROMOTION_REQUIRED`: entering the final promotion process always requires
  explicit human approval.

## Independent AI Review Assignment

Human-review packs may be reviewed by a separate AI reviewer before the human
makes a final call. The reviewer must not be the same model family that authored
the candidate:

- Codex-authored experiments are assigned to Opus/Claude review.
- Opus/Claude-authored experiments are assigned to Codex review.
- Unmapped providers default to Codex review until explicitly configured.

The assigned reviewer may recommend `approve`, `reject`, or `more evidence`,
but must not edit the candidate, run promotion, or grade its own work. The final
gate command remains explicit and auditable.

The continuous scheduler may apply a clear independent AI screening review by
calling the same auditable gate commands. `MORE_EVIDENCE` pauses the job instead
of looping. Final private acceptance and active submission promotion still
require separate explicit human-controlled actions.

## Acceptance Standard

An accepted experiment must:

- pass syntax, import, action-validity, timeout, and crash checks available in
  the configured environment;
- show a practically meaningful result under the shared benchmark policy;
- use the configured statistical comparison rather than CI-overlap eyeballing;
- avoid an unacceptable cross-deck or runtime regression; and
- include enough evidence for another worker to reproduce the result.

No specialist can declare itself the overall winner. Only the central,
seat-balanced tournament can rank deck-agent pairs for promotion.

## Coding-Provider Boundary

Codex, Claude Code, and Antigravity/Gemini are invoked only through the shared
worker controller. The provider receives a disposable copy of the active
experiment candidate and copied context. It may change only the root `main.py`.
It must not run benchmarks, modify the deck, edit context, access parent
directories, or promote a candidate. The controller imports the output only
after checking the provider exit, timeout, changed-file boundary, deck validity,
and Python interface. Provider output is evidence for an experiment, not an
acceptance decision.
