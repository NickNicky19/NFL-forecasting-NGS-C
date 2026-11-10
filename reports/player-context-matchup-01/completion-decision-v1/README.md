# Receiving player-context completion and keep/stop decisions — C

**Usable as-of profiles were produced; the new lookback recipe did not beat the strongest applicable controls. Close that tested recipe.** This additive package continues the existing championship, scorer and acceptance work. No old model, forecast, grade, negative finding or cap was reset.

## Profiles and current-query delivery

The roster/event adapter generated **53 records: 8 QB, 15 RB, 20 WR and 10 TE**, keyed by native player/event, historical team/role, opponent, actual cutoff and profile version. Missing target-game stat rows do not determine membership. C-owned receiving fields are available for RB/WR/TE where supported; A rushing and B QB sections remain explicitly owner-scoped.

The actual source cutoff is **2026-11-10 04:54:42 UTC / November 9, 10:54:42 p.m. CST**. The first verified future event is **WAS–NYG, native 401873052, November 12 at 7:15 p.m. CST**. The provider still supplies **Week 9 rosters for a Week 10 event**. All 53 profiles therefore remain preliminary/unqualified for forecast admission: **zero current forecasts, offers or selections were issued**. A later roster/status refresh is a new source observation, never an earlier clock.

[Machine index](profiles/current-W10/INDEX.json), [schema](profiles/SCHEMA.json), [examples](profiles/EXAMPLES.md) and [adapter](../../../src/receiving_profiles_c02.py) retain numerators/denominators, eligible games, source versions, raw estimates, shrinkage where actually used, support, zero/undefined/absent distinctions and exact consumed feature order. The fitted legacy zero-context coarsening is not silently changed by displaying the mathematically correct raw zero. Untargeted routes, starting alignment and contextual separation remain unavailable. No snaps-to-routes or destination-to-alignment substitution occurs.

Use the mandatory [passer-role correction](profiles/current-W10/PROFILE_METADATA_CORRECTION.json) and its overlay with the frozen base profiles: **27 non-QB pair views** are separated from QB pairs; counts and features are unchanged. The exact initial generator is retained. The model-input gate rejects incompatible old source contracts, feature order, lookback, inactive/unqualified roster status and later-than-profile fits. A profile is not a probability or a primary model qualification.

## Newly received seven-week actual-line replay

A's genuine scoped review of C and its replay are now **received and admitted for their checked public arithmetic/peer-review scope**. Independent full private-row/fit parity is not implied. B's scoped review of A is also now received; its raw/private limits remain. Earlier NOT_RECEIVED statements remain historical receipts, not the current state.

A's WR/TE reception board: **2026 W1–7, 733 eligible, 678 selected/available, 667 decided, 55 unavailable forecasts, 11 selected unknown outcomes, 81 games**. No intentional abstentions or fabricated losses fill the gaps. Evidence is exposed current-vintage, quote-timing-unverified source-row-conditioned replay, with source panels retained separately.

| Exact old C v1.1 point product | Over W–L/N/% | Under W–L/N/% | Combined W–L/N/% |
|---|---|---|---|
| P1 pooled mean |140–102/242/57.85%|242–183/425/56.94%|382–285/667/57.27%|
| P1 pooled median |115–70/185/62.16%|274–208/482/56.85%|389–278/667/58.32%|
| P2 partially pooled mean |135–100/235/57.45%|244–188/432/56.48%|379–288/667/56.82%|
| P2 partially pooled median |108–67/175/61.71%|277–215/492/56.30%|385–282/667/57.72%|

Always-Under is **344/667** and Always-Over **323/667**. P2 loses three mean/four median decisions to P1. **A's received package has not matched the strongest learned A/B/C controls on these same 667 rows.** Thus 389/667 establishes neither a learned champion nor a context-caused gain. It must not be compared directly with A's 521/917 or C's separate two-week panel. Seven point-direction weeks satisfy duration only for these exact products; probabilities, EV and Top Picks inherit none of them.

C independently reconciled the permitted 96 summary/288 side/10 paired cells. Private-row parity stays limited. A's review of C's older rows had 255 decided +20 unavailable +3 unknown; C's native-query-expanded panel has 255 decided +23 unknown. Both scopes are preserved with zero score changes.

The missing saved-control export is now prepared and published: [C retained Leaf points](intake/C_RETAINED_LEAF_POINTS_W1_W7.json.gz), 2,152 RB/WR/TE queries including 1,547 WR/TE. It contains original unrounded means/medians and source/origin bindings, extracted from safe JSON only. [Owner-local handoff](intake/STRONG_CONTROL_OWNER_LOCAL_HANDOFF.json) binds the exact 667-case mask and A's strongest compatible Leaf candidate. **A executes the private join; B independently verifies; C consolidates the returned permitted results.** Publication is not consumer acknowledgment. A separate [546-row existing C P1/P2 Week 8 point mapping](C_EXISTING_POINTS_W08.json) now supports the same owner-local extension without new fits or inference; no Week 8 score is claimed before A executes it. The prepared B-attempts/A-earlier-lines join also remains A-owned; overlapping W5 records must be deduplicated, and completion offers are a separate source task.

## Executed lookback experiment

One new mechanism was tested: **own-player lookback selection**, using new qualified 2024 warm-start context. It is a new recipe; neither the old v1.1 fit nor its seven-week replay is relabeled. Team/opponent windows stay fixed at eight; the pooled Poisson learner and alpha .1 remain fixed. No HGB non-use experiment or calibration search was repeated.

Earlier **2025 W1–8** rolling validation selected **four appearances** for end-to-end full-game median MAE: 4/8/16 scored **1.44316/1.46371/1.44830** on 1,557 known WR/TE rows. The choice was frozen before 2026 evaluation. There were genuine 8-versus-16 feature differences in **871 earlier-validation and 1,018 current-season WR/TE query rows**; sixteen was not truncated to eight. These are exposed chronological development periods, not untouched confirmation. No earlier actual-offer board qualified for choosing an actual-line objective.

| 2026 WR/TE W1–8, same 1,584 known rows | Median MAE |
|---|---:|
| Ordinary pooled control |1.40341|
| Same-source context-8 |1.40341|
| Earlier-selected context-4 |1.39078|
| Strong unchanged Leaf recipe |**1.34912**|

The candidate improves its weaker context-8 control but **loses to Leaf by .04167 catches**. Paired game sensitivity is **[.01130, .07116]** and week sensitivity **[.00866, .07813]**, candidate minus Leaf. The one missing compatible Leaf W8 origin was fitted once; W1–7 saved outputs were reused. Offered-player numerical masks, equal-player results, every week and missing states are separate, not inferred from this broader stat-row panel.

The exact-line evaluation is still **Pinnacle W2–3 only**, WR/TE 278 eligible/selected, 255 decided, 23 unknown, 32 games. No new offered week was created.

| New earlier-selected product | Over W–L/N/% | Under W–L/N/% | Combined W–L/N/% |
|---|---|---|---|
| Mean direction |50–40/90/55.56%|93–72/165/56.36%|143–112/255/56.08%|
| Median direction |41–24/65/63.08%|109–81/190/57.37%|150–105/255/58.82%|
| Exact-law direction |41–24/65/63.08%|109–81/190/57.37%|150–105/255/58.82%|

The law ties the strongest old C partial-pooling result **150/255**. Brier **.276549** remains worse than neutral **.25**, ordinary pooled **.274114** and retained direct E0 **.262048**. Its improvement over old partial pooling is only .004189, below the existing .005 descriptive review threshold. The old C pooled mean direction also had 148/255, versus the new mean's 143/255. All procedures retain their own selected sides and identical offer/outcome matching.

Mixed Top-6/10/20 selected-4 lists score **5/12, 5/19, 16/37**, versus E0 **6/12, 11/20, 22/40**. Unknown selected members remain. These last-recorded-line lists lack simultaneous-board evidence and are not executable entries or 6/6 results. No 90% or profitability claim follows.

[Lookback evidence](lookback/README.md) includes safe models, per-origin rows, broad/offered/support masks, strong controls, proper scores and game/week uncertainty. Forty-eight count fits and one necessary Leaf extension consumed **134.637 CPU seconds**, peak **431 MB**, reusing the pilot; all count fits converged. An inherited export-metric field was contained through an append-only [qualified metric view](lookback/METRIC_VIEW_CORRECTION.json): point probability metrics are N/A, law log loss is recomputed, and no forecast/side/grade/aggregate Brier changed.

## Keep/stop and requirement completion

| Mechanism/product | Disposition | Reason / next action |
|---|---|---|
| Old fixed direct context columns | CLOSE_RECIPE_NO_GAIN | Completed fixed-learner negative; no forced feature use or unchanged retry |
| Old partial-pooling point replacement | CLOSE_RECIPE_NO_GAIN | Loses to pooled mean/median on the same seven-week 667-case panel |
| New selected-window numerical/direction/Top-K replacement | CLOSE_RECIPE_NO_GAIN | Loses strongest numerical/selected controls; ties old best direction with poor probabilities |
| Old pooled point product versus strongest learned controls | INCONCLUSIVE | A must execute the bound 667-case learned-control join; no new fitting is needed |
| As-of profile data/adapter | SHADOW | Reusable, but actual snapshot is preliminary; no model/primary qualification |
| Current forecast admission | SOURCE_OR_RESOURCE_BLOCKED | Exact Week 10 roster/status and compatible current-origin model admission required; no resource cap is raised |
| Alignment/all routes/contextual separation | SOURCE_OR_RESOURCE_BLOCKED | Exact source/denominator/timing/rights dependencies remain; mechanism is untested, not disproved |

The one bounded [source pass](SOURCE_QUALIFICATION.json) reused prior qualifications and checked current documentation. Ordinary PBP supports native QB/passer-to-receiver targeting proxies, not routes. FTN play-level motion does not identify a moving receiver; its charting is distinct from postseason participation. NGS targeted separation cannot establish all-route openness, and existing rights/vintage holds are unchanged. The admitted PropLine revision is unchanged and supplies no new weeks, categories or current open offers.

| Required question | Completion here |
|---|---|
| Roster-driven as-of receiving profiles | Implemented/executed; 53 records; current admission blocked by roster version |
| Same-mask strongest reception comparison | Seven-week C point replay admitted; C control export delivered; A's stronger learned join still unexecuted |
| Distinct earlier-only 4/8/16 lookbacks | Executed with 2024 warm-start; selected four; closed for tested replacement products |
| RB conditional yards/success and team opportunity | A-owned remaining wave; no C duplicate fit |
| QB depth catchability/stint/opportunity | B-owned remaining wave; no C duplicate fit |
| Native QB–receiver targeting | Raw profiles executed with QB/non-QB separation; predictive inclusion remains queued |
| True alignment/routes/separation | Source-blocked, not completed or disproved |
| Full future exposure/context integration | Still queued; no target-game actuals substituted; separate v10 ownership preserved |
| Older-season actual-offer coverage | Missing qualified boards remain explicit; 2025 validation is numerical, 2022–24 training is not testing |

All twelve category dispositions are retained in the canonical continuation status. No private archives were moved, no production owner changed, and no website or selection release was performed. Only byte-identical temporary software duplicates and an unused browser video encoder were reclaimed; all NFL evidence and old archives remain. The pilot retention amendment is finite and preserves the unchanged whole-C cap. HTTP header normalization was repaired prospectively; one byte-identical roster readback recovered metadata without reassigning the original profile cutoff.

## Recovery and publication

The first immutable C publication is `19cd7910afd55f566a8d1251bc3b6564c2199a54`, [PR37](https://github.com/NickNicky19/NFL-forecasting-NGS-C/pull/37). [Fresh GitHub recovery](FRESH_GITHUB_RESTORATION.json) fetched four exact objects (33,271 bytes) and independently calculated a real losing Under case from the restored primitive coefficients: mean2.2849700522, U.6000283897 at2.5, actual3, LOSS. The profile index restored53 preliminary/unqualified rows. GitHub's server PR creation clock is retained; client commit dates are not used as proof of issuance. This is profile/evidence publication, not a forecast/selection capture, live consumer acknowledgment or deployment.
