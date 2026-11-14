"""Source-qualified reporting of existing, pregraded median crossings only."""
import csv,gzip,hashlib,json,lzma,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
def load(p):
 b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else lzma.decompress(b) if str(p).endswith('.xz') else b)
def bind(p):p=Path(p);return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())
def count(s,k):
 v=s[k]
 if v is None:
  assert s['selected']==s['decided']==0,'UNKNOWN_COUNT_ON_NONEMPTY_SIDE'
  return 0 # Additive identity for an empty side, never a player statistic.
 return v
def main():
 start=time.process_time();decision=ROOT/'reports/w1w9-comparison-closure-01/source-contract/attempt/COMPATIBILITY_DECISION.json';assert 'ALLOW' in json.dumps(load(decision))
 ap=ROOT/'reports/category-decision-release-01/follow-through-v1/peer-intake/A_WEEKLY_COVERAGE.json.xz';bp=HERE/'ALL_METHOD_SIDE_TABLE.json.gz'
 a=load(ap);b=load(bp);weekly=[]
 for week in range(1,9):
  if week<=4:
   r=[r for r in a['rows'] if r['procedure_ref']=='P005' and r['week']==week];assert len(r)==1;r=r[0];s={k.lower():v for k,v in r.items() if k in ['OVER','UNDER','COMBINED']};c=r['counts'];source='A_ANNUAL_W1_W4'
  else:
   rr=[r for r in b if r['category']=='pass_att' and r['procedure_id']=='B-player-context-matchup-01-v1:COMMON_EXPOSURE' and r['output_rule']=='P1_LOWER_MEDIAN' and r['week_view']==week];assert len(rr)==1;r=rr[0];s={k.lower():v for k,v in r['sides'].items()};c=dict(eligible=r['eligible'],selected=s['combined']['selected'],decided=s['combined']['decided'],unknown=0,unavailable=r['technical_unavailable'],fallback=r['fallback'],games=r['games']);source='B_NATIVE_W5_W8'
  assert c['eligible']==s['combined']['selected']==s['combined']['decided'];assert count(s['over'],'wins')+count(s['under'],'wins')==s['combined']['wins']
  # All source crossings are decided with no ties/pushes. Constant-side
  # outcomes follow exactly from the same original own-side crossing table.
  ow=count(s['over'],'wins')+count(s['under'],'losses');uw=count(s['under'],'wins')+count(s['over'],'losses');n=c['eligible'];assert ow+uw==n
  weekly.append(dict(week=week,source=source,eligible=n,available=n,selected=n,decided=n,unknown=0,unavailable=0,fallback=0,games=c['games'],own_sides=s,always_over_wins=ow,always_under_wins=uw,raw_source=r))
 own={}
 for side in ['over','under','combined']:
  d={k:sum(count(w['own_sides'][side],k) for w in weekly) for k in ['wins','losses','decided','selected']};d['rate']=d['wins']/d['decided'] if d['decided'] else None;own[side]=d
 cov={k:sum(w[k] for w in weekly) for k in ['eligible','available','selected','decided','unknown','unavailable','fallback','games']};assert cov['eligible']==195 and cov['games']==104
 weights=np.random.default_rng(1703).multinomial(8,[1/8]*8,size=500);n=np.array([w['eligible'] for w in weekly]);mw=np.array([w['own_sides']['combined']['wins'] for w in weekly]);controls={}
 for side in ['over','under']:
  v=np.array([w['always_'+side+'_wins'] for w in weekly]);samples=(weights@(mw-v))/(weights@n);wins=int(sum(v));controls['ALWAYS_'+side.upper()]=dict(wins=wins,losses=195-wins,decided=195,rate=wins/195,matched_win_difference=int(sum(mw-v)),paired_week_interval95=np.quantile(samples,[.025,.975]).tolist())
 schedule=ROOT/'sources/category-decision-release-01/schedule.csv';scheduled=sum(1 for r in csv.DictReader(schedule.open()) if r['season']=='2026' and r['game_type']=='REG' and int(r['week'])<=8)
 out=dict(id='C-ATT-COMMON-EXPOSURE-MEDIAN-W1W8-v1',assembled_UTC=datetime.now(timezone.utc).isoformat(),category='pass_att',procedure_id='B-player-context-matchup-01-v1:COMMON_EXPOSURE::lower_median',output='P1_LOWER_MEDIAN',actual_weeks=list(range(1,9)),missing_weeks=[9],own_sides=own,coverage=cov,scheduled_games_retained_snapshot=scheduled,weekly=weekly,matched_controls=controls,evidence_tier='RETAINED_ACTUAL_LINES_CURRENT_VINTAGE_SEVEN_DAY_DIAGNOSTIC;UNKNOWN_QUOTE_CLOCK_MAIN_ALT;NOT_ORIGINAL_ISSUANCE',contract=bind(decision),sources=[bind(ap),bind(bp)],numerical_typing='Do not pool Amedian errors with B numerical_mean_MAE: the latter is companionmean, notverifiedmedian error.',probability_typing='Pointmedian crossing has no inferredconfidence; nativeP2 law is separate evenwhen ownsidecounts match.',stronger_native_reference={'source':'B_NATIVE_W5_W8_ONLY','saved_adjusted_wins':69,'decided':112,'median_wins':55,'scope':'Same later112mask; earlyreference absent, no invented8weekreferenceunion.'},recommendation='KEEP_INCUMBENT;median ties strongest complete constant-side control and loses stronger native savedadjusted reference. No9weekclaim.',W9_action='Breuse anyexactretainedCOMMON_EXPOSURE median origin/output first; otherwiseoneproperregisteredhistoricalorigin fit/inference andscore onknown30ATTsourceoffers, notborrowedCMP/law.',new_fits=0,new_outcome_grades=0,new_NFL_games=0,new_original_selected_sides=0,uncertainty='Whole-week sufficientcount diagnostic,500resamplesseed1703,eight exposedclusters; no rawpairedgamebootstrap/multiplicitycontrol.',CPU_seconds=time.process_time()-start)
 p=HERE/'EIGHT_WEEK_ATTEMPTS.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['own_sides','coverage','matched_controls','missing_weeks']}))
if __name__=='__main__':main()
