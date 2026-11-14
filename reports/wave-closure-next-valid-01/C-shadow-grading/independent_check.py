"""Independent CSV-to-grade identity/state/error audit; no author grader import."""
import csv,gzip,hashlib,io,json,lzma,math
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=Path(__file__).resolve().parent
O=ROOT/'prospective/outcomes/C-NATIVE-GRADE-20261114-WASNYG-01'
def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def number(v):
 if v is None or v=='':return None
 n=float(v);assert math.isfinite(n) and n==int(n);return int(n)
def main():
 receipt=read(R/'GRADING_RECEIPT.json');raw=list(csv.DictReader(io.StringIO(gzip.decompress((O/'evidence/player_facts.csv.gz').read_bytes()).decode())))
 assert len(raw)==70 and len({(r['game_id'],r['player_id']) for r in raw})==70
 facts={(r['game_id'],r['player_id']):r for r in raw};outcomes=read(O/'OUTCOMES.json')['outcomes'];outmap={(r['game_id'],r['player_id'],r['category']):r for r in outcomes};assert len(outmap)==25
 positive_fields='attempts carries targets receptions sacks_suffered passing_tds rushing_tds receiving_tds passing_2pt_conversions rushing_2pt_conversions receiving_2pt_conversions kickoff_returns punt_returns special_teams_tds'.split()
 signed_fields='passing_yards rushing_yards receiving_yards'.split();states=Counter();explicit0=[]
 for o in outcomes:
  f=facts.get((o['game_id'],o['player_id']));proof=[]
  if f:
   assert f['team'] in ['WAS','NYG'] and f['opponent_team'] in ['WAS','NYG'] and f['team']!=f['opponent_team'] and f['season']=='2026' and f['week']=='10' and f['season_type']=='REG'
   proof=[c for c in positive_fields if (number(f.get(c)) or 0)>0]+[c for c in signed_fields if number(f.get(c)) not in [None,0]]
  expected=number(f['receptions']) if f and proof else None
  assert o['appearance']==('PLAYED' if proof else 'UNKNOWN') and o['actual']==expected and o['participation_proof_fields']==proof
  states[o['appearance']]+=1
  if expected==0:explicit0.append(o['player_id']);assert f['receptions'] not in ['',None]
 assert states=={'PLAYED':18,'UNKNOWN':7} and len(explicit0)==5
 metrics=[];checked=0;all_forecasts={};all_grades={}
 for gfile in receipt['grade_files']:
  grade=read(ROOT/gfile['path']);assert sha(ROOT/gfile['path'])==gfile['SHA256']
  run=ROOT/'prospective/runs'/grade['run_id'];forecasts=json.loads(lzma.decompress((run/'FORECASTS.json.xz').read_bytes()));fm={f['forecast_id']:f for f in forecasts};assert len(fm)==len(forecasts) and grade['forecast_SHA256']==sha(run/'FORECASTS.json.xz')
  assert len(grade['grades'])==len(fm)
  for g in grade['grades']:
   f=fm[g['forecast_id']];o=outmap[(f['game_id'],f['player_id'],f['category'])];assert o['game_id']==f['game_id'] and o['kickoff_UTC']==f['kickoff_UTC'] and o['espn_event_id']==f['espn_event_id']
   assert g['actual']==o['actual'] and g['state']==('GRADED_PLAYED' if o['actual'] is not None else 'UNKNOWN')
   if g['actual'] is not None:
    assert abs(g['mean_squared_error']-(f['mean']-g['actual'])**2)<1e-10
    assert abs(g['median_error']-(f['median']-g['actual']))<1e-10 and abs(g['absolute_error']-abs(f['median']-g['actual']))<1e-10
   checked+=1;all_forecasts[g['forecast_id']]=f;all_grades[g['forecast_id']]=g
  for model in sorted({f['model_id'] for f in forecasts}):
   for role,positions in [('FULL_FROZEN_UNIVERSE',['RB','WR','TE']),('WR_TE',['WR','TE']),('RB_SHADOW',['RB'])]:
    fs=[f for f in forecasts if f['model_id']==model and f['position'] in positions];gs=[g for g in grade['grades'] if g['forecast_id'] in {f['forecast_id'] for f in fs}];scored=[g for g in gs if g['actual'] is not None];errors=[fm[g['forecast_id']]['mean']-g['actual'] for g in scored]
    metrics.append(dict(run_id=grade['run_id'],model_id=model,role=role,eligible=len(fs),scored=len(scored),unknown=len(gs)-len(scored),mean_MAE=sum(abs(x) for x in errors)/len(errors) if errors else None,mean_MSE=sum(x*x for x in errors)/len(errors) if errors else None,mean_bias=sum(errors)/len(errors) if errors else None,median_MAE=sum(abs(fm[g['forecast_id']]['median']-g['actual']) for g in scored)/len(scored) if scored else None,actual_offers=0,OU_results=None))
 # Scope-specific supplemental packet: identical current P1 means, separately typed policy, never extra NFL cases.
 c04=[f for f in json.loads(lzma.decompress((ROOT/'prospective/runs/C-C04-20261110-W10-FIRST-01/FORECASTS.json.xz').read_bytes())) if f['model_id']=='C_V11_P1_E2_POOLED_7D']
 c06=json.loads(lzma.decompress((ROOT/'prospective/runs/C-C06-20261112-W10-CURRENT-P1-01/FORECASTS.json.xz').read_bytes()))
 assert len(c04)==len(c06)==25
 assert {(f['player_id'],f['mean'],f['median']) for f in c04}=={(f['player_id'],f['mean'],f['median']) for f in c06}
 fixtures=[]
 for pid,label in [('00-0039337','ordinary_positive'),('00-0035250','explicit_reception_zero_with_rush_participation'),('00-0031484','present_all_zero_row_without_participation_proof'),('00-0033376','absent_stat_row_not_DNP_or_IR')]:
  o=next(o for o in outcomes if o['player_id']==pid);f=facts.get((o['game_id'],pid));fixtures.append(dict(player_id=pid,case=label,source_row_present=f is not None,source_receptions=f.get('receptions') if f else None,appearance=o['appearance'],actual=o['actual'],proof=o['participation_proof_fields'],reason=o['unavailable_reasons']))
 result=dict(status='PASS_CHECKED_SCOPE',checked_UTC=datetime.now(timezone.utc).isoformat(),checked_forecast_rows=checked,source_fact_rows=len(raw),unique_outcomes=len(outcomes),states=dict(states),explicit_known_zero_receptions=len(explicit0),fixture_cases=fixtures,role_metrics=metrics,original_hashes_verified=all(sha(ROOT/p)==h for p,h in receipt['original_packet_hashes'].items()),C06_P1_means_and_medians_identical_to_C04=True,source_reads=0,new_fits=0,verification_scope='Independent csv numeric parsing, event/player/team/schema identities, explicit label presence and participation states, frozen forecast hash linkage, direct mean and median error arithmetic across100grades. Canonical grader separately executed. No independent provider-statistic adjudication beyond qualified retained ordinary source; no raw-provider second feed, distribution freshfit, original-site consumer, offered-line or settlement claim.',uncertainty='One game/one week and18playedplayers; game/week-aware comparative confidence interval not estimable. Descriptive numerical differences are not evidence of general superiority.',IR_state='No qualified IR/DNP evidence obtained; seven unresolved candidates remain UNKNOWN',actual_offers=0,original_selected_sides=0)
 (R/'INDEPENDENT_CHECK.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(status=result['status'],checked=checked,roles=metrics)))
if __name__=='__main__':main()
