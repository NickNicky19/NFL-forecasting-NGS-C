The existing common coverage ledger now has a versioned continuation:
[W1_W9_AND_HISTORY_COVERAGE_V2.csv.gz](../../category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V2.csv.gz).
It preserves all 31,527 prior entries and their complete decoded CSV bytes,
then appends 576 admitted owner aggregates, for **32,103 unique entries**.

The additions are 48 complete B side triads retaining all 144 source side records,
and 528 A historical summaries. They add coverage/admission of existing results:
zero new forecasts, NFL games, 2026 evaluation weeks, grading, inference or fits.

| Addition | Supported scope | Limits |
|---|---|---|
| B interception measurement | Frozen 144 board; 86 stored sides, W5–9 | Original versus corrected labels are distinct measurement versions of unchanged predictions/lines/sides. Top flags and full144/same86 constants remain separate. |
| A completions 2024 | Actual scored W1–18; early/full views retained | Named historical book, current-vintage seven-day reconstruction; original quote timing/issuance unverified. |
| A completions 2023 | Actual scored W6–18 | Requested early weeks remain visible; zero-decided views are not tests. |
| A Backfield 2024 | Declared early/full and Top6/role masks | Mixed roles preserved. Weekly simultaneity unverified; Top6 is retrospective, not authenticated tickets or a new primary ranker. |

B's original 33/40 plus 46 unknowns and corrected 47/86 are both retained.
The change is measurement, not a forecast improvement. B supplied explicit
dual-source reported-zero evidence for the 46 previously unknown outcomes;
C did not fill them from participation or missing values. Corrected 47/86
versus same86 Always-Under 46/86 remains a one-win, uncertain difference.
The 86 stored lines are DraftKings-labelled: 85 at 0.5 and one at 1.5;
main/alternate tier, original quote timing and settlement remain unverified.
The eligible original board remains144, with86 stored sides and58 genuine
no-leans. Separate full144 controls cannot be pooled with same86 controls.

The ledger keeps each method's own O/U/combined counts together; it does not
splice side leaders. Unknown or unavailable fields remain empty, explicit zeros
remain zero, and raw false/null declarations remain typed in `additional_metrics`.
The 81 A and nine B zero-decided views remain `NO_SCORED_OUTCOME_NOT_TEST`.
Numerical/probability results are separately typed metadata, never extra actual-
offer observations. Full/early/weekly/role/Top6 views overlap and must not be summed.

`games` retains the stated source-pool scope: B's all-window144 controls use72
board games; stored-side and same86 views use61 selected-pool games, which may
include unresolved original labels. Missing per-window or TopFlags game counts
stay empty. The exact scored-week arrays are in `additional_metrics`, alongside
the original source period, comparison mask, fallback and source limitations.

[BUILD_RECEIPT.json](BUILD_RECEIPT.json) binds immutable inputs/output and resource
use. [APPEND_ENTRY_MAP.json](APPEND_ENTRY_MAP.json) maps every appended source view
to its complete-entry ID. [INDEPENDENT_READBACK.json](INDEPENDENT_READBACK.json)
uses a separate stdlib/Decimal calculation to check every mapped side scalar,
empty-side rates and all eight B weekly/cumulative partitions. It imports no
builder, scorer or grader. Owner-local private-row, fit, source-clock and A/B
common-mask parity remain outside this public aggregate admission.

Both scripts refuse output overwrite. Root alone updates existing canonical
discovery pointers. This is a version of the existing ledger, not a new registry.
