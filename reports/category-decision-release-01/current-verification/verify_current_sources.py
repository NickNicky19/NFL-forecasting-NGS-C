"""Read-only, no-optimizer/no-inference C06 source and recipe check."""
import csv,gzip,lzma,json,hashlib,math,time,resource
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
ROOT=Path('/workspace/ngs-c');OUT=ROOT/'reports/category-decision-release-01/current-verification'
def read(p):
 b=Path(p).read_bytes();return json.loads(lzma.decompress(b) if str(p).endswith('.xz') else gzip.decompress(b) if str(p).endswith('.gz') else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csvrows(p):
 p=Path(p)
 with (gzip.open(p,'rt',newline='') if p.suffix=='.gz' else lzma.open(p,'rt',newline='') if p.suffix=='.xz' else p.open(newline='')) as f:return list(csv.DictReader(f))
def aware(x):
 d=datetime.fromisoformat(x.replace('Z','+00:00'));assert d.tzinfo;return d
start=time.process_time();source=ROOT/'sources/category-decision-release-01';old=ROOT/'sources/profile-closure-next-02';m=read(source/'MODEL_INPUT_MANIFEST.json');cut=aware(m['actual_input_cutoff_UTC']);oldrun=ROOT/'prospective/runs/C-C04-20261110-W10-FIRST-01';draft=read(oldrun/'draft/DRAFT.json');spec=next(x for x in draft['models'] if x['model_id']=='C_V11_P1_E2_POOLED_7D');modelpath=oldrun/'draft'/spec['path'];model=read(modelpath);oldcut=aware(model['fit_information_cutoff_UTC']);assert sha(modelpath)==spec['SHA256']
assert (source/'schedule.csv').read_bytes()==(old/'schedule.csv').read_bytes()
schedule=csvrows(source/'schedule.csv')
def eligible(t):
 result=set()
 for r in schedule:
  if not r['home_score'] or not r['away_score']:continue
  kickoff=datetime.fromisoformat(r['gameday']+'T'+r['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
  if kickoff+timedelta(days=7)<t:result.add(r['game_id'])
 return result
before,after=eligible(oldcut),eligible(cut);assert before==after
comparisons=[]
for n,keys in [('current_facts_2026.csv.gz',['game_id','player_id']),('pbp_facts_2026.csv.xz',['game_id','play_id'])]:
 a,b=csvrows(old/n),csvrows(source/n);assert a[0].keys()==b[0].keys()
 def key(r):return tuple(r[k] for k in keys)
 da={key(r):r for r in a};db={key(r):r for r in b};assert len(da)==len(a) and len(db)==len(b) and da.keys()==db.keys()
 diffs=[dict(identity=dict(zip(keys,k)),field=f,old=da[k][f],new=db[k][f]) for k in da for f in da[k] if da[k][f]!=db[k][f]]
 assert all(x['identity']['game_id']=='2026_09_LA_WAS' and x['identity']['game_id'] not in after for x in diffs)
 ea={k:v for k,v in da.items() if v['game_id'] in after};eb={k:v for k,v in db.items() if v['game_id'] in after};assert ea==eb
 comparisons.append(dict(path=n,total_rows=len(a),changed_cells=len(diffs),changes=diffs,eligible_rows=len(ea),eligible_equal=True))
assert [x['changed_cells'] for x in comparisons]==[2,8]
assert [x['eligible_rows'] for x in comparisons]==[8420,15136]
assert sha(ROOT/m['old_finality_contract']['path'])==m['old_finality_contract']['SHA256']==draft['source_bindings']['finality_proof']['SHA256']
completed=set(read(ROOT/m['old_finality_contract']['path'])['completed_game_ids']);assert after<=completed
roster=read(source/'roster_current_season.json');assert len(roster)==959
seen={}
for r in roster:
 if r.get('gsis_id'):seen[r['gsis_id']]=seen.get(r['gsis_id'],0)+1
players=[r for r in roster if r.get('team') in ['WAS','NYG'] and r.get('season')==2026 and r.get('status')=='ACT' and r.get('position') in ['WR','TE','RB']]
assert len(players)==25 and all(seen[r['gsis_id']]==1 for r in players)
assert sum(r['position'] in ['WR','TE'] for r in players)==18
prepared=[r for r in read(oldrun/'draft/DRAFT_FORECASTS.json.xz') if r['model_id']==spec['model_id'] and r['game_id']=='2026_10_WAS_NYG'];byid={r['player_id']:r for r in prepared}
assert len(byid)==25 and set(byid)=={r['gsis_id'] for r in players}
for r in players:assert byid[r['gsis_id']]['team']==r['team'] and byid[r['gsis_id']]['position']==r['position']
assert not any(k in r for r in players for k in ['actual','played','realized_starter'])
historical=read(ROOT/'artifacts/player-context-matchup-01/v1.1/2026-W01-P1.json.gz');hm=historical['model'];cm=model['model']
assert hm['type']==cm['type']=='L2_POOLED_POISSON' and hm['partial']==cm['partial']==False and hm['alpha']==cm['alpha']==.1
assert len(hm['impute'])==len(cm['impute'])==60 and len(hm['coef'])==len(cm['coef'])==120 and hm['categories']==cm['categories']==[]
originals={
 'prospective/runs/C-C04-20261110-W10-FIRST-01/FORECASTS.json.xz':'4334c6e93d41487011e3bedb9a0a0173e38ccfcf5c568b30efbd0b73995be362',
 'prospective/runs/C-C05-NEDET-FIRST-01/FORECASTS.json.xz':'e3dcb454f25b3a3d6b802a72f47ec91d583fe3eeeaa7fc964a0d4d255b16d32e'}
assert all(sha(ROOT/p)==s for p,s in originals.items())
report=dict(id='C06-INDEPENDENT-CANONICAL-SOURCE-AND-RECIPE-v1',checked_UTC=datetime.now(timezone.utc).isoformat(),status='PASS_CURRENT_INPUT_CACHE_REUSE_SCOPE;WHOLE_PRODUCT_RELEASE_NOT_INFERRED',calculation_path='stdlib csv/gzip/lzma/datetime and independently reconstructed America/New_York kickoff + strict seven-day admission; no author source comparator or inference called',current_source_cutoff_UTC=m['actual_input_cutoff_UTC'],original_fit_cutoff_UTC=model['fit_information_cutoff_UTC'],strict_eligible_game_sets_equal=True,eligible_games=len(after),comparisons=comparisons,current_roster_basic=959,available_current_queries=25,WR_TE_queries=18,RB_shadow_queries=7,all_current_ID_team_role_keys_match_prepared=True,source_future_target_outcomes_absent=True,old_finality_binding_SHA256=m['old_finality_contract']['SHA256'],eligible_games_subset_of_retained_finality=True,model_SHA256=sha(modelpath),historical_P1_reuse_acceptance=dict(path='reports/player-context-matchup-01/acceptance-v1/FIT_REPRODUCTION_FINAL.json',SHA256=sha(ROOT/'reports/player-context-matchup-01/acceptance-v1/FIT_REPRODUCTION_FINAL.json'),scope='Reuse completed P1 fresh-fit and single/batch/shuffle/serialization verification; no fit repeated'),recipe_equivalence=dict(features=60,transformed_coefficients=120,family='L2_POOLED_POISSON',alpha=.1,partial=False,history='2022+ labels; seven-day reconstructed availability; E0_OP32 plus22 owncontext+6opponent fields from2025/2026; earlier-only imputation/scale; mean exp link once; no added corrector'),original_forecast_hashes=originals,limitations=['Historical exact-offer mean239/412 scope is owner-local five-week WR/TE point-direction at quote-time-unverified reconstructed tier; this check does not independently inspect A private offers/masks/clocks.','Current pregame roster universe differs from historical stat-row-conditioned query universe. Whole-system eligibility/coverage and current issue horizon cannot inherit five-week admission solely from a shared model family.','The current retained fit has explicit completed/held-source validation. Those unchanged cache conditions substantiate reuse; they do not authenticate old historical publication times.','Actual new inference, final native admission, issuance, GitHub persistence and served consumer remain pending.'],new_fits=0,new_NFL_inference=0,new_GETs=0,CPU_seconds=time.process_time()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
OUT.mkdir(parents=True,exist_ok=True);(OUT/'INDEPENDENT_SOURCE_RECIPE_REVIEW.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['comparisons','limitations','original_forecast_hashes']}))
