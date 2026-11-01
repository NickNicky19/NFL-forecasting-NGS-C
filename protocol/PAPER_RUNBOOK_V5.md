# Manual exact-offer replay and paper admission

This path performs **zero collection and zero model fitting**. It is reusable for later unplayed weeks. C's original v4 forecast commands remain separate. No recurring or unattended future run is active.

## 1. Review a concrete source once, then each exact export

The current [source registry](OFFER_SOURCE_REGISTRY_V5.json) deliberately blocks both traced providers. Do not change its flags based only on a packet assertion, Nick's repository ownership or public availability. Review applicable existing provider/license/export evidence covering automated analysis and public immutable minimal quote/native-ID/clock/contract retention. Retain a permitted public-safe grant or excerpt under `protocol/`, its SHA256, provider, applicable dates, granted scope, review ID and approved exact export SHA256. Scope must actually grant `automated_analysis`, `public_quote_retention`, `identities_clocks_contracts`; strings such as "false" and denied scopes are rejected.

Before amending a qualified registry entry, preserve its canonical digest in `retained_review_SHA256`, permission bytes and applicable dates. This lets later approved exports coexist with old immutable packets. Changing the scientific/selection policy needs a new version/validator; v5 does not silently repair old packets. Source restrictions can require a different licensed source; do not purchase, sign up, bypass blocks or upload restricted bytes to satisfy this step.

## 2. Historical line-only grading first

Use a permission-cleared `C-HISTORICAL-EXACT-OFFERS-v5` JSON packet containing `source_id`, `offers` and `forecasts`. Each offer has record_kind ACTUAL_OFFER, exact venue/product/tier/offer ID, native event/version/kickoff, game/player/category, period FULL_GAME_INCLUDING_OT, scoring_contract_id, exact line/comparator, genuinely offered_sides, identity/source evidence references and whatever clocks actually exist. Unknown clocks stay null. No invented −110 price, generic six-leg payout or synthetic line is needed.

Each forecast contains its actual original method/slot ID, forecast ID, identity/kickoff, information cutoff, typed saved mean/median and `retained_forecast_evidence` (relative recoverable file) plus SHA256. The adapter opens that file, requires a unique original row and compares points/contract/cutoff/kickoff. Never edit a point or substitute the best later revision. An exact full law is optional; it must itself match retained full-law bytes. A saved probability grid cannot be rounded/interpolated into an actual-line law. Restoring a correctly versioned retained model for necessary inference is separate work, not a refit.

Outcomes use `C-OUTCOMES-v4`: verified official numerical facts, retained source-file hashes, version, unique category identities, exact native event/kickoff/contract, final-state and observation clocks, appearance and actual. Preserve played zero versus DNP/unknown/missing; counts must respect their lattice and yards may be signed. Anytime-TD needs actual rushing/receiving event components; chart-PPR needs all exact components and deduplicated credits.

```
python src/paper_v5.py historical --input paper/historical/approved-input.json --outcomes paper/outcomes/versioned.json --output paper/historical/result-v1.json
```

This writes immutable rows, P1 and supported P2 grades plus category own-side counts and probability scores. P1 works without a law or price. These imported historical files remain timing-unverified diagnostics unless a separately versioned stronger timing audit qualifies. All methods use the same offer identities; absent predictions remain unavailable. Empty pools have N/A rates. The first preselected trace population is in ACTUAL_OFFER_WORK_PACKAGE_V5.json; no actual performance has yet been graded.

## 3. New current paper input

Use an approved `C-ACTUAL-OFFERS-v5` packet with `source_id`, `offers` and `event_status`. It may be a small independently qualified subset. It must be new current evidence, not the old archive with a new timestamp. Every offer additionally needs source_asof_UTC <= observed_at_UTC <= current decision cutoff, age <=900s; OPEN lifecycle and genuinely OPEN offered sides; current availability review; and the exact v4 native event/kickoff/stat contract. Event status must verify `pre`, `STATUS_SCHEDULED`, completed=false and matching native event/kickoff within1800s. Missing news does not mean healthy. The forecast remains participation-conditioned, not an appearance/nonvoid law. OUT/doubtful flags, CMP/ATT conflicts or unchecked coherence, chart-label shadow and started/too-close games block selections.

Freeze code/policy/registry in a clean C commit before creation:

```
python src/paper_v5.py prepare --input paper/incoming/approved-current.json --output paper/runs/C-PAPER-v5-UNIQUE-ACTUAL-CLOCK
python src/paper_v5.py verify --root paper
```

The command sets its **actual current** decision/creation clocks. It chooses the latest observation per native offer ID before cutoff; identity conflicts reject. A later closed/suspended quote suppresses an earlier OPEN version. One deterministic latest-observation quote per player/game/category/venue/product is primary in the batch, with native offer ID as tie-break. No offer outcome influences selection. Strict point equality abstains. P2 uses exact Under/Push/Over, abstains on ties, and cannot invent an unavailable side. Anytime-TD only selects YES when genuinely offered. Prices remain optional for these statistical directions.

Prepare writes offers, evaluated exact-line rows, the original forecast-ID bindings/server receipts, reviewed permission bytes and a file-hashed RUN. It never overwrites a destination or changes original v4 forecasts. Do not label it authenticated paper issuance yet.

## 4. Persist before kickoff, then admit separately

Commit/push only C's permission-cleared packet. Open a C PR through normal controls. Its successful **Verify immutable paper captures** step validates exact bytes, bindings, contracts and current cutoff. Before the publication buffer expires, generate a new server receipt bound to that exact successful PR head/run:

```
python src/paper_v5.py receipt --run paper/runs/RUN_ID --commit EXACT_CHECKED_HEAD --workflow-run SUCCESSFUL_PR_RUN --output paper/receipts/RUN_ID.json
```

It freshly downloads the exact GitHub files, verifies hashes and requires the server's checks-completion clock before every kickoff minus300s, and quotes within900s at persistence. It never uses the forecast's earlier issue time as a selection clock. Commit/push the receipt, verify/merge through normal controls, then build the separate site projection:

```
python src/site_paper_v5.py build
python src/site_paper_v5.py validate
```

Website data is separate from frozen `docs/data/forward/*`. The site shows exact lines/venue/observed/decision/selection-persistence clocks, raw conditional probabilities and missing states. Frozen probability ranks stay within venue/product/tier/issuance group. No entry or value admission follows automatically. Display-only clock checks expire offers without any network refresh or collector. Started/expired/superseded records cannot remain actionable. Price mode stays unavailable until separately qualified.

## 5. Predict, preserve, then grade

After actual official final outcomes and appearance evidence arrive:

```
python src/paper_v5.py grade --run paper/runs/RUN_ID --outcomes paper/outcomes/versioned.json --output paper/grades/RUN_ID-outcome-v1.json
```

The first qualified paper snapshot per player/game/category/venue/product is primary. Later immutable revisions cannot replace it after observing outcomes. Statistical wins/losses/pushes and DNP/unknown/pending are separate from unverified bookmaker settlement. Retain the outcome/source packet with the grades, all losses, and append-only corrections. No original 6/6, payout, profit or independence claim is possible without its separately qualified entry evidence.

Current state: code/fixture paths implemented; **zero qualified real-offer packets, zero paper receipts, zero graded actual NFL offers**. A first real source review and server-persisted packet remain necessary to demonstrate operational paper issuance. This runbook does not assert that unavailable permissions have been obtained.
