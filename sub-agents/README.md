# Plan 2 Specialist Workspace

This directory contains isolated development agents for deck-specific `main.py`
experiments. A specialist is a private deck-agent pair. Nothing under this
directory is an active Kaggle submission.

## Safety Boundary

- Specialists may edit only their own directory.
- Shared tools may read the active submission as a baseline, but specialists
  never write to it.
- Tournament entry and submission promotion require separate human approval.
- `registry.json` is the inventory of created specialists.

## Create a Specialist

From the repository root:

```powershell
python sub-agents/shared/tools/create_specialist.py `
  --deck Decs/Hydrapple.csv `
  --provider codex
```

Use `--name` when the desired specialist name differs from the deck filename.
The command refuses to overwrite an existing specialist.

## Validate a Specialist

```powershell
python sub-agents/shared/tools/validate_agent.py `
  sub-agents/specialists/Hydrapple
```

Static validation does not require the competition engine. Add `--runtime` to
verify the private module against the ignored local `cg` package under the
submission directory; that package must be present on the machine.

## Run a Bounded Experiment

```powershell
python sub-agents/shared/tools/run_experiment.py start `
  --specialist Hydrapple `
  --hypothesis "Prefer the prepared attacker after a knockout" `
  --mechanism promotion_scoring
```

Edit only the printed `experiments/EXP-XXXX/candidate/main.py`, then run a
bounded benchmark:

```powershell
python sub-agents/shared/tools/run_experiment.py run `
  --specialist Hydrapple --stage smoke
```

Finish with an explicit human decision:

```powershell
python sub-agents/shared/tools/run_experiment.py decide `
  --specialist Hydrapple --reject --reason "No measurable improvement"
```

The accepted specialist files are untouched until `decide --accept`. One active
experiment is allowed per specialist, and every benchmark runs in a subprocess
with a configured timeout and preserved logs.

## Run a Coding Provider

Inspect the configured local providers:

```powershell
python sub-agents/shared/tools/run_worker.py providers
```

After starting an experiment, preview the exact isolated invocation without
calling a model:

```powershell
python sub-agents/shared/tools/run_worker.py run `
  --specialist Hydrapple --provider codex --dry-run
```

Remove `--dry-run` to invoke the provider. The worker receives a disposable copy
of the candidate and copied context. Only a syntactically valid `main.py` is
imported back, and only when the provider changed no protected workspace file.
Worker invocations are capped per experiment and by wall-clock timeout.

`antigravity` currently resolves to the installed Gemini CLI backend. The local
Antigravity desktop installation does not expose a headless PATH command, so the
resolved backend is recorded explicitly in every run rather than presented as
the desktop application.

## Run One Bounded Worker Cycle

The orchestrator combines experiment creation, one provider invocation, smoke,
screening, and the human-review stop:

```powershell
python sub-agents/shared/tools/orchestrate.py run `
  --specialist Hydrapple `
  --provider codex `
  --hypothesis "One Energy attachment should prefer a target it makes attack-ready" `
  --mechanism attack_readiness_attachment `
  --expected-effect "Fewer attachments that leave every attacker unusable"
```

Provider, engine, timeout, illegal-action, or clear screening failures are
automatically rejected and archived. A surviving candidate is placed in
`human-review/pending/` with its benchmark evidence, unified code diff, and a
bounded decision-difference trace. The trace evaluates the frozen baseline on
the same observations seen by the candidate and records where their choices
differ. Only the candidate choice advances the game, so this is behavior-review
evidence rather than a counterfactual win-rate estimate.

Review packs are assigned to an independent AI reviewer by default. A Codex
worker is reviewed by Opus/Claude; an Opus/Claude worker is reviewed by Codex.
The assignment is recorded in both the pending `.json` and `.md` review files.

List the current review queue:

```powershell
python sub-agents/shared/tools/review_queue.py list
python sub-agents/shared/tools/review_queue.py list --reviewer codex
python sub-agents/shared/tools/review_queue.py list --reviewer opus
```

Human approval after screening authorizes deep evaluation, not acceptance:

```powershell
python sub-agents/shared/tools/review_gate.py approve `
  --specialist Hydrapple --reason "Diff matches the hypothesis"
```

Rejecting the review closes the experiment. Neither action promotes anything to
the active Kaggle submission, and approval does not accept the private candidate.

Running a real coding provider may transmit the isolated candidate and copied
project context to that provider. Dry runs and local fixture tests do not. Obtain
explicit human authorization for that transmission before removing the dry/local
test boundary.

## Run the Central Tournament

The tournament loads each specialist's private `main.py` together with its own
`deck.csv`, alternates first player, and runs every selected pairing in both seat
orientations:

```powershell
python sub-agents/shared/tools/run_tournament.py `
  --specialist Hydrapple `
  --specialist Claude_Grass_Venusaur `
  --games-per-seat 300
```

Only specialists in `READY_FOR_EXPERIMENT` may enter. Every run is stored under
`sub-agents/tournaments/results/` with an immutable entrant manifest, pair-level
JSON and logs, a matchup matrix, aggregate ranking, and Markdown report. Ranking
puts fault-free execution before field win rate, worst matchup, and mean decision
time. The result names a provisional champion only; `auto_promote` is always
false and this command never writes to the active submission.

`sub-agents/tournaments/REPORT.md` is the append-only tournament history. Each
completed tournament is added once using its unique tournament ID; existing
entries are never regenerated or overwritten. The ledger records code/deck hash
changes and observed rank and win-rate deltas against the most recent run with
the same field. Deltas are labeled directly comparable only when the entrant
field and games per seat match. The detailed report inside each unique result
directory remains the authoritative snapshot for that run.

Small game counts are useful for testing infrastructure but are not sufficient
evidence for choosing a submission. Use the configured 300 games per seat for a
real two-pair comparison and increase the field before making generalization
claims.

## Run Continuous Specialist Research

The persistent scheduler consumes explicit, narrow hypotheses. It can run up to
five different specialists concurrently, but only one experiment per specialist.
Configured provider ceilings allow two Codex jobs and three Claude jobs at once;
Antigravity/Gemini may use one otherwise available global slot:

```powershell
python sub-agents/shared/tools/continuous_scheduler.py enqueue `
  --specialist Hydrapple `
  --provider codex `
  --hypothesis "Narrow behavior to test" `
  --mechanism narrow_mechanism `
  --expected-effect "Observable decision change" `
  --authorize-provider

python sub-agents/shared/tools/continuous_scheduler.py run
```

Live provider jobs transmit the isolated private `main.py`, `deck.csv`, and
copied specialist/rules context to the selected external coding provider. This
requires explicit source-egress authorization. A staged blocked job can be
authorized only after that disclosure:

```powershell
python sub-agents/shared/tools/continuous_scheduler.py authorize `
  --job JOB-00001 --acknowledge-source-egress
```

Use `status` to inspect every queued/running/review/terminal job. Use `stop` for
a graceful shutdown; current bounded child processes finish before the scheduler
exits. The scheduler enforces a five-specialist global cap, per-provider limits,
a six-new-job daily cap, unique specialist locks, process logs, append-only
history, and fresh stored seeds. A full provider queue does not prevent another
provider from using its available capacity.

The evidence path is `20 smoke -> 200 screening -> human review -> 300 main ->
500 confirmation -> 200 cross-deck games per opponent -> final human review`.
Failures and clear regressions may be rejected automatically. Screening review
packs are now sent to the assigned independent AI reviewer automatically when
`auto_ai_review` is enabled. A clear AI `REJECT` closes the experiment through
`review_gate.py reject`; a clear `APPROVE_DEEP_EVALUATION` authorizes the 300
and 500 game deep path through `review_gate.py approve`; `MORE_EVIDENCE` moves
the job to `waiting_more_evidence` and stops the loop for that experiment.

You can run the reviewer tool manually when needed:

```powershell
python sub-agents/shared/tools/auto_review.py `
  --specialist Fire --apply-gate
```

Private acceptance still uses the separate `review_gate.py accept` command and
requires confirmation plus two cross-deck opponents. Nothing in this scheduler
promotes the active submission.

### Campaign Backlogs

A specialist can be kept active through an explicit campaign backlog under
`sub-agents/continuous/campaigns/`. Each campaign contains ordered, narrow
hypotheses. The scheduler enqueues the next pending hypothesis only when that
specialist is idle and `READY_FOR_EXPERIMENT`, so it never runs two experiments
for one deck at the same time.

The current Grass campaign is:

```text
sub-agents/continuous/campaigns/Grass.json
```

It uses Claude Opus for the No_Name_Grass specialist and still passes through
the same smoke, screening, independent AI review, deep-evidence, and final human
gates. A campaign keeps work moving; it does not lower the evidence bar.

## Run Controlled Promotion

Phase 6 is a separate four-step lifecycle. A request is created only when a
privately accepted specialist is the fault-free winner of a tournament with at
least three entrants and 300 games per seat:

```powershell
python sub-agents/shared/tools/promote_candidate.py request `
  --specialist Hydrapple `
  --tournament T-YYYYMMDD-HHMMSS-XXXXXX `
  --reason "Powered tournament winner"

python sub-agents/shared/tools/promote_candidate.py approve `
  --promotion PROM-0001 `
  --reviewer human `
  --reason "Evidence and exact hashes reviewed" `
  --acknowledge-submission-change

python sub-agents/shared/tools/promote_candidate.py execute `
  --promotion PROM-0001
```

Execution snapshots the current submission, atomically copies `main.py` and
`deck.csv`, validates and imports the result, runs complete-pair smoke games and
the package benchmark from the real submission directory, and writes a manifest.
Any failure restores the snapshot. A successful promotion can be explicitly
rolled back with `rollback --acknowledge-rollback`. Promotion history is
append-only under `sub-agents/promotion/REPORT.md`.

Use `verify_platform.py` to audit all implemented phase invariants and append a
verification result under `sub-agents/verification/`.

## Current Scope

The current platform creates, registers, validates, snapshots, and benchmarks
isolated candidates; invokes bounded Codex, Claude Code, or Gemini-backed worker
cycles; generates human-review packs; ranks complete private deck-agent pairs in
a central tournament; records candidate-versus-baseline decision differences;
and controls submission promotion with snapshots, smoke tests, manifests, and
rollback. A statistically powered multi-specialist tournament and the first
evidence-qualified real promotion remain future work.
