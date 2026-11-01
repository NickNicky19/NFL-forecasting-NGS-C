# Actual-offer source resolution — 2026-11-01

**No source has qualified for C actual-offer grading or new paper admission.** This is a source-specific hold, not a completed prop comparison. The executed work is structural source tracing, native identity reconciliation, saved-C identity coverage, and a tested exact-line grading/admission/site adapter. Zero NFL fits, zero new synthetic experiments, zero provider offer-endpoint calls, zero actual-offer outcome scores and zero new paper selections.

The original 2,513 v4 forecasts and all issue/model/persistence bytes remain frozen. Their accepted server receipt is 2026-11-01T00:13:48Z; selections created later cannot inherit it. The 407 roster candidates are not established participants/starters. Prospective outcomes remain pending. The original NGS recipe and adverse calibration results stand.

## Concrete producer and line lineage

Read-only repository: [nicks-expert-nfl-picks at 0f615dd](https://github.com/NickNicky19/nicks-expert-nfl-picks/tree/0f615dd95fb6684ffe84ccd978a49e620ed6ba6c). Exact file Git blob/SHA256/size/schema inventories are in [INVENTORY.json](INVENTORY.json); independent branch and offer-capture checks are in [BRANCH_TRACE.json](BRANCH_TRACE.json).

* `pull/books.py` (Git blob `406c24755aa9823311c01e3116662845854cf393`) reads ESPN core provider `100` propBets. Its explicit full-game/OT name map covers ten categories. It copies `current.target.value` into an internal `close` field and `open.target.value` into `open`. **The word close is a code label, not an authenticated closing quote/time.** Native ESPN athlete refs are used when possible; an inherited normalized-name/team fallback exists. The returned player/category map discards native market/event/athlete join lineage, offered sides, lifecycle and quote clocks.
* The same module reads Sleeper Picks `lines/available`, filters NFL/normal/pre_game options and takes an Over line or the first option's line. Per-side multipliers exist temporarily. Its legacy adapter does not establish that all sides are active or share one line, and discards native option/event IDs and quote clocks. The Picks route is separate from Sleeper's documented Fantasy API.
* `pull/build.py` (Git blob `13a09f2a3e02e1819432860ee98417cf445cad99`) initially generates model thresholds. `apply_book` replaces `line` with the ESPN/DK candidate or Sleeper fallback, records `line_from`/`our_line`, and **leaves the projection's `source=model/average` unchanged**. Thus a model/average projection tag does not make a `line_from=dk` threshold synthetic. This refines the earlier v4 qualification wording; no old report/score is overwritten.
* `archive_of` keeps line/projection/lean/category and coarse game/player identity, but drops the raw quote clocks/IDs/sides/prices/lifecycle. A started-player update can attach a subsequently retrieved line to an older projection. Global `saved_at` does not date every quote.
* `past_week` fetches lines for confirmed-final games and stores a bare category-to-line map. These weekly records are after-game retrievals. They are eligible only for a lower-tier timing-unverified diagnostic after rights and offered-side/contract qualification; they cannot prove original pregame picks.

## Inventory and dispositions

| Exact source subset | Actual retained coverage | Qualified | Held / rejected | Resolution |
|---|---|---:|---|---|
| Main pin `output/data/weeks/2026_w01.json`–`w07.json` | 5,066 unique player/game/category line views, 107 games, ten categories | 0 | All 5,066 held: provider analysis/public-retention scope, original offered sides/contract provenance; quote clocks absent | Applicable ESPN grant/export scope; recover side/contract provenance from original upstream evidence. Timing stays unverified if unrecoverable |
| Same weekly files, explicit ESPN identity subset | 1,843 views; all native ESPN/Sleeper/GSIS/week/team matches agree | 0 | Same rights/contract hold; no identity conflict | Small preselected initial diagnostic population; 1,807 have saved C case identity membership |
| Remaining weekly identities | 3,223 views uniquely map native Sleeper/week/team to GSIS | 0 | Original ESPN-to-Sleeper join/fallback lineage not retained | Recover native upstream mapping; do not guess name joins |
| Main pin `output/data/archive/2026_w08.json` | 622 DK-tagged + 19 Sleeper-tagged views; 568+19 have kickoff later than global save | 0 | 54 DK views already at/before kickoff; remaining 587 are stale archive candidates, not current offers | Fresh qualified quote/status/availability snapshot plus provider scope required for new paper admission |
| Same W8 mixed archive, generated thresholds | 1,400 `ours`; 438 fixed anytime-TD thresholds | 0 | Rejected as actual-offer evidence | Keep only in their original forecast/synthetic tier |
| Main archives W4–W7 | DK 755/668/676/617; Sleeper 0/14/16/32 | 0 | Mixed generated values and different issue horizons; no per-quote clocks | Qualify each source and snapshot separately; never combine best revisions |
| Main retained forecast captures | 338 W6 + 93 W7 `data/forward`; 2 W7 + 11 W8 `data/current-classic` files | 0 | Repeated quote views, not independent samples. All 444 canonical payload hashes verify; local capture clocks do not authenticate publication/quote age | Use original server publication evidence where recoverable; rights remain separate |
| Phase2 `data/offers/2026/w06/*.json.gz` at `81c3fc2a612ced916f4c54814f978c509058bca5` | Three Oct14 captures: 158 / 158 / 166 complete side rows; latest 83 O/U pairs, 73 players, ten games | 0 | Sleeper scope unqualified; quote freshness explicitly NOT_ESTABLISHED, original GitHub publication unauthenticated | Best retained side/identity/lifecycle lead. Existing provider grant first; publication/quote clocks determine evidence tier |
| Prior seasons | Four named branch trees plus main inspected; explicit 2025 paths are statistics caches | N/A | No 2025 actual-offer file found in this bounded search | Exact existing historical offer path/export needed, not a model rerun. This is not a claim about every uninspected branch |
| Earlier current-source sweep | KarmaEdge, FieldworkLines, QueryStation in frozen v4 review | 0 | Publication restriction / derived-or-stale board / no accessible licensed bytes respectively | Their exact gaps remain; no access bypass, signup or duplicate collector |

Weekly line counts W1–W7: **753, 738, 740, 764, 699, 705, 667**. Five passing categories each have 214; rush yards 637 (QB212/RB407/WR18), rush attempts399 (QB114/RB283/WR2), receptions1,319 (RB309/WR675/TE335), receiving yards1,330 (RB317/WR678/TE335), rush+rec311 (RB298/WR13). Anytime-TD and exact chart-PPR have no genuine market in these weekly files. Every row remains in the qualification denominator; population/role differences are not silent exclusions.

Native case membership finds **4,969/5,066** weekly views in saved C P2/H-MULTI/E0_OP files; 97 lack that C case. This checks identity membership only. Outcome version, role masks, contracts and quote cutoffs still need qualification. No errors, side wins or probability scores were inspected. A/B/C superiority and common scored samples remain N/A.

## The additional Week6 capture lead

The three immutable files and their byte/payload hashes are listed under `phase2_offer_capture` in BRANCH_TRACE. Producer source: `tools/offers.py` blob `5239439e197ea5f31d71d95cb628121c63ba638d`; `docs/OFFER_CAPTURE.md` blob `44ebfd5b0788c015b3b0bb5198739b07950cdd63` at the Phase2 pin.

Latest claimed collection: **2026-10-14T01:13:43.805087Z**. Complete sides: receptions54 Over+54 Under; rush attempts12+12; passing yards17+17. Retained raw options confirm active/pre_game/normal states, native Sleeper market/player/game IDs and matching paired lines, with zero structural conflicts. Earlier captures are separate revisions (158 sides each), not additional independent football outcomes. There are also 862 no-offer candidate-side rows in the latest 1,028-row universe.

All three Git blob hashes and canonical payload hashes were restored and verified. That does not establish the original publication time. Source `updated_at` is reported but the capture itself says quote freshness is not established; full-response digest cannot be reconstructed from the retained target-scope subset. Rules URL/hash receipts are not an exact entry quote or bookmaker settlement. No six-leg execution is established.

## Exact permission evidence and smallest owner action

The official [Disney/ESPN terms](https://disneytermsofuse.com/english/) (updated 2024-05-24), §§2A and2B(x), restrict public reuse and automated extraction; §2A expressly addresses ML training/testing/benchmarking. No applicable grant covering these ESPN offer records was found. Current terms do not establish the permissions that applied to each older acquisition.

The official [Sleeper general terms](https://support.sleeper.com/en/articles/5486620-general-terms-of-use) (updated 2026-10-06), §§9.2,11.1,11.3, restrict copying/redistribution and third-party extraction without applicable written approval. [Free Fantasy API documentation](https://docs.sleeper.com/) does not document or grant Picks `lines/available` use/redistribution. No applicable Picks grant was found.

**Nick does not need to build a new CSV.** The retained Week6 files already supply the smallest concrete structural starting point. The smallest unblocker is an **existing Sleeper authorization or approved licensed export scope** covering those exact records, C's automated research/benchmarking and minimal immutable public evidence: native IDs, line/comparator, offered sides/lifecycle, contracts and actual clocks. A public-safe grant/excerpt/reference with applicable dates is enough to review; do not post credentials or private agreement details. An applicable ESPN grant is an alternative for the wider weekly panel, with the extra historical side/clock limitations above. Nick's authorization alone cannot waive a provider's restrictions. No purchase or signup is requested.

Even after permission, missing historical quote/publication clocks stay missing. We can run a timing-unverified diagnostic where the remaining contracts qualify; we cannot retroactively authenticate it. New current offers require fresh independent observation/status and their own pregame GitHub persistence.

## Executable continuation

[PAPER_RUNBOOK_V5.md](../../protocol/PAPER_RUNBOOK_V5.md) documents manual permission review, exact-line P1/P2 replay, immutable prospective packet creation, PR/server receipts, grading and site projection. Existing blocked providers fail before scoring/writing. Positive and negative code paths use conspicuously fictional software fixtures, not counted NFL observations. The website consumes a separate exact-offer manifest; v4 forecast data is unchanged.

Next bounded wave: review one applicable existing grant/export; normalize the three retained Week6 captures with a single frozen snapshot rule; grade saved points first on all qualified exact cases; evaluate eligible saved full laws at those same lines without grid interpolation; then capture a fresh independently qualified current subset before kickoff. No completed NFL fit or broad synthetic experiment is needed. If no grant exists, the source holds remain visible and the original future forecasts remain available for later official grading.
