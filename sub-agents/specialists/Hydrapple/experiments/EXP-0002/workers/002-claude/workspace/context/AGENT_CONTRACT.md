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

