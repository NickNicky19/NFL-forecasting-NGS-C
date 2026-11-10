# C05 current eligibility source snapshot

The prepare stage actually executed three bounded requests: the current-known season roster and HEAD checks of the already-used weekly-stat/PBP sources. No model was fitted or forecast issued.

The 22:51:53 UTC November 10 snapshot has 959 basic QB/RB/WR/TE records; NE–DET has 58 basic records and 23 valid provider-ACT receiving candidates (7 RB,10 WR,6 TE). ACT does not identify starters, health or future participation. The current roster source has no `week` column; the projection deliberately retains `roster_week=null`. Individual transaction-effective times remain unknown. The older C04 header-presence record is not overwritten.

The roster raw SHA and both strong football-source ETags match the earlier retained source versions. HEAD did not download or hash the current football bodies. This metadata does not authenticate historical publication times. The new forecast contract remains an explicitly older football/feature-cutoff shadow, not a claim that model features were refreshed now.

`INPUT_MANIFEST.json` binds the actual roster projection, candidate schedule, original C04 model-input manifest, HTTP clocks and version comparisons. `PREPARE_EXECUTION_BINDING.json` binds the actual executed source code. Full raw payloads were held only in memory; the retained projection is permitted factual metadata. Existing source attribution is nflverse / CC BY4; no NGS, news, images or protected feed is retained.

The fourth and final request is reserved for the native November 15 scoreboard after root commits code and records a clean issuance gate. The target was fixed beforehand as the earliest uncaptured retained game: NE at DET, native 401873053, November 15 14:30 UTC / 8:30 a.m. CST. No future-event admission or source manifest is claimed before that stage. Failed/mismatched/stale native status will hold issuance; no automatic retry exists.
