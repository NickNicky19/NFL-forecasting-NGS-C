"""Independent denominator/rank checks of supplied tables, not source proof."""
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
import csv,json,hashlib,time,resource,datetime as dt
R=Path(__file__).resolve().parent
started=time.process_time();checks=[];issues=[]
def check(kind,team,actual,expected):
 ok=actual==expected;checks.append({'check':kind,'team':team,'actual':str(actual),'expected':str(expected),'pass':ok})
 if not ok:issues.append(checks[-1])
def read(name):return list(csv.DictReader((R/name).read_text().splitlines()))
def rounded(n,d,places):return (Decimal(n)/Decimal(d)).quantize(Decimal('1').scaleb(-places),rounding=ROUND_HALF_UP)
def ranks(rows,key,rank='Rank'):
 values=[Decimal(x[key]) for x in rows]
 check('descending_supplied_values',None,values,sorted(values,reverse=True))
 for row,value in zip(rows,values):
  expected=1+sum(v>value for v in values);tied=sum(v==value for v in values)>1
  check('competition_rank:'+key,row['Defense'],row[rank],('T' if tied else '')+str(expected))
tables={n:read(n) for n in ['A1_TE_receiving_yards.csv','A2_alignment_efficiency.csv','A3_passing_attempts.csv','A4_completions.csv','A5_RB_rushing.csv']}
base={x['Defense']:x for x in tables['A3_passing_attempts.csv']}
for n,rows in tables.items():
 check('rows:'+n,None,len(rows),32);check('unique_teams:'+n,None,len({x['Defense'] for x in rows}),32);check('same_team_universe:'+n,None,sorted(x['Defense'] for x in rows),sorted(base))
for x in tables['A1_TE_receiving_yards.csv']:
 check('TE_yards_per_game',x['Defense'],Decimal(x['TE yards per game']),rounded(x['TE receiving yards'],x['Games'],2));check('TE_vs_PASS_games',x['Defense'],x['Games'],base[x['Defense']]['Games'])
for x in tables['A3_passing_attempts.csv']:check('PASS_attempts_per_game',x['Defense'],Decimal(x['Attempts per game']),rounded(x['Pass attempts faced'],x['Games'],2))
for x in tables['A4_completions.csv']:
 b=base[x['Defense']];check('PASS_completions_per_game',x['Defense'],Decimal(x['Completions per game']),rounded(x['Completions allowed'],b['Games'],2));check('PASS_completion_percent',x['Defense'],Decimal(x['Completion percent'].rstrip('%')),rounded(Decimal(x['Completions allowed'])*100,b['Pass attempts faced'],1));check('completions_not_above_attempts',x['Defense'],int(x['Completions allowed'])<=int(b['Pass attempts faced']),True)
for x in tables['A5_RB_rushing.csv']:
 check('RB_carries_per_game',x['Defense'],Decimal(x['RB carries per game']),rounded(x['RB carries faced'],x['Games'],2));check('RB_vs_PASS_games',x['Defense'],x['Games'],base[x['Defense']]['Games'])
for n,k in [('A1_TE_receiving_yards.csv','TE receiving yards'),('A3_passing_attempts.csv','Pass attempts faced'),('A4_completions.csv','Completions allowed'),('A5_RB_rushing.csv','RB carries faced')]:ranks(tables[n],k)
ranks(tables['A2_alignment_efficiency.csv'],'Slot yards per target','Slot rank')
# Rounded YPT and YPC values cannot reconstruct exact target or yard numerators.
report={'id':'DEFENSIVE-SUPPLIED-TABLE-INTERNAL-CHECK-v1','checked_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'PASS_INTERNAL_ARITHMETIC_ONLY' if not issues else 'SUPPLIED_TABLE_DISCREPANCIES','checks':len(checks),'failed_checks':issues,'teams_each':32,'tables':5,'rate_checks':160,'ranking_rows_checked':160,'game_denominator_crosschecks':64,'Decimal_rounding':'ROUND_HALF_UP;two decimals per-game and one decimal completion percent as displayed. Agreement is internal arithmetic, not authentication of provider rounding contract.','count_totals_supplied':{'TE_yards':sum(int(x['TE receiving yards']) for x in tables['A1_TE_receiving_yards.csv']),'passing_attempts':sum(int(x['Pass attempts faced']) for x in tables['A3_passing_attempts.csv']),'completions':sum(int(x['Completions allowed']) for x in tables['A4_completions.csv']),'RB_carries':sum(int(x['RB carries faced']) for x in tables['A5_RB_rushing.csv'])},'examples':[{'team':'Bengals','TE_yards':645,'games':8,'exact_yards_per_game':'80.625','displayed_half_up':'80.63'},{'team':'Dolphins','completions':168,'attempts':221,'completion_percent_formula':'100*168/221','displayed_percent':'76.0%'},{'team':'Raiders','slot_YPT':'11.5','targets':None,'outside_YPT':'9.1','reason':'No target or yard totals supplied; no denominator was inferred.'}],'not_checked':['External correctness, season, cutoff, rights and publication clocks.','Whether passing attempts exclude sacks or include non-QB attempts at the unnamed source.','PFR fullback/hybrid RB classification.','Alignment labels/player alignment frequencies/untargeted routes.','YPC/YPT exact rates without unrounded numerators and denominators.'],'software_observations_not_NFL_tests':True,'new_fits':0,'new_forecasts':0,'new_actual_offer_weeks':0,'network_requests':0,'CPU_seconds':time.process_time()-started,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'bindings':[{'path':n,'SHA256':hashlib.sha256((R/n).read_bytes()).hexdigest()} for n in tables]}
(R/'ARITHMETIC_CHECK.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k in ['status','checks','failed_checks','rate_checks','count_totals_supplied','CPU_seconds']}));assert not issues
