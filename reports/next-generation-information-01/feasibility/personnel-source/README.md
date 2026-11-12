# Personnel-source feasibility — Session C

**Decision: SOURCE_BLOCKED for the proposed historical personnel-conditioned receiving-redistribution test.** The actual 2026 injury file has relevant rows but no row clock or historical report versions. The inspected roster evidence also does not establish a complete historical pregame teammate universe. No fit or forecasting-accuracy claim was made.

This is a new proposed information block: teammate official game-report designations and qualified role changes, rather than another target-share average, profile, defense or recency arm. Newness does not establish availability or usefulness. [FEASIBILITY.json](FEASIBILITY.json) records the bounded decision and exact missing artifacts.

## Actual source result

The public nflverse injury file was observed on **November 12, 2026 at11:52:46am America/Chicago** (`17:52:46Z`). Its65,923 compressed bytes had SHA-256 `36c933c378dd06eca5f4d43b1891412ba2d0e632ff0df85ddaddaf32e40ca0d8`. HTTP Age was3,161 seconds; Last-Modified was15:56:22Z. Those are response/file clocks, not each player's information clock, and do not prove the source was the newest available.

| Week2026 | Reported injury rows | WR/TE rows | Teams represented | Row-clock coverage |
|---|---:|---:|---:|---:|
| W1 |182|30|32|0|
| W2 |251|40|32|0|
| W3 |301|49|32|0|
| W4 |318|56|32|0|
| W5 |361|72|30|0|
| W6 |376|79|28|0|
| W7 |350|62|28|0|
| W8 |320|58|28|0|
| TotalW1–8 |2,459|446|not additive|0|

The file contains3,097 rows through W10. These are report rows, not all players or a complete eligible team roster. All source fields are bound in [CURRENT_INJURY_SOURCE_RECEIPT.json](CURRENT_INJURY_SOURCE_RECEIPT.json); [ACTUAL_COVERAGE.json](ACTUAL_COVERAGE.json) preserves statuses, missingness and unique-identity checks. There were no duplicate season/week/team/GSIS identities.

The [official dictionary](https://nflreadr.nflverse.com/articles/dictionary_injuries.html) describes `date_modified` as an update clock. **The obtained2026 file has no `date_modified`, report date or other row clock.** Documentation is therefore insufficient even for a declared earlier-updated timing reconstruction from these bytes. The fraction revised after a historical decision cannot be measured; it must not be reported as zero. Current W10 labels alone do not prove event-effective applicability to a future query.

## Retained snapshots and genuine limits

The C snapshot observed November2 at19:30:04Z retains26 W8 SEA/CHI report rows, including3 WR/TE rows, before that game's listed kickoff. These26 designation/practice pairs match the new download. This is genuine narrow pregame evidence; it does not supply W1–8 training coverage or the complete teammate denominator.

The November5 snapshot retains266 W9 report rows. Of these, **187 differ** in designation and/or practice status in the November12 vintage;79 are unchanged. This demonstrates historical source-vintage changes, not any measured model contamination or accuracy effect. Original files/hashes remain intact. [RETAINED_VINTAGE_COMPARISON.json](RETAINED_VINTAGE_COMPARISON.json) binds the exact changed identities/fields, with source hashes in [RETAINED_SOURCE_BINDINGS.json](RETAINED_SOURCE_BINDINGS.json).

Null/empty game designation and an absent injury row do not establish healthy, active, starter, DNP or a statistical zero. Practice participation differs from game participation. The current-known-season roster is already available information and does not authenticate past event-effective teams or starters. The existing stat-row-conditioned receiving pool cannot supply missing pregame teammates; all eligible players and an other/unallocated bucket are required for an allocation claim.

2024/2025 assets were verified in release metadata only. Their rows and historical clocks were not inspected; this receipt makes no blanket claim that every older source is unavailable.

## Permissible next action

Session C's source/intake owner needs immutable, permitted predecision report snapshots or genuinely versioned source clocks for the declared origins, plus a full event-effective historical teammate universe. Existing sources may instead supply prospective facts after their real observation; current event/role applicability still needs admission. Use existing authorized jobs/manual routes. No new collector, scheduler, paid acquisition or arbitrary injury multiplier is authorized. Original-site delivery and eligible older candidates continue independently.

[PERSONNEL_STATUS_SCHEMA.json](PERSONNEL_STATUS_SCHEMA.json) defines the proposed shared factual contract; it does not fit a model or assign role probabilities. Source-qualified expected role, target redistribution, future exposure and predictive gain remain unestablished.

## Rights and reproducibility

Current public repository metadata declares [CC-BY-4.0](PUBLIC_REPOSITORY_LICENSE_METADATA.json), corroborating C's existing minimal nflverse factual-retention route. The retained212,204-byte projection omits names, injury descriptions and presentation, preserving IDs/designation/practice facts. Attribution, original licensed-source reference and modification notice are in [ATTRIBUTION.json](ATTRIBUTION.json). No raw news, protected charting, market payload or off-GitHub archive was created.

Run `python reports/next-generation-information-01/feasibility/personnel-source/reproduce_personnel_source.py` from C to recompute the retained projection hash, row counts and cross-vintage arithmetic. It ran successfully in Python3.12 using only the standard library, with0 fits. [REPRODUCTION_RECEIPT.json](REPRODUCTION_RECEIPT.json) states its scope. A separate reviewer [independently checked the retained projection and cross-vintage arithmetic](../evaluation/PERSONNEL_PROJECTION_INDEPENDENT.json), reproducing2,459 W1–8 rows,446 WR/TE rows and187/266 changed W9 rows without another GET or the author's summary functions. That check is not raw-source, historical-clock or model-fit parity. The original compressed/full CSV bytes were temporary in memory: their hashes and original field list were measured during extraction, and **cannot be independently recovered or reverified offline from the projection**. Optional `--source-gzip` checks supplied exact bytes against those hashes before reconstruction; that mode was not executed. [ROW_INSPECTION_COMMAND.txt](ROW_INSPECTION_COMMAND.txt) preserves the successful bounded command without authorizing another read.

The eight-read budget is closed, including two404 documentation attempts and one connector-rejected license endpoint. The sandbox-denied connection for the authorized data read obtained no bytes; the same bounded URL succeeded through normal network approval. [READ_LEDGER.json](READ_LEDGER.json) records all attempts. No source sweep, model fit, current forecast, new scored week or release resulted.
