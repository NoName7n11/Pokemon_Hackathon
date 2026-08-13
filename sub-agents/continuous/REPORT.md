# Continuous Specialist Research

Append-only scheduler history. Automatic rejection is allowed; acceptance and submission promotion always require separate human actions.

<!-- JOB-00001:1:enqueued -->
## 2026-08-12T19:51:25.354443+00:00 - JOB-00001

- Specialist: `Hydrapple`
- Provider: `codex`
- State: `queued`
- Event: `enqueued`
- Detail: Awaiting an available specialist slot.
- Hypothesis: When a normal Energy attachment makes an attack usable this turn, apply that readiness preference only to the Active Pokemon; never give the readiness bonus to a Benched target, and preserve the shipped attachment ranking otherwise.

<!-- JOB-00002:1:enqueued -->
## 2026-08-12T19:51:35.186067+00:00 - JOB-00002

- Specialist: `Claude_Grass_Venusaur`
- Provider: `claude`
- State: `queued`
- Event: `enqueued`
- Detail: Awaiting an available specialist slot.
- Hypothesis: For forced promotion and own-board CARD choices after a knockout, prefer an attack-ready Mega Venusaur ex, Hydrapple ex, or Teal Mask Ogerpon ex over support Pokemon when it can immediately deal more usable damage; preserve generic live-attacker scoring outside that narrow choice.

<!-- JOB-00001:2:source_egress_blocked -->
## 2026-08-12T19:53:09.282663+00:00 - JOB-00001

- Specialist: `Hydrapple`
- Provider: `codex`
- State: `awaiting_provider_authorization`
- Event: `source_egress_blocked`
- Detail: No source was sent. Explicit authorization is required to transmit isolated main.py, deck.csv, and copied strategy context to Codex.
- Hypothesis: When a normal Energy attachment makes an attack usable this turn, apply that readiness preference only to the Active Pokemon; never give the readiness bonus to a Benched target, and preserve the shipped attachment ranking otherwise.

<!-- JOB-00002:2:source_egress_blocked -->
## 2026-08-12T19:53:09.298481+00:00 - JOB-00002

- Specialist: `Claude_Grass_Venusaur`
- Provider: `claude`
- State: `awaiting_provider_authorization`
- Event: `source_egress_blocked`
- Detail: No source was sent. Explicit authorization is required to transmit isolated main.py, deck.csv, and copied strategy context to Claude.
- Hypothesis: For forced promotion and own-board CARD choices after a knockout, prefer an attack-ready Mega Venusaur ex, Hydrapple ex, or Teal Mask Ogerpon ex over support Pokemon when it can immediately deal more usable damage; preserve generic live-attacker scoring outside that narrow choice.

<!-- JOB-00001:3:provider_authorized -->
## 2026-08-12T21:51:47.948823+00:00 - JOB-00001

- Specialist: `Hydrapple`
- Provider: `codex`
- State: `queued`
- Event: `provider_authorized`
- Detail: Human explicitly authorized sending the isolated private source/context to codex.
- Hypothesis: When a normal Energy attachment makes an attack usable this turn, apply that readiness preference only to the Active Pokemon; never give the readiness bonus to a Benched target, and preserve the shipped attachment ranking otherwise.

<!-- JOB-00002:3:provider_authorized -->
## 2026-08-12T21:51:48.181004+00:00 - JOB-00002

- Specialist: `Claude_Grass_Venusaur`
- Provider: `claude`
- State: `queued`
- Event: `provider_authorized`
- Detail: Human explicitly authorized sending the isolated private source/context to claude.
- Hypothesis: For forced promotion and own-board CARD choices after a knockout, prefer an attack-ready Mega Venusaur ex, Hydrapple ex, or Teal Mask Ogerpon ex over support Pokemon when it can immediately deal more usable damage; preserve generic live-attacker scoring outside that narrow choice.

<!-- JOB-00001:4:screening_started -->
## 2026-08-12T21:52:00.798893+00:00 - JOB-00001

- Specialist: `Hydrapple`
- Provider: `codex`
- State: `running_screening`
- Event: `screening_started`
- Detail: PID 6148; log C:\Users\novan\Desktop\Projects\Pokemon_Hackathon\sub-agents\continuous\logs\JOB-00001-screening.log.
- Hypothesis: When a normal Energy attachment makes an attack usable this turn, apply that readiness preference only to the Active Pokemon; never give the readiness bonus to a Benched target, and preserve the shipped attachment ranking otherwise.

<!-- JOB-00002:4:screening_started -->
## 2026-08-12T21:52:00.837167+00:00 - JOB-00002

- Specialist: `Claude_Grass_Venusaur`
- Provider: `claude`
- State: `running_screening`
- Event: `screening_started`
- Detail: PID 24284; log C:\Users\novan\Desktop\Projects\Pokemon_Hackathon\sub-agents\continuous\logs\JOB-00002-screening.log.
- Hypothesis: For forced promotion and own-board CARD choices after a knockout, prefer an attack-ready Mega Venusaur ex, Hydrapple ex, or Teal Mask Ogerpon ex over support Pokemon when it can immediately deal more usable damage; preserve generic live-attacker scoring outside that narrow choice.

<!-- JOB-00001:5:screening_failed -->
## 2026-08-12T21:55:31.015873+00:00 - JOB-00001

- Specialist: `Hydrapple`
- Provider: `codex`
- State: `rejected`
- Event: `screening_failed`
- Detail: Process exited with 1.
- Hypothesis: When a normal Energy attachment makes an attack usable this turn, apply that readiness preference only to the Active Pokemon; never give the readiness bonus to a Benched target, and preserve the shipped attachment ranking otherwise.

<!-- JOB-00002:5:screening_complete -->
## 2026-08-12T21:59:01.233414+00:00 - JOB-00002

- Specialist: `Claude_Grass_Venusaur`
- Provider: `claude`
- State: `waiting_screening_review`
- Event: `screening_complete`
- Detail: 20-game smoke and 200-game screening completed; human review required.
- Hypothesis: For forced promotion and own-board CARD choices after a knockout, prefer an attack-ready Mega Venusaur ex, Hydrapple ex, or Teal Mask Ogerpon ex over support Pokemon when it can immediately deal more usable damage; preserve generic live-attacker scoring outside that narrow choice.

<!-- JOB-00002:6:experiment_closed -->
## 2026-08-12T22:00:31.324485+00:00 - JOB-00002

- Specialist: `Claude_Grass_Venusaur`
- Provider: `claude`
- State: `rejected`
- Event: `experiment_closed`
- Detail: Private experiment decision: rejected.
- Hypothesis: For forced promotion and own-board CARD choices after a knockout, prefer an attack-ready Mega Venusaur ex, Hydrapple ex, or Teal Mask Ogerpon ex over support Pokemon when it can immediately deal more usable damage; preserve generic live-attacker scoring outside that narrow choice.

<!-- JOB-00003:1:enqueued -->
## 2026-08-12T23:24:31.482800+00:00 - JOB-00003

- Specialist: `Hydrapple`
- Provider: `codex`
- State: `queued`
- Event: `enqueued`
- Detail: Awaiting an available specialist slot.
- Hypothesis: When a normal Energy attachment makes an attack usable this turn, apply readiness preference only to the Active Pokemon and preserve the shipped ranking for every Benched target.

<!-- JOB-00004:1:enqueued -->
## 2026-08-12T23:24:31.713750+00:00 - JOB-00004

- Specialist: `Fire`
- Provider: `codex`
- State: `queued`
- Event: `enqueued`
- Detail: Awaiting an available specialist slot.
- Hypothesis: When choosing or evaluating attacks for Mega Charizard X ex and Mega Charizard Y ex, estimate their effect-driven damage and required Energy discard instead of treating zero printed damage as zero value; preserve all non-Charizard attack logic.

<!-- JOB-00005:1:enqueued -->
## 2026-08-12T23:24:31.960426+00:00 - JOB-00005

- Specialist: `Grass`
- Provider: `claude`
- State: `queued`
- Event: `enqueued`
- Detail: Awaiting an available specialist slot.
- Hypothesis: When evolving the Chikorita line and no Wild Growth Meganium is already in play, prioritize establishing Meganium card 710 before competing Mega Meganium endpoints; preserve evolution ranking after the energy engine exists.

<!-- JOB-00006:1:enqueued -->
## 2026-08-12T23:24:32.213992+00:00 - JOB-00006

- Specialist: `Dark`
- Provider: `claude`
- State: `queued`
- Event: `enqueued`
- Detail: Awaiting an available specialist slot.
- Hypothesis: For attack choice and immediate attacker scoring, account for Mega Sharpedo ex Hungry Jaws receiving its conditional damage only when Sharpedo is damaged; preserve generic attack ranking for all other Pokemon.

<!-- JOB-00003:2:screening_started -->
## 2026-08-12T23:24:47.973878+00:00 - JOB-00003

- Specialist: `Hydrapple`
- Provider: `codex`
- State: `running_screening`
- Event: `screening_started`
- Detail: PID 12372; log C:\Users\novan\Desktop\Projects\Pokemon_Hackathon\sub-agents\continuous\logs\JOB-00003-screening.log.
- Hypothesis: When a normal Energy attachment makes an attack usable this turn, apply readiness preference only to the Active Pokemon and preserve the shipped ranking for every Benched target.

<!-- JOB-00004:2:screening_started -->
## 2026-08-12T23:24:48.030843+00:00 - JOB-00004

- Specialist: `Fire`
- Provider: `codex`
- State: `running_screening`
- Event: `screening_started`
- Detail: PID 19292; log C:\Users\novan\Desktop\Projects\Pokemon_Hackathon\sub-agents\continuous\logs\JOB-00004-screening.log.
- Hypothesis: When choosing or evaluating attacks for Mega Charizard X ex and Mega Charizard Y ex, estimate their effect-driven damage and required Energy discard instead of treating zero printed damage as zero value; preserve all non-Charizard attack logic.

<!-- JOB-00005:2:screening_started -->
## 2026-08-12T23:24:48.080579+00:00 - JOB-00005

- Specialist: `Grass`
- Provider: `claude`
- State: `running_screening`
- Event: `screening_started`
- Detail: PID 10584; log C:\Users\novan\Desktop\Projects\Pokemon_Hackathon\sub-agents\continuous\logs\JOB-00005-screening.log.
- Hypothesis: When evolving the Chikorita line and no Wild Growth Meganium is already in play, prioritize establishing Meganium card 710 before competing Mega Meganium endpoints; preserve evolution ranking after the energy engine exists.

<!-- JOB-00006:2:screening_started -->
## 2026-08-12T23:24:48.130489+00:00 - JOB-00006

- Specialist: `Dark`
- Provider: `claude`
- State: `running_screening`
- Event: `screening_started`
- Detail: PID 8072; log C:\Users\novan\Desktop\Projects\Pokemon_Hackathon\sub-agents\continuous\logs\JOB-00006-screening.log.
- Hypothesis: For attack choice and immediate attacker scoring, account for Mega Sharpedo ex Hungry Jaws receiving its conditional damage only when Sharpedo is damaged; preserve generic attack ranking for all other Pokemon.

<!-- JOB-00003:3:screening_failed -->
## 2026-08-12T23:28:22.593728+00:00 - JOB-00003

- Specialist: `Hydrapple`
- Provider: `codex`
- State: `rejected`
- Event: `screening_failed`
- Detail: Process exited with 1.
- Hypothesis: When a normal Energy attachment makes an attack usable this turn, apply readiness preference only to the Active Pokemon and preserve the shipped ranking for every Benched target.

<!-- JOB-00004:3:screening_failed -->
## 2026-08-12T23:28:52.701990+00:00 - JOB-00004

- Specialist: `Fire`
- Provider: `codex`
- State: `rejected`
- Event: `screening_failed`
- Detail: Process exited with 1.
- Hypothesis: When choosing or evaluating attacks for Mega Charizard X ex and Mega Charizard Y ex, estimate their effect-driven damage and required Energy discard instead of treating zero printed damage as zero value; preserve all non-Charizard attack logic.

<!-- JOB-00005:3:screening_complete -->
## 2026-08-12T23:31:22.911701+00:00 - JOB-00005

- Specialist: `Grass`
- Provider: `claude`
- State: `waiting_screening_review`
- Event: `screening_complete`
- Detail: 20-game smoke and 200-game screening completed; human review required.
- Hypothesis: When evolving the Chikorita line and no Wild Growth Meganium is already in play, prioritize establishing Meganium card 710 before competing Mega Meganium endpoints; preserve evolution ranking after the energy engine exists.

<!-- JOB-00006:3:screening_complete -->
## 2026-08-12T23:32:23.045560+00:00 - JOB-00006

- Specialist: `Dark`
- Provider: `claude`
- State: `waiting_screening_review`
- Event: `screening_complete`
- Detail: 20-game smoke and 200-game screening completed; human review required.
- Hypothesis: For attack choice and immediate attacker scoring, account for Mega Sharpedo ex Hungry Jaws receiving its conditional damage only when Sharpedo is damaged; preserve generic attack ranking for all other Pokemon.

