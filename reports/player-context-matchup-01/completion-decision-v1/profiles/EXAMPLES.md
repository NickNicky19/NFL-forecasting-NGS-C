# Readable as-of profile examples

Actual source cutoff: **2026-11-10 04:54:42 UTC** (November 9, 10:54:42 p.m. CST). Event: WAS–NYG, November 12 at 7:15 p.m. CST. These are preliminary Week 9 roster profiles for a Week 10 event, not forecasts or confirmed participation. All 53 current-query admissions are unavailable until the roster/version gate qualifies. No injury source was retrieved; unknown does not mean healthy.

| Case | Player | Eligible same-team context games | Targets / official team attempts | Most recent player context | State |
|---|---|---:|---|---|---|
|ordinary|Theo Johnson (TE)|8|28 / 255 (OBSERVED)|2026-10-11T17:00:00+00:00|UNQUALIFIED_ROSTER_OR_STATUS_VERSION|
|sparse|Isaiah Likely (TE)|7|63 / 241 (OBSERVED)|2026-10-25T17:00:00+00:00|UNQUALIFIED_ROSTER_OR_STATUS_VERSION|
|unseen_or_no_history|Calvin Austin III (WR)|0|None / None (ABSENT_HISTORY)|None|UNQUALIFIED_ROSTER_OR_STATUS_VERSION|
|known_zero|No real case in declared universe; see explicit software fixture|N/A|N/A|N/A|Not fabricated|
|missing_source|Theo Johnson (TE)|8|28 / 255 (OBSERVED)|2026-10-11T17:00:00+00:00|UNQUALIFIED_ROSTER_OR_STATUS_VERSION|

The deterministic real ordinary case is Theo Johnson; sparse is Isaiah Likely; no-history is Calvin Austin III. Names/teams come from the versioned source projection, not current team assumptions. The universe contained no WR/TE whose entire qualified window had known-zero targets; the test fixture proves known-zero volume 0/2=0 while catch quality 0/0 remains undefined. Missing alignment/routes/separation remain explicit SOURCE_BLOCKED for every profile.

The first profile projection labeled all passers as QBs. The append-only role overlay qualifies historical (game, passer) roles, preserves 27 non-QB pair views, and changes no target counts, feature vector, probability or score. Use the base-plus-overlay view; `QB_pair_targeting.qualified_QB_pairs` and `other_or_unknown_passer_pairs` are separate. A targeted pass is not evidence of an untargeted route.

Each raw receiving rate carries its numerator/denominator, game support and applicable descriptive uncertainty. Forecast inputs retain the legacy zero-target coarsening; raw descriptive zero volume is not silently inserted into a fitted model. The model-input gate requires a new matching source-contract hash, exact feature order/lookback, fit clock, target exclusion and primitive artifact hash. The old v1.1 models cannot be substituted merely because the dimensions match.

Ordinary E0 features consume earlier outcomes/opportunities; own profiles consume qualified earlier target/play rows; opponent features consume earlier shrunken depth/down response. Each profile retains the separate consumed-game lists and the actual latest admitted game. Fresh Nov10 downloads remain current-vintage reconstruction of historical rows under the strict seven-day policy. Future target actuals, starters and target-game context are absent/unnecessary.
