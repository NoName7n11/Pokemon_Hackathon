# Independent Review Prompt

Review the candidate as a gameplay decision system, not only as a win-rate
number. Confirm that the experiment evidence matches its claimed mechanism.

You are the assigned independent reviewer. Do not edit the candidate, do not run
promotion, and do not review work authored by the same model family. If the
review pack says the candidate was implemented by Codex, Opus/Claude reviews it.
If it was implemented by Opus/Claude, Codex reviews it.

Inspect representative differences in attacks, retreats, promotions, energy
attachments, evolutions, trainer sequencing, ignored lethal attacks, unusually
slow decisions, and losses. Choose one outcome:

- `APPROVED`: evidence and gameplay behavior justify accepting the candidate.
- `REJECTED`: behavior or measurement does not justify acceptance.
- `MORE_EVIDENCE`: request a named ablation, matchup, trace, or fresh-seed run.

Approval accepts a private specialist version. It does not authorize submission
promotion.
