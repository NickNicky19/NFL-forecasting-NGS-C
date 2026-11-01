# First genuinely future C capture — v4

C issued **2,513 immutable forecasts for 407 active-roster candidates across 13 unplayed Week 8 games**, including all twelve categories. GitHub's successful check at commit `d782c25cd1505bcbfe9030b2ae7f966da544ee58`, [run 41255765990](https://github.com/NickNicky19/NFL-forecasting-NGS-C/actions/runs/41255765990), completed **2026-11-01 00:13:48 UTC / October 31 7:13:48 p.m. CDT**. First kickoff is November 1 18:00 UTC / noon CST, 17h46m12s later. Eight games share that earliest kickoff. CAR–GB was already final and excluded. The primary scoring snapshot is the first qualified capture, not a hindsight revision.

These are provisional, participation-conditioned laws, not starter/appearance forecasts, bookmaker nonvoid probabilities or demonstrated real-prop skill. The 407 chart-PPR rows are an explicitly rare-zero-label-subset shadow. Qualified current offers, real selections, graded outcomes and entries are absent; no wins or profit are manufactured. Week 8 numerical/event predictions proceed despite the offer gap.

## Table A — twelve-category forecast and improvement status

All are H-MULTI with the registered observed-current-source freshness policy. Numerical/probability improvement and uncertainty are **N/A: games unplayed and no forward comparator results**. Prior historical results remain separate. Sparse/no-history uses supported target labels, with the original metadata preserved in [the correction](SUPPORT_CORRECTION.json).

| Category | Future method | Forecasts | Sparse / no target history | Issuance | Forward accuracy/change |
|---|---|---:|---:|---|---|
| pass_yd | P2 / E0_DEF | 71 | 16 / 12 | Forecast-only captured | Pending |
| pass_td | P2 / E0_DEF | 71 | 16 / 12 | Forecast-only captured | Pending |
| pass_cmp | P2 / E0_ENV | 71 | 16 / 12 | Forecast-only captured | Pending |
| pass_att | P2 / E0_ENV | 71 | 16 / 12 | Forecast-only captured | Pending |
| pass_int | P2 / E0_ENV | 71 | 16 / 12 | Forecast-only captured | Pending |
| rush_yd | P2 / E0_OP | 168 | 31 / 20 | Forecast-only captured | Pending |
| rush_att | P2 / E0_OP | 168 | 31 / 20 | Forecast-only captured | Pending |
| rec | P2 / E0_ENV | 336 | 46 / 21 | Forecast-only captured | Pending |
| rec_yd | P2 / E0_DEF | 336 | 46 / 21 | Forecast-only captured | Pending |
| rush_rec_yd | P2 / E0_DEF | 336 | 46 / 21 | Forecast-only captured | Pending |
| anytime_td | P2 / E0_OP | 407 | 62 / 33 | Forecast-only captured | Pending |
| fpts | P2 / E0_ENV | 407 | 62 / 33 | Shadow; full-tail labels unqualified | Pending |

Implementation is P2-core complete for eleven categories, with remaining six-component gaps; chart-PPR has partial label coverage. Forecast-only issuance is operational and server-qualified; real-line paper issuance remains blocked by exact offer qualification. Predictive improvement is not yet demonstrated in any category. [CSV](CATEGORY_STATUS.csv) · [three-state registry](CATEGORY_REGISTRY.json) · [component matrix](COMPONENT_STATUS.json) · [full future artifacts](../../prospective/).

## Table B — each method's own actual-offer selections

| Categories / policy | Over W/L/decided/rate | Under W/L/decided/rate | Combined W/L/decided/rate | Qualified offers | Evidence |
|---|---|---|---|---:|---|
| All 12 / P1 unrounded point direction | N/A | N/A | N/A | 0 | No qualified actual-offer universe; not confidence abstention |
| All 12 / P2 exact-law direction | N/A | N/A | N/A | 0 | Forecasts captured; selections unavailable |

No shared threshold, closest grid value, consensus average or later closing quote supplies a missing line. The exact-line importer calculates Under/Push/Over from the retained law at each actual line. It rejects synthetic/hypothetical records, stale/suspended/conflicting quotes, incompatible contracts and missing lines; prices are not mandatory for statistical direction. Eight software fixtures check player-specific lines, changed-line recomputation, complement/tie/boundary logic and synthetic exclusion; they are not NFL picks. [Qualification sweep and exact gaps](OFFER_QUALIFICATION.json). Native-ID mapping, quote clocks, lifecycle, actual venue/contract and public retention remain required. The original site's mixed model/fixed/average fields are not imported as actual offers.

## Table C — reference matching

| Scope, all 12 categories | Exact common sample | Same-row errors / sides | Dependency |
|---|---|---|---|
| A/C | N/A | N/A | Exact native predictions/laws/query/label/cutoff/role/scoring export |
| B/C | N/A | N/A | Same; architecture reconstruction is not exact reproduction |
| A/B/C | N/A | N/A | All compatible exports and offered contracts/clocks |

[Detailed retained comparability ledger](../robustness-v3/ABC_COMPARABILITY.csv). No A/B headline is copied onto C's different population/freshness tier.

## Table D — six-leg / two-entry procedure

| State | Entries / original 6/6 | Any payout / net / expected return | Overlap |
|---|---|---|---|
| NO_QUALIFIED_SIX_LEG_ENTRY | 0 / N/A | N/A — no exact entry quote | N/A — no entries |

No forced six, side mix or second ticket. No unverified product of marginals is served as joint confidence.

## Table E — retention and publication

| Evidence | Executed state |
|---|---|
| GitHub restoration | [58files / 9,777,496bytes](GITHUB_RESTORE.json), all12 safe numeric-JSON models / all2,513 inferences reproduced;0pickle/0newfits |
| Independent read-only verification | [Actual sources, features, full training leaf counts, inference, contracts, mutation invariance and server proof passed](INDEPENDENT.json); [independent public final check](INDEPENDENT_PUBLIC_FINAL.json) |
| Future website | [Exact public desktop/mobile/DST/stopped-game/failure parity passed](served-final/RENDERED.json); served asset `8df8d016e62db5cc6a2405dacc25feb8227af65d`, [publication receipt](PUBLICATION.json) |
| Historical regressions | [All twelve original and v3 calibrated views retained](LOCAL_HISTORICAL_REGRESSION.json); no completed fit rerun |

[C's site](https://nicknicky19.github.io/NFL-forecasting-NGS-C/) separates Upcoming/Actual Props, Prospective Results and Synthetic Diagnostics. Website publication is not model promotion. Capture/model/offer/outcome clocks are distinct; status checks expire after30minutes and started games are suppressed. The manual path is documented in [the runbook](../../protocol/FORWARD_RUNBOOK_V4.md). No scheduled collector or automated future operation is active.

## What executed and what remains

Twelve total model-fit attempts used79.21CPU seconds /83.91wall seconds and358,658,048peak process bytes; all completed fits are reused. The pilot's unused non-event-prior validator failed after fitting; its surviving numeric forest was recovered by checking all training imputation/priors/leaf counts without refitting. The original fit clock was not retained and remains unknown; actual inference/persistence clocks are genuine. [Failure1](FAILURE_001.json), [ignored-source inclusion failure2](FAILURE_002.json) and [cross-platform floating-check failure3](FAILURE_003.json) remain visible. Neither failed GitHub check authenticates issuance. [Finite actual resource ledger](RESOURCE_USAGE.json).

Independent review found ten QB CMP/ATT CDF-order contradictions, including two median violations and no mean violations. [Append-only diagnostic](../../prospective/metadata/COHERENCE_v4_1.json) blocks dependent selections; original forecasts are not capped or rewritten. Support metadata has442count differences and81additional sparse flags; correct target support was already consumed by the unchanged models.

No new NGS benefit is claimed. The original C0/C1/C2 conclusion remains negative/inconclusive beyond opportunity support. The repeated user bundle's identical hash adds0samples/0inputs; its verifier and inert receiving reconciliation previously passed. It contains501weekly receiving rows and117summary rows, with duplicated HTML copies excluded; four rounding-boundary conflicts and one missing cell stay unqualified. Passing/rushing numerical extraction, native mapping, denominators, rights and model/timing provenance remain specific gaps. Season summaries and target-game NGS never enter these forward models. [Intake receipt](../USER_NGS_REPEAT_INTAKE_V3.json).

The completed2025validation/calibration checkpoint remains frozen:216weekly models,44,251queries/41,577known outcomes/272games, with sigmoid primary Brier worse in10categories and two tiny inconclusive changes. No sigmoid is promoted; no old NFL fit was repeated. [Prior complete rankings and negative results](../robustness-v3/README.md).

The next bounded queue prioritizes exact-line import/grading without refits, current manual refresh at actual readiness, then qualified post-final grading and only afterward permitted future updates. Unknown/DNP/void/push stay separate; postgame participation and full chart credit evidence are needed where statistics alone do not establish a played-zero label. Only a source-qualified real-offer package may advance to paper-selection review; no category has demonstrated prospective superiority. [Queue and per-category dependencies](../../protocol/NEXT_BOUNDED_QUEUE_V4.json).

The independently found UTC game-option label defect is fixed and verified in the final served asset. Original source/forecast clocks, models and hashes did not change. Native Chromium’s managed-proxy CA remains unavailable; public rendering used actual system-TLS-verified HTTPS responses with certificate checks enabled. Own paper-selection and post-final result website admission remain gated work; forecast-only operation does not establish those products or better picks.
