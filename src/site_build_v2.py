"""Build a static evidence site from retained forecast rows, never new fits."""
import json,gzip,hashlib
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
from contracts_v2 import CATEGORIES
def build(run,docs,report):
 data=docs/'data';data.mkdir(parents=True,exist_ok=True);index=[];total=0
 for d in sorted(run.glob('*/DONE.json')):
  root=d.parent
  with gzip.open(root/'rows.json.gz','rt') as f:rows=json.load(f)
  if not rows:continue
  r=rows[0]
  if r['arm']!='E0_OP':continue
  name=f'{r["target"]}-{r["history"]}-{r["family"]}-W{r["week"]:02}.json';out=[]
  for p in rows:
   row={k:v for k,v in p.items() if k not in ['features','grid_logloss','nll','reference_over','reference_brier']}
   fv=p['features'];row['consumed_context']={name:fv[i] for name,i in [('own_outcome_mean3',0),('own_outcome_support3',1),('own_outcome_mean8',2),('own_outcome_support8',3),('last_eligible_source_age_days',5),('reported_attempts_mean3',20),('reported_carries_mean3',23),('reported_targets_mean3',26),('team_attempts_mean3',29),('team_carries_mean3',30)]}
   out.append(row)
  (data/name).write_text(json.dumps(out,separators=(',',':')))
  index.append({k:r[k] for k in ['target','history','family','week','version']}|dict(file=name,rows=len(out),sha256=hashlib.sha256((data/name).read_bytes()).hexdigest()));total+=len(out)
 scores=pd.read_csv(report/'SCORES.csv') if (report/'SCORES.csv').exists() else pd.DataFrame()
 summary=scores.replace([float('inf'),-float('inf')],['Infinity','-Infinity']).astype(object).where(pd.notna(scores),None).to_dict('records') if len(scores) else []
 manifest=dict(schema='C-RESEARCH-SITE-v2',categories=[dict(id=k,label=v[0],contract='nick-chart-ppr-v1' if k=='fpts' else 'rush-or-rec-at-least-one-v1' if k=='anytime_td' else 'official-player-fullgame-OT-v1',grid=None) for k,v in CATEGORIES.items()],files=index,source_as_of_UTC=None,source_snapshot_observed_UTC=max(x['retrieval_completion_from_local_mtime_UTC'] for x in json.load(open('reports/SOURCE_MANIFEST.json')) if x['source'].startswith('stats_player_week_')),source_clock_type='observed original local download completion; historical publication/update unknown',evaluation='2026 REG Weeks 1–7',live_offers_available=False,actionable_rankings=False,retention='GitHub facts and C-authored non-NGS evidence; offers/NGS held',summary=summary,site_forecast_views=total)
 lead=report/'LEADERS.csv'
 if lead.exists():
  df=pd.read_csv(lead);manifest['leaders']=df.astype(object).where(pd.notna(df),None).to_dict('records')
 (data/'manifest.json').write_text(json.dumps(manifest,separators=(',',':'),allow_nan=False))
 cal=report/'CALIBRATION_DIAGNOSTICS.csv'
 if cal.exists():
  frame=pd.read_csv(cal);(data/'calibration.json').write_text(json.dumps(frame.astype(object).where(pd.notna(frame),None).to_dict('records'),separators=(',',':'),allow_nan=False))
 (data/'six-leg.json').write_text(json.dumps([dict(week=w,state='NO_QUALIFIED_SIX_LEG_ENTRY',eligible_venue_candidates=0,entries=0,six_of_six=None,any_payout=None,net_profit=None,expected_return=None,two_entry_success_probability=None,overlap=None,reason='No redistribution-cleared offers, exact entry quote, venue combination/settlement rules or authenticated pregame candidate universe') for w in range(1,8)],indent=2))
 manifest['six_leg_sha256']=hashlib.sha256((data/'six-leg.json').read_bytes()).hexdigest()
 if (data/'calibration.json').exists():manifest['calibration_sha256']=hashlib.sha256((data/'calibration.json').read_bytes()).hexdigest()
 (data/'manifest.json').write_text(json.dumps(manifest,separators=(',',':'),allow_nan=False))
 (docs/'build.json').write_text(json.dumps(dict(built_at_UTC=datetime.now(timezone.utc).isoformat(),served_commit='LOCAL_PREPARED_NOT_DEPLOYED',asset_release_id=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),data_as_of_UTC=manifest['source_as_of_UTC'],source_snapshot_observed_UTC=manifest['source_snapshot_observed_UTC'],model_version='C-ALL12-LAW-THRESHOLD-v2.1; exact per-row version shown',status='HISTORICAL_RECONSTRUCTION_NOT_LIVE'),indent=2))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--docs',type=Path,default=Path('docs'));p.add_argument('--report',type=Path,default=Path('reports/all12-v2.1'));a=p.parse_args();build(a.run,a.docs,a.report)
