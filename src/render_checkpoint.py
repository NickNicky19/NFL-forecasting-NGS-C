"""Render retained aggregates only; never fit or regenerate forecasts."""
from pathlib import Path
import json
import pandas as pd

def render(root):
 n=pd.read_csv(root/'NUMERICAL.csv');pairs=json.loads((root/'PAIRED.json').read_text());ledger=pd.read_csv(root/'ABC_COMPARABILITY.csv')
 lines=['# Executed five-category NGS comparison','',
 '**Targeted NGS values have not established a persistent gain beyond historical support/opportunity information.** This checkpoint completes the registered numerical reconstruction across all79weekly origins. Probability/offer-side and exact A/B head-to-head comparisons remain unestablished. No production package is proposed.','',
 'C0 = reconstructed strong HGB-L1 direct point; C1 = C0 + eligible earlier NGS availability/age/metric-specific opportunity support; C2 = C1 + registered raw values. These are unchanged learner/panel/update/cutoff comparisons inside C. They are not exact B reproduction or victories over A/B printed headline scores. See [baseline binding](../BASELINE_BINDING.md).','',
 '## Table A — numerical NGS effect','',
 'MAE is in the category’s native units. Delta columns are C2−C0 / C2−C1, so negative is lower error. CI is the paired95% game-cluster C2−C0 interval; week intervals, relative changes and all weeks/subsets remain in [PAIRED.json](PAIRED.json) and [NUMERICAL.csv](NUMERICAL.csv). Intervals are descriptive exposed research, unadjusted for repeated tests.2026has only seven week clusters. Prediction coverage is100% of this retrospective query panel; gradable coverage is the displayed outcome/query ratio. No authenticated pregame-roster completeness is claimed.','']
 for year in [2026,2025]:
  lines += [f'### {year} regular season'+(' Weeks1–7' if year==2026 else ' all eighteen weeks'),'',
   '| Category/group | C0 baseline | C1 support | C2 values | Delta vs C0 / C1 | Outcomes/games | Outcome coverage; fallback | NGS queries | Game CI vs C0 |',
   '|---|---:|---:|---:|---:|---:|---|---:|---|']
  for target,horizon in [('pass_cmp','ALL'),('rec_yd','ALL'),('pass_yd','ALL'),('rush_yd','ALL'),('rush_yd','RB'),('rush_yd','QB'),('rec','ALL')]:
   z=n[(n.season==year)&(n.target==target)&(n.horizon==horizon)].set_index('arm');a=z.loc['C0'];b=z.loc['C1'];c=z.loc['C2']
   p=next(x for x in pairs if x['season']==year and x['target']==target and x['horizon']==horizon and x['control']=='C0');q=next(x for x in pairs if x['season']==year and x['target']==target and x['horizon']==horizon and x['control']=='C1')
   label=target+(' '+horizon if target=='rush_yd' else '')
   lines.append(f'| {label} | {a.mae:.6f} | {b.mae:.6f} | {c.mae:.6f} | {p["delta"]:+.6f} / {q["delta"]:+.6f} | {int(a.outcomes)}/{int(a.games)} | {int(a.outcomes)}/{int(a.queries)}; {int(a.fallback_queries)} | {int(a.ngs_queries)}/{int(a.queries)} | [{p["game_ci"][0]:.4f}, {p["game_ci"][1]:.4f}] |')
  lines.append('')
 lines += ['## Table B — each method’s own selections','',
 'Period for every row:2022–2025full regular seasons and2026W1–7. There is no admitted exact offer/identity/cutoff export. HGB points supply no law. N/A means technically unavailable, not intentional abstention or zero selections. Prices and settlement remain unestablished. Software fixtures do not create NFL wagers or threshold observations.','',
 '| Category | Exact arm/method | Over W/L/decided/rate | Under W/L/decided/rate | Combined W/L/decided/rate | Coverage | Evidence tier |',
 '|---|---|---|---|---|---|---|']
 for t in ['pass_cmp','rec_yd','pass_yd','rush_yd','rec']:
  for arm in ['C0','C1','C2']:lines.append(f'| {t} | HGB-L1 reconstructed/{arm}/P1 or unavailable P2 | N/A | N/A | N/A | N/A | No admitted offers; point-only |')
 lines += ['', 'No original selections, top6/10/20, pushes, voids, pending, unknown-offer participation, bookmaker nonvoid or price outcomes can be counted without the missing offer contract. None is silently set to zero. Neutral/prevalence and football probability controls remain unavailable on real offers; no law is manufactured from point errors.','',
 '## Table C — A/B reference matching','',
 '| Category | A reference | B reference | C candidate | Exact common sample | Same-row errors/side results | Unmatched/limitations |','|---|---|---|---|---|---|---|']
 for r in ledger.itertuples():lines.append(f'| {r.category} | {r.A_reference} | {r.B_reference} | HGB C0/C1/C2 | N/A | N/A | C queries {r.C_queries}; outcomes {r.C_supported}. Exact A/B membership/prediction/label exports not restored |')
 lines += ['', 'Shared/A-only/B-only/C-only memberships, actual-version disagreements and common-intersection metrics remain null, not inferred from counts. C’s internal same-row comparisons are established; source schedules alone cannot prove player/label equivalence. A rushing headline is RB-only; C reports RB and QB separately. See [machine ledger](ABC_COMPARABILITY.csv).','',
 '## Persistence and adverse findings','',
 'The table below shows C2−C1 MAE for each season. A small gain against C0 can coexist with a loss against support-only C1. Historical seasons were already used for research.','',
 '| Category/group | 2022 | 2023 | 2024 | 2025 | 2026 W1–7 |','|---|---:|---:|---:|---:|---:|']
 for t,h in [('pass_cmp','ALL'),('rec_yd','ALL'),('pass_yd','ALL'),('rush_yd','ALL'),('rush_yd','RB'),('rush_yd','QB'),('rec','ALL')]:
  v=[next(x['delta'] for x in pairs if x['season']==y and x['target']==t and x['horizon']==h and x['control']=='C1') for y in range(2022,2027)]
  lines.append('| '+t+(' '+h if t=='rush_yd' else '')+' | '+' | '.join(f'{x:+.6f}' for x in v)+' |')
 lines += ['',
 'Pooled C2−C1 is adverse for completions, passing yards, receptions and rushing yards. Receiving yards improves by only about0.000404yards beyond C1. Values win in1/5completion seasons,2/5passing-yard seasons,2/5reception seasons,4/5receiving-yard seasons and3/5pooled-rushing seasons. These effects do not establish a broadly useful raw-quality recipe. No confirmation learner was fitted or retroactively selected to rescue a weak result. A stronger distributional comparison requires its own finite registration and exact baseline qualification.','',
 '2026receiving-yard MAE improves by0.159yards versus C0, but support-only already supplies0.156yards of that difference.2025completion C2 improves by0.134completions versus C0 but **worsens** by0.011versus C1.2026QB rushing worsens against both controls; QB prior rushing-NGS coverage iszero, so its forecast changes arise indirectly through the pooled QB/RB learner, not direct QB tracking measures.2022startup remains in full-system scores: completions have107fallback queries and106scored fallback outcomes per arm.','',
 'All arms preserve the same full forecast and gradable coverage. Gains are numerical point-error changes, not broader forecast coverage. No conclusion about improved probabilities, selected Over accuracy, selected Under accuracy, combined selection accuracy or price-aware value is established. Native-unit errors do not rank categories against each other.','',
 '## Execution, verification and retention','',
 'Actual execution:1,185unique slots =1,149fits +36startup fallback slots,79weekly origins;184,335arm forecast rows on61,445query/category rows and58,185supported category outcomes. Outcome rows overlap categories and are not independent football observations. CPU257.24seconds, wall257.41seconds across fit invocations, peakRSS660,787,200bytes. Zero hyperparameter searches, no refits for table rendering, no source collector/scheduler/production writes/API-credit spending.','',
 '[Independent verifier](../INDEPENDENT_CHECK.json) reconciled all retained numerical metrics, masks, labels,324original paired contrasts and representative baseline/candidate model inference; pilot checks additionally cover future/target feature and forecast mutation invariance. Eleven software tests include signed-zero/push/half-point arithmetic, missingness and training-only transformations. No actual-offer win/loss/boundary or probability verification is claimed.','',
 '[Full restoration receipt](../RESTORATION_RECEIPT.json):8,473,049source bytes and30,700,114execution archive bytes recovered byte-for-byte from private Library. Every ZIP entry passed. Restricted bytes/models remain private; public Git has only code/aggregates/safe manifests. The Drive quota failure and cumulative scratch guard limitation remain in [failures](../FAILURES_AND_LIMITATIONS.md) and [resource accounting](../RESOURCE_ACCOUNTING.json).','',
 'Complete records: [every weekly/season/startup/subset metric](NUMERICAL.csv), [paired changes/uncertainty](PAIRED.json), [micro and season-balanced summaries](MICRO_AND_SEASON_BALANCED.csv), [stable result IDs](RESULTS_INDEX.csv), [unavailable selection cells](SELECTIONS.csv), [run receipt](RUN_RECEIPT.json). Old pilot and separate continuation outputs remain unchanged.','',
 '## Category recommendation and exact next dependency','',
 '- **Completions:** support information is more promising than this values group; raw values lose to C1 in four seasons.','- **Receiving yards:** small C2-versus-C0 improvement persists, but almost all is C1 support. No established material value increment.','- **Passing yards:** values reverse across seasons;2023/2024/2025lose to C1.','- **Rushing yards:** modest pooled/RB gains are mixed;2026QB worsens and direct QB NGS coverage isabsent.','- **Receptions:** tiny mixed point changes, with2026values worse than support-only.','',
 '**No category package advances to production-owner review from this raw-values recipe.** This is a study recommendation, not a new universal admission rule or waiting period. Exact strong A/B models/row/label exports, approved offers with identity/cutoff contracts and a legitimate law are the next comparison dependencies; excluded derived fields need their version/denominator bridge. Missing these does not erase the completed internal numerical evidence. [Finite queue](QUEUE.json) records zero additional fits until a new bounded comparison is registered.']
 (root/'README.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':render(Path(__file__).resolve().parents[1]/'reports/complete-v1')
