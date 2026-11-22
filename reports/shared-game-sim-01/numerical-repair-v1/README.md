# Shared-game simulator: fixed repair canary stopped

**Completed and retained: zero games and zero trajectories.** The single declared repair canary, **2026_04_DET_CAR**, stopped in **BOTH_TEAM_COUNT_CORE** after **500 iterations and 563 objective evaluations**. The worker stopped on that first failure. It did not attempt a child fit, sample trajectories, advance to another origin or run the full remainder.

| Retained numerical result | Value |
|---|---:|
| SciPy success / status | false / 1 |
| Termination | TOTAL NO. OF ITERATIONS REACHED LIMIT |
| Initial objective | 12.643117355079287 |
| Terminal objective | 0.4620903275546069 |
| Terminal gradient infinity norm | 0.0017474439008135477 |
| Durable checkpoints | 50, at iterations 10 through 500 |
| New game attempts / stages / generations | 1 / 1 / 0 |

The objective, parameterization, initialization, information, chronology, tolerances and seed policy were unchanged. The hard limits were 500 iterations and 1,000 objective evaluations per stage. Original acceptance still required SciPy success and finite outputs. Objective decrease did not satisfy acceptance; it is not evidence of improved prop predictions. This result establishes a runtime stop, not a forecasting loss or a failure of every method in this family. No further numerical diagnostic or retry was run.

## Cost, retained evidence and remainder

The canary worker used **12.105303134 CPU seconds** and **13.461185758 controlled wall seconds**, one worker and one thread, with peak RSS **213,331,968 bytes**. Including the previous 59.093234438 seconds, immediate input checks and the recipe readback, cumulative canary usage is **72.629575547 / 180 CPU seconds**. New canary usage is **13.536341109 seconds**.

At this report snapshot, the same task carries **298.758657034 / 1,800 CPU seconds** and **399.459292683 / 7,200 controlled wall seconds**. The included 380-CPU-second completion reserve remains available. Final report readback costs append to the same [ledger](LEDGER.json). Process measurements and conservative preparation charges retain their disclosed metering limitations.

The original launch remains **2026-11-22T18:05:20.108935Z**. The approved elapsed ceiling is **21,600 seconds**, with fixed deadline **2026-11-23T00:05:20.108935Z**. The earlier 7,200-second elapsed overrun is preserved. Neither clock nor earlier consumption was reset, and no other package's budget was transferred.

[Full-remainder decision](FULL_REMAINDER_GATE.json): **STOP_FIRST_NEW_CANARY_FAILURE**. A valid, fully reopened canary was unavailable, so the conservative complete-path projection did not qualify. All 73 remaining origins stay unexecuted. Missing execution is not a loss or an intentional zero-selection policy.

The [actual executable and input freeze](FREEZE_A.json) was published at **3bfea990293ea7c5d8e2c411416962fccf9a0cf3** and [restored from GitHub](READBACK_freeze_A.json). The worker verified its code and actual input bodies before the attempt. No S-P/D-P forecast bundle exists. NFL D-P retention/reopening, trajectory conservation, forecast mutation/reproduction, new grading and current simulator capture remain **NOT_RUN**.

The [machine result](RESULTS.json.gz) contains the complete retained repair attempt, initial and terminal diagnostics, all checkpoints and counters. It excludes literal provider anchors, source plays, offers, outcomes and private ordinal bodies. A [separate C check](INDEPENDENT_FAILURE_RECORD_CHECK.json) verified the records and preserved file hashes. This is not B fit reproduction or a forecasting-accuracy check.

All 33 original failure files remain byte-identical to the pinned predecessor. The first original optimizer record remains **NOT_RETAINED**. The original final interrupted stage, vector and possible in-memory work remain unknown. The new, normally terminated repair has zero generation calls; it does not resolve that older uncertainty.

## All twelve category statuses

The canonical frame remains **3,474 cases, 74 games, W4–9 and 464 unknown outcomes**. W4 has two games; W1–3 are absent. Historical issue/quote clocks, source tiers, unclassified lines and conditional statistical settlement limits remain unchanged. No new simulator side record, probability score or numerical error can be measured from the failed fit.

| Category | Full-frame cases | Available / native / fallback forecasts | Status |
|---|---:|---:|---|
| pass_yd | 148 | 0 / 0 / 0 | Not executed after canary failure |
| pass_td | 148 | 0 / 0 / 0 | Not executed after canary failure |
| pass_cmp | 148 | 0 / 0 / 0 | Not executed after canary failure |
| pass_att | 148 | 0 / 0 / 0 | Not executed after canary failure |
| pass_int | 148 | 0 / 0 / 0 | Not executed after canary failure |
| rush_yd | 439 | 0 / 0 / 0 | Not executed after canary failure |
| rush_att | 226 | 0 / 0 / 0 | Not executed after canary failure |
| rec | 922 | 0 / 0 / 0 | Not executed after canary failure |
| rec_yd | 925 | 0 / 0 / 0 | Not executed after canary failure |
| rush_rec_yd | 222 | 0 / 0 / 0 | Not executed after canary failure |
| anytime_td | 0 | 0 / 0 / 0 | No matching offer contract |
| nick-chart-ppr-v1 | 0 | 0 / 0 / 0 | No matching offer contract |

Selection and decided records are **NOT_RUN/N/A**. The original A/B/C nominees, losses, pair masks and own-list results remain in the [saved-method comparison](../follow-through-v1/README.md). Different populations and horizons are not pooled into a new ranking.

## Independent receiving and delivery follow-through

C reopened the exact existing masks: **638/922 reception cases** and **638/925 receiving-yard cases**, the same within each target's mean, median and law siblings. Exclusions are 49 identity, 206 role and 29 missing-origin cases for receptions; 49, 208 and 30 respectively for receiving yards. [Mask evidence and reopening code](../saved-method-follow-through-v1/MASK_README_V1.md) preserve the original results.

B's review at **e8c242b8ef60a24494296659b8c02d867f157cc5** was retrieved. It reports 671 cases and hashes per target, but does not supply the fixed ordinal sets or its private identity body. **Intersection, C-only and B-only remain unresolved pending B's fixed-set comparison.** The net difference of 33 is not proof of 33 wrong omissions. No C defect has been demonstrated, and outcomes did not choose either set. C's actual ordinal/exclusion body was reopened privately; it was not publicly uploaded.

B's **5,338 saved bindings** were already received and graded at **0f5859c** under the different-horizon, timing-unverified diagnostic contract. A's **2,116 cases, 45 games, W4–7 and 6,258 procedure views** remain completed and closed. No join, fit or A recovery was repeated. Peer owners must update their own stale statuses after actual receipt; C does not claim cross-chat dispatch or acknowledgment.

The exact intended current products are **C-M3-v1.1::{rec,rec_yd}::M3-0::base::{MEAN_POINT,MEDIAN_POINT,LAW}**, the retained Leaf baseline. The existing current-query module now contains a guarded, separately typed adapter for these products. It is distinct from the expired C06 P1 packet and the M3-1 NB/Student-t adapter. This is software correctness work, not a current forecast or an accuracy gain.

**No fresh qualified current M3 model/source packet or typed feed has been issued, and no website product has been activated or served-verified by C.** The [delivery record](../saved-method-follow-through-v1/PRODUCT_DELIVERY_BINDINGS.md) identifies C's registered current-query/source executor and the missing finite current-origin execution package. The website owner must verify the actual previous pointer, admit the exact fresh product and return previous/new served-value and rollback receipts. Mean, median, law, strict crossing, website margins and Top Picks remain separate products.

A's earlier compatible five-week qualification and C's six supported receiving blocks remain intact. No new universal waiting period is introduced. Existing independently eligible releases and current-feed work continue under their owners, separately from this stopped simulator package.

[Saved-method checkpoint](../saved-method-follow-through-v1/README.md), [B/website handoff](B_WEBSITE_HANDOFF_V2.json) and [finite owner actions](FINITE_QUEUE.json) provide exact bindings and remaining steps. PR #65 remains draft; numerical execution approval did not authorize merging its changed head or activating the website.
