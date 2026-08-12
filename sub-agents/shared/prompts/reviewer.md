# Human Review Prompt

Review the candidate as a gameplay decision system, not only as a win-rate
number. Confirm that the experiment evidence matches its claimed mechanism.

Inspect representative differences in attacks, retreats, promotions, energy
attachments, evolutions, trainer sequencing, ignored lethal attacks, unusually
slow decisions, and losses. Choose one outcome:

- `APPROVED`: evidence and gameplay behavior justify accepting the candidate.
- `REJECTED`: behavior or measurement does not justify acceptance.
- `MORE_EVIDENCE`: request a named ablation, matchup, trace, or fresh-seed run.

Approval accepts a private specialist version. It does not authorize submission
promotion.

