# W1–4 exact FTN completion join received

A completed the saved-output join at immutable commit `5a41d2bac6027e0ac1b5a2744d52f8ec5e93c47e`: **84 retained actual completion offers, 48 games, 2026 W1–4**. All 84 forecasts and outcomes are available; there are zero unknowns, fallback forecasts, abstentions, pushes or technical failures. Full-board and all-three-B-arm common masks are identical. The old pending 146-query handoff is superseded by this executed 84-offer result; it must not be requested again.

| Exact procedure/output | Own Over W–L / decided | Own Under W–L / decided | Combined W–L / decided / rate | Same-offer MAE |
|---|---|---|---|---|
| B0 mean, B1 exact alias | 5–2 / 7 | 38–39 / 77 | 43–41 / 84 / 51.19% | 5.142122 |
| B2 mean | 4–4 / 8 | 36–40 / 76 | 40–44 / 84 / 47.62% | 5.125128 |
| B0 lower median, B1 alias | 9–5 / 14 | 35–35 / 70 | 44–40 / 84 / 52.38% | 4.833333 |
| B2 lower median | 14–7 / 21 | 33–30 / 63 | 47–37 / 84 / 55.95% | 4.833333 |
| B0 stored-law P2, B1 alias | 9–5 / 14 | 35–35 / 70 | 44–40 / 84 / 52.38% | N/A |
| B2 stored-law P2 | 14–7 / 21 | 33–30 / 63 | 47–37 / 84 / 55.95% | N/A |
| A CatBoost mean-objective point | 24–13 / 37 | 27–20 / 47 | 51–33 / 84 / 60.71% | 4.563232 |
| A HGB MAE-objective point | 25–14 / 39 | 26–19 / 45 | 51–33 / 84 / 60.71% | 4.601968 |
| Always Over | 44–40 / 84 | N/A | 44–40 / 84 / 52.38% | N/A |
| Always Under | N/A | 40–44 / 84 | 40–44 / 84 / 47.62% | N/A |

| Week | Offers / games | B0=B1 mean | B2 mean | B2 lower median / P2 |
|---|---|---|---|---|
| 2026 W1 | 10 / 6 | 6–4 | 6–4 | 7–3 |
| W2 | 25 / 14 | 13–12 | 10–15 | 16–9 |
| W3 | 26 / 15 | 14–12 | 13–13 | 14–12 |
| W4 | 23 / 13 | 10–13 | 11–12 | 10–13 |

The primary mean-direction contrast loses three decisions (−3.57 percentage points, seven side disagreements). Its paired game interval is [−10.11, +2.33] percentage points; the four-week interval is [−9.90, +3.03]. Median/law direction gains three decisions within-method, with 11 disagreements and a game interval [−3.59, +12.20] percentage points. It remains four wins behind both retained A leaders on these exact cases. This does not justify replacing the predeclared mean output after viewing the results. Preserve **CLOSE_RECIPE_NO_GAIN** for the primary information recipe and **INCONCLUSIVE** for the secondary median/law effect. No new selective policy was tested; broad-board and selective 90% targets remain unestablished.

B2 Brier improves from 0.264828 to 0.263128, three-state log loss from 0.724653 to 0.721530 and Over-event AUC from 0.50682 to 0.52784. The paired Brier interval includes zero; Brier remains worse than neutral 0.25. A point controls have no inferred probability or EV. Complete numerical, probability, fallback, subgroup and same-mask controls remain in the [permitted result projection](FTN_COMPLETION_W1_W4_RESULTS_PERMITTED_PROJECTION.json.gz).

The exact B producer is `d79acddf5f094c85001c9b17a525ac7d9e25f9ec`, namespace `B-FTN-BALL-QUALITY-COMPLETION-v1`. B0 reuses `B-QB-OPPORTUNITY-PROFILE-INCREMENT-v1:R3`; B1 is an output/input-contract alias. The inspected adapter enforces QB/pass_cmp identities, `H-RECENT` history, `2022_EXPANDING` feature memory, origin cutoff ordering, canonical historical teams and exact kickoff/cutoff equality. Mean crossing, lower-median crossing and strict stored-law P2 are distinct policies even where their decisions agree. No joint attempts/completions law is claimed.

Offer source is `ANNUAL_NAMED_NJ`: numeric book IDs 68 (78 offers), 69 (4) and 79 (2), without bound names. All original quote clocks and venue settlements are unqualified; `cutoff_qualified=false` for every offer. FTN historical publication clocks are unverified current-vintage seven-day reconstruction. These four weeks are additional exact-procedure statistical line-crossing diagnostics, not new NFL games, original-issued picks, authenticated ordinary/main-line history or deployment evidence.

C independently checked all 570 published side triads, weekly-to-cumulative counts and weighted numerical/Brier arithmetic, 288 paired differences, source SHA/Git-blob identities and the published adapter/mask schemas. The three views overlap; empty W5–9 rows mean **outside this W1–4 join**, not a finding that later offers are absent. C did not inspect A's private 1,596-row joined vector, raw FTN plays, historical observation vintages or fitted models. [A's independent predetermined W1 review](OWNER_INDEPENDENT_W1_REVIEW.json) remains owner-attributed, not C raw-row parity.

The [membership/comparability receipt](MEMBERSHIP_AND_COMPARABILITY.json) identifies what the hashes commit to. Cross-source diagnostic aggregation is possible when B confirms exact procedure/output/history/fallback/decision/outcome compatibility and canonical disjoint periods. It must retain source strata and timing limitations. The opaque mask hashes alone do not establish one homogeneous bookmaker board or original pregame issuance. A W5 annual offers must be deduplicated against B W5 before adding them; different file hashes do not prove disjointness.

[Existing A late-completion coverage](A_LATE_COMPLETION_EXISTING_COVERAGE_PROJECTION.json.gz) is a source-bound availability lead: the same CatBoost version has four annual W5 offers (1–3), and W6/W7 have 28 internal-threshold decisions each (11–17 and 16–12). Those internal lines do not fill actual-offer weeks, but saved forecasts can be assessed for joining to B's real late offers. W8 contains separately measured archive/group products; no exact CatBoost/HGB identity on B's W8 board is established. No matching A W9 output is bound by these receipts. A should inventory the retained vectors by exact procedure/player/game/origin, join supported saved outputs first, then use authenticated retained-origin inference only where genuinely missing. This is an owner-local artifact/identity task, not a default new fit or a blanket different-source blocker.

[Source bindings](SOURCE_BINDINGS.json), [normalized ledger rows](NORMALIZED_COMPLETION_ROWS.json.gz), [aggregate verification](INDEPENDENT_AGGREGATE_CHECK.json) and [read budget](READ_BUDGET.json) retain execution scope. FTN-derived outputs: FTN Data via nflverse, CC-BY-SA 4.0; PBP separately CC-BY 4.0. Protected A rows remain owner-local. C performed zero fits, inference, peer writes or source acquisition.
