# Earlier NGS experiment and C's distinct comparison

A's `ngs-context-reconstruction-v1-2026-10-22` is completed, not untested. At pin `507bbd186ad6eb6ded5d75337b6a966864ef2e2f`, inspect `reports/ngs-context-study/{summary.json,ngs-source-binding.json}`, `nfl_lab/{context.py,context_study.py}`, and the information-mechanism matrix in the user task. C read these exact sources; hashes are in REFERENCE_READS.json.

The earlier fixed ridge/logistic challenger augmented base97 with **28 columns**: fourteen raw metric means and their counts over three eligible roster-game slots, missing NGS consuming slots, max age 60 days, kickoff+7 days assumed availability. Passing: time-to-throw, intended depth, aggressiveness, expected completion, CPOE. Receiving: cushion, separation, intended depth, YAC above expectation. Rushing: efficiency, eight-defender percentage, time-to-LOS, rushing-over-expected/attempt, rushing-over-expected percentage. It trained on 2019–2022 and evaluated 2023, with NGS only 2022/2023. The broad roster/outcome panel included many nonprimary-role zero labels and postseason: for passing it scored 6,173 rows in 285 games/22 weeks, including 5,505 passing-zero rows. Its passing MAE therefore cannot be compared directly to a QB-only C score.

| Target | Earlier base loss | Earlier NGS loss | Result |
|---|---:|---:|---|
| pass_cmp | 0.725921 | 0.734825 | Worse |
| rec_yd | 15.281329 | 15.299871 | Worse |
| pass_yd | 10.196688 | 10.196251 | Tiny improvement |
| rush_yd | 7.930309 | 7.955582 | Worse |
| rec | 1.161634 | 1.161250 | Tiny improvement |

Across all eleven original targets, only passing yards, carries and receptions improved their declared primary score; eight lost. Passing-yard RMSE worsened despite the tiny MAE gain. Recorded offers were unavailable. Continuous normal diagnostics and earlier count-law diagnostics are not imported as C's integer threshold probabilities. Original issuance and publication clocks remain unestablished.

C tests a **different information ablation**, not discovery of new metrics: one unchanged HGB direct learner, primary-role stat-row populations, all regular-season weeks, explicit C1 availability/opportunity support, and C2 small category-specific exposure-weighted groups from eight eligible NGS reports within 365 days. C2−C1 isolates values beyond support; C2−C0 retains the full effect. C excludes unqualified expected/model-derived fields rather than asserting a valid 2025 CP2.0 bridge. No shrinkage, decay, receiver aggregation, volume conversion or tuning was fitted. Those are distinct unexecuted mechanisms.

This version also changes learner, historical periods and population relative to the **old** experiment, so it cannot attribute differences between the old and new studies solely to feature weighting. Within C, those controls are held fixed. Historical seasons remain exposed research. A new repository does not make them untouched confirmation.
