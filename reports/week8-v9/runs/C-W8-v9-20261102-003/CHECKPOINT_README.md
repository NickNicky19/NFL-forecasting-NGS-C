# Week 8 results to date — original pregame forecasts

Actual-line scorecard first. All12categories: **original C actual-line selections: none; qualified retrospective actual-line replays: none**. No qualified Week8line was recovered. Over/Under/combined W–L, hit rates, side differences and category leaders are N/A, not zero-loss records. Prices/entry payouts are not the missing gate.

|Category|Original actual-line Over/Under/combined|Retrospective exact-line Over/Under/combined|Forecast rows|Pending|Evidence|
|---|---|---|---|---|---|
|Passing Yards|N/A / N/A / N/A|N/A / N/A / N/A|71|6|No qualified actualWeek8line; original forecasts serververified|
|Passing TDs|N/A / N/A / N/A|N/A / N/A / N/A|71|6|No qualified actualWeek8line; original forecasts serververified|
|Completions|N/A / N/A / N/A|N/A / N/A / N/A|71|6|No qualified actualWeek8line; original forecasts serververified|
|Pass Attempts|N/A / N/A / N/A|N/A / N/A / N/A|71|6|No qualified actualWeek8line; original forecasts serververified|
|Interceptions|N/A / N/A / N/A|N/A / N/A / N/A|71|6|No qualified actualWeek8line; original forecasts serververified|
|Rushing Yards|N/A / N/A / N/A|N/A / N/A / N/A|168|16|No qualified actualWeek8line; original forecasts serververified|
|Rush Attempts|N/A / N/A / N/A|N/A / N/A / N/A|168|16|No qualified actualWeek8line; original forecasts serververified|
|Receptions|N/A / N/A / N/A|N/A / N/A / N/A|336|25|No qualified actualWeek8line; original forecasts serververified|
|Receiving Yards|N/A / N/A / N/A|N/A / N/A / N/A|336|25|No qualified actualWeek8line; original forecasts serververified|
|Rush + Rec Yards|N/A / N/A / N/A|N/A / N/A / N/A|336|25|No qualified actualWeek8line; original forecasts serververified|
|Anytime TD|N/A / N/A / N/A|N/A / N/A / N/A|407|31|No qualified actualWeek8line; original forecasts serververified|
|Fantasy Points (PPR)|N/A / N/A / N/A|N/A / N/A / N/A|407|31|No qualified actualWeek8line; original forecasts serververified|

Most accurate Over category: **NOT ESTABLISHED**. Most accurate Under category: **NOT ESTABLISHED**. Combined/category-side leaders: **NOT ESTABLISHED**. No actual-line selections have been scored for Week8. EarlierW2–3v7/v8diagnostics stay separate.

## Forecast-only numerical and event accuracy

**12completed captured games;Chicago–Seattle remains pending.** Original2513forecastrows/407roster player-games remain unchanged. The latest version grades1441scalar/eventforecast views for239physically evidenced player-games, with873unknown-participation views/137finalgameplayers and199pending views/31Mondayplayers. Scalar/category views are overlapping, not independent games. No missing source row or allzero stat row becomes DNP or zero.

|Category|Method arm|Issued/final/graded|Unknown/pending|Median MAE|Mean RMSE|Mean bias|CRPS|NLL|
|---|---|---|---|---|---|---|---|---|
|Passing Yards|E0_DEF|71/65/31|34/6|75.1613|97.2785|22.7872|53.3929|5.7349|
|Passing TDs|E0_DEF|71/65/31|34/6|0.9355|1.1866|0.0712|0.6233|1.3734|
|Completions|E0_ENV|71/65/31|34/6|6.7742|8.4400|2.8325|4.7280|3.4598|
|Pass Attempts|E0_ENV|71/65/31|34/6|8.8387|11.4443|4.6189|6.2191|3.6116|
|Interceptions|E0_ENV|71/65/31|34/6|0.6452|0.9431|-0.0826|0.4335|1.1039|
|Rushing Yards|E0_OP|168/152/92|60/16|19.8478|30.7959|-1.6141|14.3319|4.1147|
|Rush Attempts|E0_OP|168/152/92|60/16|3.5326|4.8441|-0.1734|2.4454|2.6828|
|Receptions|E0_ENV|336/311/208|103/25|1.2452|1.7673|0.1208|0.8871|1.7098|
|Receiving Yards|E0_DEF|336/311/208|103/25|17.5048|27.2629|-0.5551|12.8397|3.7886|
|Rush + Rec Yards|E0_DEF|336/311/208|103/25|22.3173|33.2180|-2.6153|16.3696|4.2879|
|Anytime TD|E0_OP|407/376/239|137/31|N/A|N/A|N/A|0.1581|0.4867|
|Fantasy Points (PPR)|E0_ENV|407/376/239|137/31|5.0192|6.9217|-0.0217|3.5249|5.4394|

AnytimeTD is the inherited rushing-or-receiving event, not an offered YES/NO market. Brier 0.158110; postgame diagnostic from original captured role-prior 0.174730; neutral0.25. Eventprobability mean 0.2019 vs actualeventfrequency 0.2259; N=239. No passing/returnTD is a rushing/receiving TD. Numerical/Bernoulli scores cannot establish sportsbook hit rates.

All methods are original C-FORWARD-P2-v4/P2_LEAF/H-MULTI with the frozen percategory arm. Means use MSE/RMSE; median MAE stays separate. Exact/tail/interval, support/role, validplayedzero, fallback and game-block diagnostic uncertainty are in SUMMARY/ROLE_SUPPORT. Oneweek/12games and appearance conditioning limit interpretation. No model/side/history winner is chosen from these outcomes.

## Source, corrections and limits

The bounded refresh at2026-11-02T18:48UTC confirmed12nativeFINALevents and oneunplayed event. NativeGSIS/game/team/kickoff and officialstat contracts are matched. NFLverseCCBY4 factual projections exclude EPA/CPOE/NGS/headshots and generic fantasy totals. No original forecast, model, capture clock or receipt is edited. Original2,513rows are the scoring universe; no targetgame reporting threshold selects membership.

All001/002/003packets and grades remain. Version002 corrects the initial omitted-but-available completions column:31actuals recovered, no new fits. Version003 qualifies one previously unresolved chartactual using native kickoff-returnTDplay1385: DylanLaube scores6under nick-chart-ppr-v1; his AnytimeTD actual remains0. Otheractuals stay unchanged. Full unmodified MITproducer source plus copyright/pins document separate2pt statIDs and directlost-fumble totals, counted once. The release buildcommit is not independently authenticated merely from its filedate.

Chart forecasts remain label-coverage-limited shadows even though the single rare-positive actual is now qualified. CMP/ATT original contradictions continue to block affected selections; no numerical forecasts are capped. No authenticated injury-exit diagnosis or complete inactive/appearance feed is claimed. Allzero or missingphysicalproof rows stay unknown; originalrole/sourceposition differences remain auditable.

## Evidence and operation

[Canonical graded forecast rows](GRADED_FORECAST_ROWS.csv.gz) · [Numerical CSV](NUMERICAL.csv) · [Roles/support](ROLE_SUPPORT.csv) · [Actual-line state CSV](ACTUAL_PROP_SCORECARD.csv) · [Version registry](GRADE_VERSION_REGISTRY.json) · [Source disposition](OFFER_QUALIFICATION.json) · [Independent review](INDEPENDENT_GRADE_AUDIT.json).

Original pregame selection, retrospective actual-line replay and forecast-only results are separate products. No synthetic threshold, guessed line, bestrevision selection, fabricatedNOside or sharedthreshold result populates the prop scorecard. No original6/6 or two-entry/payout/netprofit record exists. No modelpromotion follows from this grading.

Replay with `python src/week8_report_v9.py validate`; do not refit. New source-qualified outcomes get a new immutable packet and grade version. Grading newly eligible completed games precedes any future refit under the existing policy. [Prospective Results website](https://nicknicky19.github.io/NFL-forecasting-NGS-C/#prospective). [GitHub restoration](GITHUB_RESTORE.json) and [publication acceptance](PUBLICATION.json) are appended only after actual checks.
