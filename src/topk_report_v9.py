"""Readable and compact projections of the completed zero-refit audit."""
import csv,gzip,io,json,shutil
from collections import defaultdict
from pathlib import Path
import actual_accuracy_v6 as a
from topk_reference_v9 import ROOT,OUT,ART,METHODS,common_pool
from reliability_v8 import read,write
from diagnose_v8 import classify,cases,metrics

def flat_csv(path,rows):
    flat=[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in rows];f=io.StringIO();w=csv.DictWriter(f,list(dict.fromkeys(k for r in flat for k in r)),lineterminator='\n');w.writeheader();w.writerows(flat);path.write_bytes(gzip.compress(f.getvalue().encode(),mtime=0))
def thin(r):
    fields=['diagnostic_id','book','week','method','scope','category','side_variant','K','common_eligible','side_eligible','selected_count','fewer_than_K','wins','losses','decided','pushes','hit_rate','mean_confidence_decided','expected_wins_decided','all_selected_expected_wins','all_selected_mean_confidence','states','games','weeks','role_composition','category_composition','uncertainty','selected_quotes_after_first_selected_kickoff','selected_forecast_cutoffs_after_first_selected_kickoff','unilateral_price_diagnostic']
    q={k:r[k] for k in fields if k in r}
    if 'uncertainty' in q:q['uncertainty']={k:v for k,v in q['uncertainty'].items() if k!='qualification'}
    if 'unilateral_price_diagnostic' in q:q['unilateral_price_diagnostic']={k:v for k,v in q['unilateral_price_diagnostic'].items() if k!='qualification'}
    return q

def thin_overlap(r):return {k:v for k,v in r.items() if k not in ['whole_policy_records','comparison','diagnostic_ids']}
def build():
    weekly=read(OUT/'WEEKLY_RESULTS.json.gz');cumulative=read(OUT/'CUMULATIVE.json.gz');overlap=read(OUT/'OVERLAPS.json.gz');members=read(ART/'MEMBERSHIP.json.gz');pooldata=read(ART/'COMMON_POOL.json.gz');run=read(OUT/'RUN.json');raw,_=a.load_records();pool,_=common_pool(raw);cmap=cases();bank=read(ROOT/'artifacts/reliability-v8/REFERENCE_BANK.json.gz');controls=[]
    for b in ['pinnacle','draftkings','fanduel']:
     for c in ['pass_yd','rush_yd','rec','rec_yd']:
      for m in METHODS:
        rows=[classify(g[m],cmap[oid],bank) for oid,g in pool.items() if g[m]['venue']==b and g[m]['category']==c];controls.append(dict(book=b,category=c,method=m,**metrics(rows)))
    write(OUT/'ALL_COMMON_OFFER_METHODS.json',controls)
    flat_csv(OUT/'WEEKLY_RESULTS.csv.gz',weekly);flat_csv(OUT/'CUMULATIVE.csv.gz',cumulative);flat_csv(OUT/'MEMBERSHIP.csv.gz',members)
    text='# Fixed Top-K benchmark audit — v9\n\nThis is an **EXPLORATORY LAST-RECORDED-LINE RANKING DIAGNOSTIC**, not a simultaneous pregame board, future probability, settled ticket or payout record. Uses the same exposed2026W2–3/32games and unchangedP2/P3/saved earlier-role prevalence. No refits, new probabilities, category/side switching or newbook search. All810registered weeklylists/405cumulative views are retained.\n\nThe common probability-ready candidatepool has2624quote-cases;145technicalmissing cases remain excluded with reasons. The one whole0.0halfpoint-reference case already lacks retainedP2/P3forecasts, so it causes no additional loss from the existing P2/P3ready board. Unknown later outcomes stay in the candidate pool/members. Each procedure filters its own selected side for Over-only/Under-only, then ranks by its own probability with the registered ties/one-player rule. Whole-policy comparisons retain each procedure\'s own members, not the intersection.\n\n|Book|Method|K|Selected / decided|W-L / hit rate|Mean confidence, decided|Expected decided / all|Games/weeks|\n|---|---|---|---|---|---|---|---|\n'
    for r in cumulative:
      if r['scope']=='GLOBAL' and r['side_variant']=='MIXED':text+=f"|{r['book']}|{r['method']}|{r['K']}|{r['selected_count']} / {r['decided']}|{r['wins']}-{r['losses']} / {100*r['hit_rate']:.2f}%|{100*r['mean_confidence_decided']:.2f}%|{r['expected_wins_decided']:.3f} / {r['all_selected_expected_wins']:.3f}|{r['games']}/{r['weeks']}|\n"
    text+='\nThese are two weekly lists per cell. Original P3Pinnacle globalK6 remains10–2 across twelve selected legs. Its week2 andweek3lists each have5wins/1loss; neither is an original6/6entry. No unknown/void member is replaced. DraftKingsP3K6selected12,decided11; its all-selected expectation differs from the decided-mask expectation. No price or payout is assumed. [EveryK/book/week/side/scope](WEEKLY_RESULTS.csv.gz), [full cumulative states/uncertainty](CUMULATIVE.csv.gz) and [actual individual membership](MEMBERSHIP.csv.gz).\n\n## Simpler control and overlap\n\nOn the identical177Pinnacle rushing cases, P3 and the earlier-role prevalence reference bothwin104/177. That is no incremental all-offer hit count. Their probabilities/Brier/logloss remain separate; see ALL_COMMON_OFFER_METHODS.json. The TopKrecords are different procedures and do not inherit a champion claim from one aggregate.\n\n|Book|K6 pair|Exact-offer overlap|Player-game overlap|Own selections|\n|---|---|---|---|---|\n'
    for b in ['pinnacle','draftkings','fanduel']:
     for methods in [['P2_LAW','P3_DIRECT'],['P2_LAW','EARLIER_PREVALENCE_V8'],['P3_DIRECT','EARLIER_PREVALENCE_V8']]:
        q=[r for r in overlap if r['book']==b and r['K']==6 and r['scope']=='GLOBAL' and r['side_variant']=='MIXED' and r['methods']==methods];text+=f"|{b}|{' / '.join(methods)}|{sum(r['exact_offer_overlap'] for r in q)}|{sum(r['player_game_overlap'] for r in q)}|{sum(r['selected'][0] for r in q)} / {sum(r['selected'][1] for r in q)}|\n"
    text+='\n[All810pair-overlap views](OVERLAPS.json.gz) preserve price/role/category differences and both complete policyrecords. Overlap is dependence/context, not a new evaluation mask. Role/category composition and selected versus decided masks are retained beside every weekly result. No posthoc QB-only, RB-fade or per-category switch is evaluated. Original v7/v8results, losses, candidatepanels and workload failures remain unchanged.\n\n## Difficulty, prices and evidence limits\n\nAll source main/alternate/promotional tiers remain UNVERIFIED; no like-difficulty universal superiority follows. A single selected-side recorded closing American price can supply raw implied-price context only: it includes vig, can be stale, lacks commonOPENstate and is not a fitted/qualified market-only benchmark. No nonsynchronous opposite price is spliced into a fake no-vig pair. Market-only control remains N/A; line-only direction grading does not require prices.\n\nTwo exposed weeks and repeatedbooks do not add independent seasons. Descriptive intervals use retained v8game/Wilson rules and do not establish superiority or future confidence. New control comparisons are exposed diagnostics, not untouched confirmation. The next admissible test is independently persisted future primary/shadow procedures on a genuinely qualified common real-offer board.\n'
    (OUT/'README.md').write_text(text)
    membership_path=ROOT/'docs/data/topk-membership-v9.json.gz';shutil.copyfile(ART/'MEMBERSHIP.json.gz',membership_path)
    public=dict(schema='C-TOPK-REFERENCE-COMPARISON-v9',run=run,weekly=[thin(r) for r in weekly],cumulative=[thin(r) for r in cumulative],overlaps=[thin_overlap(r) for r in overlap],membership=dict(path='data/topk-membership-v9.json.gz',SHA256=a.sha(membership_path),rows=len(members),encoding='gzip-json'),methods=METHODS,scope='EXPLORATORY_LAST_RECORDED_LINE_RANKING_DIAGNOSTIC',no_common_pregame_board=True,no_entry_or_payout=True,market_reference='N/A: same-line/time/OPEN price pair not established',uncertainty_qualification='Only two exposed weeks; small game clusters; descriptive intervals, not independent proof',single_price_qualification='Single-side recorded close; vig not removed; OPEN/synchrony unverified; not a market-only control or value claim',tier='2026W2-W3;twoexposedweeks;same32footballgames',evidence_URL='https://github.com/NickNicky19/NFL-forecasting-NGS-C/tree/main/reports/topk-reference-v9')
    p=ROOT/'docs/data/topk-reference-v9.json';p.write_text(json.dumps(public,separators=(',',':'),allow_nan=False)+'\n');build=read(ROOT/'docs/build.json');build['topk_reference_v9_SHA256']=a.sha(p);(ROOT/'docs/build.json').write_text(json.dumps(build,separators=(',',':'))+'\n');print('TOPK_REFERENCE_PROJECTION',len(weekly),len(cumulative),len(members),p.stat().st_size)

def validate():
    site=read(ROOT/'docs/data/topk-reference-v9.json');assert site['weekly']==[thin(r) for r in read(OUT/'WEEKLY_RESULTS.json.gz')] and site['cumulative']==[thin(r) for r in read(OUT/'CUMULATIVE.json.gz')];assert read(ROOT/'docs'/site['membership']['path'])==read(ART/'MEMBERSHIP.json.gz') and site['overlaps']==[thin_overlap(r) for r in read(OUT/'OVERLAPS.json.gz')];assert a.sha(ROOT/'docs'/site['membership']['path'])==site['membership']['SHA256'];assert a.sha(ROOT/'docs/data/topk-reference-v9.json')==read(ROOT/'docs/build.json')['topk_reference_v9_SHA256'];assert site['run']['new_fits']==0 and len(site['weekly'])==810 and site['no_common_pregame_board'];print('TOPK_REFERENCE_PARITY',810,405)

if __name__=='__main__':
    import sys
    validate() if sys.argv[1:]==['validate'] else build()
