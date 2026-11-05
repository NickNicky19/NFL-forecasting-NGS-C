# Post-wave diagnosis, qualification and delivery — POST-WAVE-5W-v1

The actual-prop championship is still partial. This retained A reference panel covers **2026 Weeks 1–7**, requested Weeks 1–8, using timing-unverified actual recorded lines. These are each procedure’s own side records, not original C picks or new A/B/C champions. No additional NFL outcomes were scored in this diagnosis wave. QB passing; RB primary rushing; RB/WR/TE receiving. Exact history is producer-bound but not fully expanded in the public CSV.

| Category | A method / output reference | Over W-L/n/% | Under W-L/n/% | Combined W-L/n/% | Eligible/selected/scored | Games | Duration floor |
|---|---|---:|---:|---:|---:|---:|---|
| Passing yards | HGB_MAE_DIRECT / mae_objective_point | 41–29/70 (58.57%) | 37–36/73 (50.68%) | 78–65/143 (54.55%) | 143/143/143 | 79 | MET: 7 weeks; not admission |
| Passing TDs | COUNT_A_MEAN / mean_objective_point | 43–31/74 (58.11%) | 44–24/68 (64.71%) | 87–55/142 (61.27%) | 142/142/142 | 78 | MET: 7 weeks; not admission |
| Completions | CATBOOST_MEDIUM / mean_objective_point | 35–18/53 (66.04%) | 44–47/91 (48.35%) | 79–65/144 (54.86%) | 144/144/144 | 79 | MET: 7 weeks; not admission |
| Pass attempts | COUNT_A_LEGACY_POINT / legacy_empirical_point | 19–16/35 (54.29%) | 51–57/108 (47.22%) | 70–73/143 (48.95%) | 143/143/143 | 79 | MET: 7 weeks; not admission |
| Interceptions thrown | LEAF_CDF / mean | 75–58/133 (56.39%) | 8–2/10 (80.00%) | 83–60/143 (58.04%) | 143/143/143 | 78 | MET: 7 weeks; not admission |
| Rushing yards | EQUAL_CDF_CAT_HGB_POINT / empirical_point_blend | 61–55/116 (52.59%) | 199–128/327 (60.86%) | 260–183/443 (58.69%) | 455/455/443 | 81 | MET: 7 weeks; not admission |
| Rush attempts | BACKFIELD_CDF / mean | 70–60/130 (53.85%) | 104–93/197 (52.79%) | 174–153/327 (53.21%) | 335/335/327 | 81 | MET: 7 weeks; not admission |
| Receptions | LEAF_CDF / median | 157–103/260 (60.38%) | 364–293/657 (55.40%) | 521–396/917 (56.82%) | 992/992/917 | 81 | MET: 7 weeks; not admission |
| Receiving yards | RESPONSE_CDF / mean | 298–268/566 (52.65%) | 201–162/363 (55.37%) | 499–430/929 (53.71%) | 1008/1008/929 | 81 | MET: 7 weeks; not admission |
| Rush + rec yards | RESPONSE_CDF / mean | 117–113/230 (50.87%) | 130–108/238 (54.62%) | 247–221/468 (52.78%) | 493/493/468 | 81 | MET: 7 weeks; not admission |
| Anytime TD | N/A: no compatible offer | N/A | N/A | N/A | Unknown | N/A | NOT MET |
| Exact chart PPR | N/A: no compatible offer | N/A | N/A | N/A | Unknown | N/A | NOT MET |

Full namespaced identities, side differences, controls, uncertainty and missing states: [canonical headline JSON](HEADLINE_ACTUAL_LINE_REFERENCE.json). The corrected Count A mean is a separate tied procedure from the legacy point; neither borrows the other’s identity.

Observed A W1–7 maxima remain: **Over—interceptions, Leaf median 4–1/5 (80%); Under—interceptions, CatBoost 4–1/5 and Leaf mean 8–2/10 (80%), tied; combined—passing TDs, corrected Count A mean and legacy point 87–55/142 (61.27%), tied.** These exposed, differently selected samples are not future leaders. Same-pool constants beat completions by 3 wins and attempts by 6. Count A’s source-bound Leaf-median control is 85/142, only 2 fewer wins, with a paired interval crossing zero. No historical side splice is proposed.

## Why predictions stayed unchanged

The added receiving share values and ordinary team-completion context reached the fitted learner correctly. [MODEL_INPUT_TRACE.json](MODEL_INPUT_TRACE.json) checks 20 saved primitive models across eight stage/origin groups. It reconstructs the five W2 training matrices for S0/S1/C0/C1/C2, each with 19,623 earlier eligible rows. Native joins, varying/missing value columns, training-only median imputations, feature order and exact training fingerprints match the saved models. The original input/target/future-mutation and representative inference audits are reused through their immutable bindings.

All new performance/context values have **zero fitted splits**. One support field, `player_targets5`, is used in 7–8 splits; reception history, target history, TE role and the exact threshold account for the other splits. After normalizing numerically identical integer/float threshold metadata, the fitted trees match within each origin/group. This explains the unchanged predictions without a dropped-column, feature-order, cache or inference-bypass defect. Unretained split-gain traces do not establish universal redundancy or why every other learner would ignore those fields. Ordinary team completions are **not newly validated NGS**.

The tested representations are **CLOSED_NO_INCREMENT**. No forced feature usage or new football tuning was performed. Their preserved exact Pinnacle reception results are:

| Procedure | Over | Under | Combined | Eligible/selected/decided | Brier |
|---|---:|---:|---:|---:|---:|
| S0 support / S1 share values | 34–26/60, 56.67% | 155–122/277, 55.96% | 189–148/337, 56.08% | 362/340/337 | 0.26062234 |
| C0 / C1 support / C2 completion values | 39–26/65, 60.00% | 155–117/272, 56.99% | 194–143/337, 57.57% | 362/340/337 | 0.25986835 |

Period: 2026 W2–3 only, timing-unverified actual-line diagnostics. Each group retains 22 identity-held unavailable queries, 3 selected unknown outcomes, zero statistical pushes and zero pending. Values added no wins, probability change or coverage. Brier remains worse than neutral 0.25. The separate 2025 origins are synthetic diagnostics, not actual offered markets.

One saved 512-row synthetic positive-control fit verifies that this software path can split on an added last column. It contributes **zero NFL weeks**. Its original metadata assertion failure, original attempt code hash, explicitly path-normalized public source copy and conservative CPU charge remain in [TRACE_ATTEMPTS.json](TRACE_ATTEMPTS.json); that completed toy fit was reused. Independent review checked all 20 models, the five training matrices, toy inference, qualification accounting and source hashes: [receipt](INDEPENDENT_VERIFICATION.json). No football models were refit.

## One product-specific qualification ledger

The [JSON ledger](QUALIFICATION_TABLE.json.gz), [CSV](QUALIFICATION_TABLE.csv.gz) and [twelve-category summary](TWELVE_CATEGORY_QUALIFICATION.json) retain exact procedure, target, output, role, history, policy and source contracts. Every scored `(season, week)`, attempted/zero-selection/unresolved week, available metric, own-side result and season coverage is shown. They project existing evidence; they are not additional experiments. Weekly aliases merge only under the bound ALL64 source contract, and cumulative views never add weeks.

There are 7,272 product profiles, 2,081 meeting the duration floor, including 114 actual-line direction profiles. These are **not independent model or NFL observation counts**. None of the received exact-line probability or Top Picks products meets five scored weeks. The original C-v4 capture has 34 typed forecast-only products, each with one Week 8; the parent replay confers no prospective test weeks. C01 has two actual-line weeks and four separate synthetic diagnostic origins. They cannot be added into six actual-line test weeks. Historical duration does not establish current-season validation; MET is a duration floor, not automatic admission or superiority.

B’s immutable index at `d835346c2cda1cf7d2ffcfb843b103cbcb489615` was read back; the new repair/gate producer is `7d286572aa41db434d93b7619f4bf1a6b0e33ad4`. C received 7,413 of 7,893 published source views, with mandatory V3/V4 source-clock and point-attribution qualifications, and normalized 2,444 selection triads through its existing adapter. Proper scores and the unchanged B0 ancillary mean remain separate. The omitted 480 COMMON_COHORT views are **not received or admitted**. The additional 64-law source is separately retained. Private B rows, coefficients and inference parity remain unverified. These are scoped owner-local aggregate arithmetic admissions.

B’s reception repair moves 194–143/337 to 195–142/337 while Brier worsens 0.259868→0.260203. Passing TD remains 14/26, with Brier 0.266196→0.264826, still worse than neutral. Selective pools remain receptions 85/160 versus always-Under 87/160, and passing TD 6/13 versus always-Under 7/13. The 90% gate selects no qualifying cases: N/A, TARGET_NOT_ESTABLISHED. These exact repairs/gates have two or one scored weeks. B owns the confidence-ordering diagnosis and any materially distinct next repair; C does not duplicate it.

[Source dispositions](SOURCE_DISPOSITIONS.json) distinguish receipt, hash validation, scoped aggregate admission and unseen/private claims. A’s latest known immutable export remains `21ca035c0e7a3caf5aae10353a59a09572483e76`; a newer allocation-wave export reference has not been received. User-reported A0/A1 ties and losing structured-RB results are preserved as reported, not fabricated into scored C rows. The old 402-byte conflict was resolved by A and is not a current blocker. Missing historical source/origin cells and B’s specific recovery gates remain in the canonical task ledger. The full W1–8/historical championship is incomplete.

Automatic approval review rejected the original eight-file extension download because 3,836,639 raw bytes exceeded its registered additional 2 MiB allowance. A versioned six-file reduction with cumulative/read/hash guards retrieved 1,292,473 bytes within that unchanged allowance. The omitted comparison masks remain unadmitted. [Failure and correction record](QUALIFICATION_BUILD_ATTEMPTS.json). Legacy ESPN/Sleeper/NGS source holds are unchanged; public aggregate/technical exports confer no raw-provider rights.

## Count A: seven test weeks, current delivery still missing

[Exact delivery disposition](COUNT_A_DELIVERY_DISPOSITION.json). `pass_td__COUNT_A_MEAN`, procedure `f8607aa99a94c7c1c9ab5c89599e07eba9b15527749b092b225f368032881e83`, has seven scored 2026 weeks and 87 wins in 142 decided cases. It meets the duration floor for this tested point-direction product. No probability, EV, live cross-category ranking or fallback-performance qualification is borrowed.

Original-site PR #1 [comment 6642441018](https://github.com/NickNicky19/nicks-expert-nfl-picks/pull/1#issuecomment-6642441018), posted November 4 at 21:22:14 UTC, was verified; no superseding receipt appeared on the latest checked discussion page. It records Count A blocked, zero new activations, incumbent retained. Corrected mean is `FORECASTS.parquet.point`; `legacy_point` mixes fallback and `mean` is NaN. Bare predict omits the trained-prior-mean corrector and can fall back to a median. C has not received/restored that complete private procedure and has not deserialized an untrusted joblib. Current-adapter parity is not established by a manifest or invented fixture.

At actual `lab-state` head `275aa84b27c4239d3b2dfea07755734d9db0ac7c`, registered `state/public/weekly-adaptive-v1/2026-W09` is absent, while its parent contains W07/W08. The latest W8 publication contains 143 rows, zero Count A rows, expired November 3 at 01:15 UTC, and uses different P2 median procedures. This is a missing current approved export, **not proof that the underlying model is missing**. It cannot be relabelled fresh Count A.

**Exact owner action:** A/the registered producer restores the complete existing model, features, preprocessing and mean-corrector; demonstrates retained-case and fresh-process current-adapter parity; then publishes permitted corrected-mean, eligibility, role, side, ranking, fallback and expiry fields with real source/issuance/server-persistence receipts through the existing admitted route. C can validate the derived packet; the original-site owner acknowledges/adopts it. This published disposition is coordination evidence, **not a delivered forecast packet or new consumer acknowledgement**. No blanket refit, general deployment permission, five new future weeks or public private-model migration is needed. No production write or workflow dispatch occurred.

## Capture and next finite work

The original C-v4 capture remains 2,513 forecasts / 407 roster candidates / 13 games. Final grades remain 1,532 played, 981 participation-unknown and zero pending, with zero original qualified actual-line selections. CMP/ATT blocks, fantasy-label/tail shadow and appearance conditioning remain; Thursday W8 was outside the capture. No original prediction or loss changed.

At November 5, 00:13:08 UTC, the registered status route returned native event `401873037`, JAX at BAL, 2026 REG W9, scheduled for **November 6, 01:15 UTC / Thursday November 5, 7:15 p.m. CST**. This retained observation is not a perpetually current status or forecast. The initial combined-query 400 failure remains preserved; the existing per-day route succeeded. There is **no new C or Count A pregame offer/selection packet** in this wave. Qualified fresh offers and the exact complete current Count A adapter/feed are absent. The old held offers and expired output cannot substitute; refresh event, roster, source and offer clocks again at issuance.

Next finite packages: A’s existing Count A producer delivery followed by C’s zero-fit parity/admission check; B’s confidence-ordering diagnosis and A’s common-case allocation diagnosis under their own budgets; C’s distinct next information mechanism only under a new finite registration. These two representations are closed without increment. Six-component gaps remain in the prior matrix; no injury, opponent, NGS or availability benefit is inferred here. Continue independently supported championship source/history joins without repeating failed equivalent fits.

C’s website applies this same ledger below the actual-prop scorecards, with explicit duration-only labels and no primary activation. Publication, served verification and scientific admission remain separate in the later publication receipt. No model promotion, precise six-leg probability, wager or original-site change.

Portable trace replay requires `C_VERIFIED_FACTS_DIR` pointing to the hash-verified existing facts input. The public failed-attempt source differs only in replacing its temporary directory literal with that environment variable; [normalization receipt](SOURCE_PORTABILITY_DELTA.json). Completed trace output is frozen and refuses another run.
