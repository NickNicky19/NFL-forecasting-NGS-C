# C04 current-source qualification and deferred issuance gate

A different, current-season roster source is now retained: `nflverse-data/releases/download/rosters/roster_2026.csv`, observed **2026-11-10 18:45:38 UTC**. Its provider Last-Modified is **15:34:29 UTC**. The documented loader returns season-level roster data; the separately retained data-schedule documentation states roster updates daily at 07:00 UTC. This qualifies an actually observed **current-known roster candidate snapshot**, conditional on appearance. It does not authenticate every transaction's effective instant, future gameday membership, health or expected starters.

The projection retains **959 QB/RB/WR/TE basic records**, including non-ACT records and one missing native ID; valid native IDs are unique. `week` is deliberately **null in the query contract**, not fabricated as Week 10. The full source header was not retained before a preserved diagnostic failure; therefore this package does **not** claim the upstream file lacks a week column. Any such field is simply not used to assert a future event-week roster. The original Week9-versus-Week10 weekly-source hold remains unchanged.

The fresh football inputs completed at **2026-11-10 18:55:28.982066 UTC**:

- `sources/profile-closure-next-02/roster_current_season.json`: minimal native player, team, position, name and provider-status fields for all basic roles.
- `schedule.csv`: current 2026 regular-season games, including native ESPN event IDs; projection persisted immediately after the recovery retrieval.
- `candidate_schedule.json`: **14 tentative future Week10 games**, not yet native-admitted.
- `current_facts_2026.csv.gz`: **9,455 unique player-games across136 games**, Weeks1–9, matched to non-null current schedule scores. No target Week10 actual rows exist. Explicit missing fields remain missing.
- `pbp_facts_2026.csv.xz`: **16,993 plays** in the same qualified43-column ordinary factual contract, including receiving yards. No target Week10 plays exist.
- `MODEL_INPUT_MANIFEST.json`: immutable file/source hashes and actual observation/cutoff clocks. It is sufficient for model preparation, not issuance.

The tentative14-game/28-team slate has **842 basic offensive-player records**, **439 valid source-ACT records**, and **364 source-ACT RB/WR/TE receiving candidates**. The other75 active QBs remain B-owned/basic;403 non-ACT-or-invalid records are held explicitly. Another117 league basic records are outside these teams. These are source/provider statuses and candidate rules, not confirmed participation. C's missing-history/rookie fallbacks remain necessary.

Current source observations do not authenticate the original availability of old game statistics. Historical seven-day versus one-day reconstruction, model-label admission, and current-query history must follow their separately declared policies. In particular, a future game kickoff must not cause current queries to admit records beyond the actual input cutoff. A newly observed current source containing a Monday final does not by itself remove a registered24-hour proxy.

## Recent completion qualification and immutable input v2

The separately registered ninth retrieval attempted one Week9 native-final query at19:23UTC. It returnedHTTP400; the request and error remain retained, with no repeat. `MODEL_INPUT_MANIFEST_V2.json` preserves all five predictor-file hashes and separately retains their18:55:28.982066UTC cutoff. Its actual qualification cutoff is **2026-11-10 19:23:09.469852UTC**. This is a source-admission clock, not a new football-data observation or successful new native-final response.

`completed_game_proof.json` admits1,208 older games with qualified official final scores and two recent games with already-retained, identity-matched native `STATUS_FINAL` evidence: JAX–BAL and CIN–ATL. The other13 recent games are held. Those older proof observations retain their original clocks; they are never relabeled fresh. The source/adapter must apply this same completed-game whitelist to all current models. `FINALITY_EXECUTION_BINDING.json` binds unchanged v2/proof bytes and the exact gzip-retained collector code that executed GET9. Its source failure does not prevent independently executable forecasting from the supported subset.

## Final native event gate — reserved until actual issuance

Do **not** call the following until the producer has fitted/prepared its current reference and shadow and is ready to freeze the packet:

`python reports/profile-closure-next-02/current-source/acquire_current_sources.py --stage refresh_status`

This is the tenth source retrieval attempt under `CURRENT_FINALITY_AMENDMENT.json` and `CURRENT_STATUS_ROUTE_AMENDMENT.json`. Two date-range requests returnedHTTP400, so the final unused stage now uses the existing supported single-date route directly: `dates=20261112&limit=100`. Attempt11 has no automatic retry authority. No access-denied bypass, polling loop or collection scheduler exists. Every admitted event must match native identity, teams, season/week/type, kickoff and current scheduled/unplayed state. Unmatched, absent or started games are held; only the actually verified subset may be issued. The14-game tentative candidate board remains retained. `events.json` and final `SOURCE_MANIFEST.json` are written only after this gate, binding the unchanged v2 model inputs and their separate football predictor clock.

A current local receipt alone is insufficient: native-status response `Age`, when present, must be finite and between0 and1800 seconds. HTTP `Date`, when present, must be within1800 seconds of observation and no more than5 seconds ahead for clock skew. A missing clock remains unknown; both unknown block admission. Invalid or stale headers reject this source response rather than trigger a favorable-status fallback. The final manifest binds the exact events bytes to the source ID, observation clock, raw response hash, retained response headers and executing code. The issue adapter independently checks these bindings, elapsed age and a still-future kickoff. These1800-second status rules do not replace the source-specific roster/football freshness contracts.

At this checkpoint the ledger has **nine retrieval attempts**, including two date-range400 responses, and **zero model fits, forecasts or selections** from this source task. Current offers are unavailable; the source pass retrieves no sportsbook/pick'em lines.

## Failures preserved, not hidden

`ROSTER_STAGE_FAILURE.json` records a post-download duplicate-diagnostic mask error. The projection and source bytes/hashes were already retained. Diagnostics were corrected from the saved projection with no refetch.

`FOOTBALL_STAGE_FAILURE.json` records the date-range400 and the first schedule projection that had not yet been saved. The older schedule hashes differed, so they were not relabeled fresh. The exact recovery request and immediate projection are recorded, with the root's bounded10-attempt amendment and unchanged32MiB response cap.

The exact failed scripts and actual input-transform script are gzip-retained; `SOURCE_TRANSFORM_BINDING.json` binds the immutable input manifest and executed transformation. The current CLI removes the obsolete failed route. Original inputs, metadata and old evidence are not overwritten.

`STATUS_HTTP_AGE_REPAIR.json` preserves the previously unexecuted final-status code and the identified stale-cache counterexample. `STATUS_HTTP_CLOCK_FIXTURES.json` records14 offline boundary fixtures, including fresh receipt with stale cache, non-finite/negative age, stale/future dates and unknown clocks. This patch precedes the first final-status execution; it changes no saved forecast or historical NFL score and adds no football observations.

Source rights remain the existing ordinary nflverse CC BY4 factual-projection permissions and minimal native event facts. No descriptions, betting data, FTN/NGS tracking, extra personal fields, private archives or credentials were retained. Source update documentation is not evidence of an individual historical file's availability.
