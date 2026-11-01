"""Build the v8 checkpoint from canonical rows. No fitting or acquisition."""
import csv,gzip,io,json
from collections import defaultdict
import numpy as np
import actual_accuracy_v6 as a
from reliability_v8 import ROOT,OUT,ART,read,write,key,references
from diagnose_v8 import latest,cases,classify,metrics

def csv_output(path,rows):
    f=io.StringIO();fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader();w.writerows(rows)
    b=f.getvalue().encode();path.write_bytes(gzip.compress(b,mtime=0) if path.suffix=='.gz' else b)

def paired(values,games):
    if not values:return dict(n=0,mean=None,interval=None,games=0)
    groups=defaultdict(list)
    for game,value in zip(games,values):groups[game].append(value)
    sums=np.array([[sum(v),len(v)] for v in groups.values()]);rng=np.random.default_rng(881102)
    z=sums[rng.integers(len(sums),size=(2000,len(sums)))].sum(axis=1)
    return dict(n=len(values),mean=float(np.mean(values)),interval=np.quantile(z[:,0]/z[:,1],[.025,.975]).tolist(),games=len(groups),kind='PAIRED_GAME_BLOCK_DESCRIPTIVE_2000',qualification='Only two exposed 2026 weeks, or one selected 2025 week per origin; repeated comparisons, not confirmation')

def build():
    raw=latest();cmap=cases();bank=references();rr=[classify(r,cmap[r['offer_id']],bank) for r in raw]
    byid={r['record_id']:r for r in rr};members=read(ART/'RANK_MEMBERSHIP.json.gz');ranks=read(OUT/'RANK_RESULTS.json.gz');grouped=defaultdict(list)
    for r in ranks:grouped[tuple(r[k] for k in ['book','method','scope','category','side_variant','K'])].append(r)
    ranktotals=[]
    for k,lists in grouped.items():
        ids={r['diagnostic_id'] for r in lists};selected=[byid[r['record_id']] for r in members if r['diagnostic_id'] in ids]
        ranktotals.append(dict(zip(['book','method','scope','category','side_variant','K'],k))|dict(lists=len(lists),selected_count=len(selected),tier='EXPLORATORY_LAST_RECORDED_LINE_RANKING_DIAGNOSTIC',no_simultaneous_board=True,not_entry_or_payout=True,**metrics(selected)))
    write(OUT/'RANK_CUMULATIVE.json.gz',ranktotals)
    flat=[]
    for r in raw:
        fields=['record_id','offer_id','category','method_id','method_version','policy_id','venue','product','line_tier','game_id','player_id','player_name','position','season','week','line','point_type','point','p_under','p_push','p_over','selected_side','actual','appearance','status','decision_UTC','kickoff_UTC','graded_UTC','evidence_tier']
        flat.append({k:r.get(k) for k in fields}|{s+'_source_closing_UTC':r['source_snapshot_clocks'].get(s) for s in ['OVER','UNDER']})
    csv_output(OUT/'GRADED_ROWS.csv.gz',flat)
    csv_output(OUT/'RANK_SUMMARY.csv',[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in ranktotals])
    summary=[]
    for book in ['pinnacle','draftkings','fanduel']:
      for cat in a.CATEGORIES:
       for method in a.METHODS:
        q=[r for r in raw if r['venue']==book and r['category']==cat and r['method_id']==method];s=a.aggregate(q)
        row=dict(book=book,category=cat,method=method,eligible=len(q),games=s['games'],weeks=s['weeks'],unavailable=s['unavailable_forecasts'],abstentions=s['abstentions'],tier=a.TIERS[2],higher_own_side=s['higher_side'],Over_minus_Under_percentage_points=s['Over_minus_Under_percentage_points'])
        for side in ['OVER','UNDER','COMBINED']:
            for field in ['selected','wins','losses','decided','rate','pushes','voids','DNP','pending','unknown_participation','missing_actuals']:row[side+'_'+field]=s[side][field]
        row['reason']=None if q else 'Market absent' if cat not in ['pass_yd','rush_yd','rec','rec_yd'] else 'Method not executed on this category/offer'
        summary.append(row)
    csv_output(OUT/'CATEGORY_METHOD_SCORECARD.csv',summary)
    comparisons=[]
    for book in ['pinnacle','draftkings','fanduel']:
      indexed={(r['offer_id'],r['method_id']):r for r in rr if r['venue']==book and r['category']=='pass_yd'}
      for control in ['P2_LAW','P2_LINKED_V8','P3_DIRECT']:
        pairs=[(indexed[(oid,control)],r) for (oid,m),r in indexed.items() if m=='P2_WORKLOAD_V8' and (oid,control) in indexed and r['status'] in ['WIN','LOSS','PUSH'] and indexed[(oid,control)]['status'] in ['WIN','LOSS','PUSH']]
        gs=[r['game_id'] for _,r in pairs]
        def brier(r):
            ps=np.array([r['_ps'][s] for s in ['under','push','over']]);y=np.array([r['actual']<r['line'],r['actual']==r['line'],r['actual']>r['line']]);return float(.5*np.sum((ps-y)**2))
        comparisons.append(dict(book=book,control=control,candidate='P2_WORKLOAD_V8',Brier_candidate_minus_control=paired([brier(y)-brier(x) for x,y in pairs],gs),win_indicator_candidate_minus_control=paired([int(y['status']=='WIN')-int(x['status']=='WIN') for x,y in pairs],gs),same_row=True))
    queries=read(ART/'WORKLOAD_PREDICTIONS.json.gz');numeric=[]
    for origin in sorted({r['origin_id'] for r in queries}):
      q=[r for r in queries if r['origin_id']==origin and r['actual'] is not None];gs=[r['game_id'] for r in q]
      for control in ['RETAINED_P2','P2_LINKED_V8']:
        numeric.append(dict(origin_id=origin,control=control,candidate='P2_WORKLOAD_V8',median_absolute_error_change=paired([abs(r['arms']['P2_WORKLOAD_V8']['median']-r['actual'])-abs(r['arms'][control]['median']-r['actual']) for r in q],gs),CRPS_change=paired([r['arms']['P2_WORKLOAD_V8']['CRPS']-r['arms'][control]['CRPS'] for r in q],gs),same_row=True))
    write(OUT/'WORKLOAD_PAIRED_UNCERTAINTY.json',dict(actual_line=comparisons,numerical=numeric))
    status=read(ROOT/'reports/propline-v7/TWELVE_CATEGORY_STATUS.json')
    for cat,s in status.items():
        s.update(actual_line_evaluation='EXECUTED_3BOOKS_W2_W3' if cat in ['pass_yd','rush_yd','rec','rec_yd'] else 'SOURCE_HAS_NO_THIS_MARKET',improvement='NOT_ESTABLISHED_ON_FUTURE_ACTUAL_OFFERS;two exposed weeks',storage='C_LICENSED_SOURCE_AND_CANONICAL_ROWS;freshGitHubrestore pending',website='PREPARED_PENDING_SERVED_VERIFICATION')
        if cat=='pass_yd':s['new_mechanism']='Four origins executed; small actual-line Brier gains vsP2, no hit gain, worse thanP3; numerical reversals; no promotion'
        if cat in ['pass_cmp','pass_att']:s['forecast_issuance']+=';10QB/20incoherentrows remain paper-blocked'
        if cat=='fpts':s['forecast_issuance']+=';chart-labelcoverage-limited shadow'
    write(OUT/'TWELVE_CATEGORY_STATUS.json',status)
    comp=read(ROOT/'reports/propline-v7/COMPONENT_STATUS.json');comp['A_WORKLOAD'].update(implemented='Original opportunity controls plus new forecast-attempt-bin/conditional-yard mechanism, same eligible context',executed='Four count fits:2025W9/W13,2026W2/W3;143query outcomes,3book exact-line comparisons',decision='No hit gain; small Brier gain vsP2/linked but losesP3; numerical/CRPS reversals; no promotion')
    comp['F_PROBABILITIES_PRICES'].update(executed='All3books P1typedpoints/P2/P3; earlier-only prevalence; selectedconfidence/reliability/AUC,Top6/10/20diagnostics;FD P3rushing Brier0.248733 exception,originalPN8failures retained',decision='No current paper/model promotion. No synchronous historical OPEN pricepairs; no-entry/no-payout. Two exposed weeks only')
    write(OUT/'COMPONENT_STATUS.json',comp)
    base=[r for r in raw if r['venue']=='pinnacle'];j=a.scorecard(raw,a.load_records()[1]);v=next(v for v in j['views'] if v['period']=='2026_W1_W7' and v['method']=='PRIMARY');sid=next(g['stratum_id'] for g in v['leader_groups'] if g['stratum']['venue']=='pinnacle');head=a.markdown(j,stratum=sid)
    s='# Actual-line selected-side reliability — v8\n\n'+head+'\nThe frozen common914model-decided comparison remains P2/P1median483–431, P3 500–414, P1mean459–455 and Always-Under476–438. The full constant/prevalence panel below includes two additional known played-zero outcomes without fitted predictions (916cases); that mask is not the914comparison.\n\nDeclared reference remains P2_LEAF/H-MULTI/E0_OP, ALL_ELIGIBLE_OFFERS. Table above is Pinnacle only; all12categories remain required. W2–3 only, timing-unverified last-recorded exact lines. No authenticated selections, book-settled wagers, or promoted leader. Support requires100unique decided outcomes,20games,5weeks plus prespecified confirmation; this source has only2weeks. Wilson headline intervals are independence diagnostics. Detailed v8 probability estimates use game blocks where supported, still conditional on two exposed weeks.\n\n'
    s+='[Every category/method/book, including states](CATEGORY_METHOD_SCORECARD.csv) · [Canonical individual rows CSV gzip](GRADED_ROWS.csv.gz) · [All12category readiness](TWELVE_CATEGORY_STATUS.json) · [Six components](COMPONENT_STATUS.json) · [Full source/retention facts](../../protocol/SOURCE_FACETS_V6.json). The website uses the same versioned canonical datasets, with a compact display projection; full laws/features remain retained.\n\n'
    s+='## Book robustness\n\nAdmission/snapshot rules were committed before performance lookup. DraftKings905admitted/134held;FanDuel896admitted/145held. Full panels repeat32NFLgames,2weeks. Across all3books:2769quotes,1020unique player-game-category cases (including unknowns),487player-games. Quote/method/list counts are not independent football observations. All exact prices,clocks,line/role/cutoff differences and held IDs are retained.\n\n|Book|Procedure|Over W-L/n/rate|Under W-L/n/rate|Combined W-L/n/rate|Eligible/scored|\n|---|---|---|---|---|---|\n'
    for book in ['pinnacle','draftkings','fanduel']:
      for method in ['P2_LAW','P3_DIRECT','P1_MEAN','P1_MEDIAN','ALWAYS_UNDER','ALWAYS_OVER','EARLIER_PREVALENCE_V8']:
        q=[r for r in raw if r['venue']==book and r['method_id']==method];z=a.aggregate(q);s+='|'+ '|'.join([book,method,*[a.side_text(z[x]) for x in ['OVER','UNDER','COMBINED']],str(len(q))+'/'+str(z['scored_offers'])])+'|\n'
    s+='\n[Exact intersections](BOOK_INTERSECTIONS.json.gz): PN/DK502;PN/FD712;DK/FD499;all3books432same-line/period/role/cutoff cases. Common football identities:859/860/814/784respectively. Different lines remain different offers. Equal exact-line forecasts are shared-model arithmetic, not independent confirmation; prices/quote clocks may differ. Main/alternate tier remains unknown.\n\nOriginal24Pinnacle providerVOIDdisputes, reasons and48side-grade conflicts remain frozen. [Symmetric sensitivity](VOID_SENSITIVITY.json.gz) includes all cases primarily and separately excludes a case if either provider side is VOID, across all methods. No VOID→DNP or played-zero→settled-win assumption. For ranked lists, fixed members are retained and exclusions never replaced.\n\n'
    s+='## Role and retained-row checks\n\nRushing remains QB/RB/WR-specific; receiving remains RB/WR/TE-specific. Different selected populations do not establish a causal side advantage. Pinnacle P3 examples below; all books, methods, side/week/role intersections and uncertainty remain in RELIABILITY_SLICES.json.gz.\n\n|Category|Role|Over W-L/n/rate|Under W-L/n/rate|Combined W-L/n/rate|Games/weeks|\n|---|---|---|---|---|---|\n'
    for cat in ['rush_yd','rec','rec_yd']:
      for role in ['QB','RB','WR','TE']:
        q=[r for r in base if r['category']==cat and r['method_id']=='P3_DIRECT' and r['position']==role]
        if not q:continue
        z=a.aggregate(q);s+='|'+ '|'.join([cat,role,*[a.side_text(z[x]) for x in ['OVER','UNDER','COMBINED']],str(z['games'])+'/'+str(z['weeks'])])+'|\n'
    s+='\nRepresentative retained DraftKings P2 rows are chosen for audit status only, never to choose the pilot or fit a rule. Provider grades remain separate from statistical results.\n\n|Player / game / category|Exact line / book|Last source-side clock / C cutoff|P(Under/Push/Over)|Own side / actual / statistical grade|\n|---|---|---|---|---|\n'
    for what in ['WIN','LOSS','PLAYED_ZERO']:
        r=next(r for r in rr if r['venue']=='draftkings' and r['method_id']=='P2_LAW' and (r['status']==what if what!='PLAYED_ZERO' else r['actual']==0 and r['appearance']=='PLAYED' and r['status'] in ['WIN','LOSS']))
        s+='|'+ '|'.join([r['player_name']+' / '+r['game_id']+' / '+r['category'],str(r['line'])+' / '+r['venue'],max(r['source_snapshot_clocks'].values())+' / '+r['decision_UTC'],' / '.join(f"{100*r['_ps'][x]:.2f}%" for x in ['under','push','over']),r['selected_side']+' / '+str(r['actual'])+' / '+r['status']])+'|\n'
    s+='\nThe one FanDuel whole-number line (Tyson Bagent rushing0.0) has unknown participation. P2/P3 preserve exact push mass; the registered half-point prevalence control is explicitly UNAVAILABLE, not rounded or dropped. No decided push or verified venue void is fabricated.\n\n'
    s+='## Selected-side reliability and ranking\n\nAll eight original Pinnacle P2/P3 Briers exceed neutral0.25. Across3books,23/24 exceed0.25; FanDuelP3rushing is0.248733. This small exception is not calibrated future skill. [Per-book/category/side/week/role/history/age metrics](RELIABILITY.json.gz), [joint filter slices](RELIABILITY_SLICES.json.gz), [fixed confidence curves](CONFIDENCE_COVERAGE.json.gz), [earlier-only prevalence](EARLIER_REFERENCE_RESULTS.json), [prior audit](PRIOR_AUDIT.json.gz) and [quote/cutoff sensitivity](CUTOFF_SENSITIVITY.json.gz) retain reversals.\n\nPinnacle mean P(Over) is below actual Over frequency in all4markets for bothmodels. Passing P2:41.51%predicted vs60.32%actual; selectedconfidence60.33% vs42.86%hits. P3passing:57.77%confidence vs41.27%hits. Prior signed yard tails lift means slightly; they do not explain this underprediction. Missing contemporaneous lineup information and model opportunity/quality weaknesses remain possible, not proven causal explanations.172/2624matched quote cases change historical player/team membership between quote and saved kickoff cutoff. This audit uses the later of the two source-side quote clocks.309cases also have that clock before the nominal weekly fit origin; this is a limitation, not proof of leakage without checking actual eligible training prefixes. Even unchanged membership can have different age features. No earlier-quote-cutoff availability claim is made.\n\nPinnacle Over-discrimination AUC is near0.5 (P2range0.490–0.545;P3range0.509–0.544), while selected-confidence AUC varies0.464–0.583. Calibration, directional bias and ranking are distinct diagnostics. No global Brier failure proves every rank is useless; no small perfect subset validates its nominal probabilities. Full bins preserve counts,gaps,uncertainty and infinity/failure states.\n\n|Book|Method|K|Selected/decided|W-L/rate|Mean selected confidence|Games/weeks|\n|---|---|---|---|---|---|---|\n'
    for r in ranktotals:
      if r['scope']=='GLOBAL' and r['side_variant']=='MIXED':s+='|'+ '|'.join([r['book'],r['method'],str(r['K']),str(r['selected_count'])+'/'+str(r['decided']),a.side_text(dict(wins=r['wins'],losses=r['losses'],decided=r['decided'],rate=r['hit_rate'])),f"{100*r['all_selected_mean_confidence']:.2f}%" if r['all_selected_mean_confidence'] is not None else 'N/A',str(r['games'])+'/'+str(r['weeks'])])+'|\n'
    s+='\n**Every TopK number above is an exploratory LAST-RECORDED-LINE RANKING DIAGNOSTIC.** No simultaneous board, historical OPEN lifecycle or line-continuity evidence; selected quotes or forecast cutoffs can occur after another selected game. No executable ticket, original6/6, payout or prospective performance is implied. DK P3K6selects12but only11decided (one unknown), not a perfect six. [All global/category mixed/Over-only/Under-only policies](RANK_SUMMARY.csv), [week-level states/confidence/timing](RANK_RESULTS.json.gz), [exact membership](../../artifacts/reliability-v8/RANK_MEMBERSHIP.json.gz) and [technical/tie exclusions](../../artifacts/reliability-v8/RANK_EXCLUSIONS.json.gz). One player/list; outcome-blind ties; no forcedK; providerVOID sensitivity never replaces members. New passing arms have within-category lists only.\n\n'
    s+='## Executed workload mechanism\n\n[Pre-fit protocol](../../protocol/WORKLOAD_LINK_V8.json), [fit ledger](../../artifacts/reliability-v8/FIT_LEDGER.json), [all numerical results](WORKLOAD_NUMERICAL.json), [opportunity errors](WORKLOAD_OPPORTUNITY_ERRORS.json), [exact-line results](WORKLOAD_ACTUAL_RESULTS.json), [paired changes/intervals](WORKLOAD_PAIRED_UNCERTAINTY.json). Only4newattempt fits,143outcomes across2025W9/W13 and2026W2/W3; original yard/control fits reused. This is not full2025validation. Same32E0_OPfeatures, originalrows/history/seven-day assumption, training-only transforms. Historical jointattempt/yardcounts form fixed conditional yard laws; forecastattempt-bin weights replace leaf weights. Target actualattempts are diagnostic labels only. Zeroattempt→zeroyards and the changed prior are explicit in new linked support control. No NGS/calibrator/injury effect was added.\n\n|Book|P2 Brier|Linked Brier|Workload Brier|P3 Brier|Workload W-L/n|\n|---|---|---|---|---|---|\n'
    ms=read(OUT/'WORKLOAD_ACTUAL_RESULTS.json')
    for book in ['pinnacle','draftkings','fanduel']:
      z={r['method']:r for r in ms if r['book']==book};w=z['P2_WORKLOAD_V8'];s+='|'+ '|'.join([book,*[f"{z[m]['half_scaled_UPO_Brier']:.6f}" for m in ['P2_LAW','P2_LINKED_V8','P2_WORKLOAD_V8','P3_DIRECT']],f"{w['wins']}-{w['losses']}/{w['decided']}"])+'|\n'
    s+='\nWorkload modestly improves Brier over P2/linked at all3books, but does not beat P3 and does not increase selected-side wins. Numerical and CRPS results reverse by origin:2025W9worse/W13better;2026W2worse/W3mixed. Forecastattempts still underpredict by1.84W2and3.40W3attempts on the full query panel. Effects are inconclusive, with paired game-block intervals and research exposure disclosed. No model promotion or alteration of Week8forecasts. The small proper-score gains remain reported even where MAE worsens. Fallback branches are software-verified; none of these143queries actually exercised a missing-bin fallback.\n\n'
    s+='## Current captures, coverage and retained evidence\n\nOriginal2,513v4forecasts/407roster candidates/13games and serverreceipt00:13:48ZNov1 remain unchanged; candidates are not confirmedstarters. CMP/ATT coherence blocks and chart-label limits remain. [Later status audit](CURRENT_GATE_FINAL.json) records actual current state; in-progress games cannot receive new pregame forecasts and are not final grades. No new current actual-line selections or six-leg entries qualify. No forced entry; six-of-six/payout/netprofit N/A.\n\n[Coverage matrix](OFFER_COVERAGE.csv) retains every12category×book×week/year cell: sourceonly4marketsW2–3;W1,W4–7andallpriorseasonsabsent. Additionalbooks cannot fill them. [A/B/C exact prediction matching](../propline-v7/ABC_MATCHING.json) remains NOT ESTABLISHED for every category: native case identities alone do not supply A/B typed forecasts, exact laws, cutoffs and outcome versions. [Bounded source disposition](ALTERNATIVE_SOURCE_DISPOSITION.json): two other public candidates contain team/game markets, not nativeplayerprops; no newNFLfile,API,key/signup/payment or off-GitHub archive was used. Currentindividualprops still need a licensed fresh exact-player/event/stat/line/side/tier snapshot with real observation/lifecycle clocks and a compliant recoverable route; house settlement and entryquotes are additional gates. Source prices alone do not authenticate simultaneous marketOPEN; no no-vig benchmark was manufactured.\n\n[Independent inference/temporal verification](INDEPENDENT_V8.json), [failures/corrections](FAILURES.json), [resource report](RESOURCE_RECEIPT.json), [GitHub fresh restore](GITHUB_RESTORE.json) and [exact publication states](PUBLICATION.json). Publication/restoration receipts are appended after actual checks. Originalv7andv7.1, NGS losses, v4/v5records and oldreceipts are frozen. No additional personal licence grant is requested for the already-CCBYsample.\n\nNo evidence-supported Over, Under or combined category leader is established: only2weeks versus5required, repeated football cases, unverifiedboardtiming and no subsequent independent confirmation. Observed book-specific maxima in the table remain descriptive. Next bounded wave: obtain/qualify genuinely fresh permitted current offers or extend licensed category/week coverage; grade originalv4onlyafter independentFINAL/participation proof. Any further workload/calibration variant needs a new earlier-only protocol/fit budget, not reuse of these outcomes as confirmation.\n'
    (OUT/'README.md').write_text(s)
    return dict(category_method_rows=len(summary),graded_rows=len(flat),ranking_summary_views=len(ranktotals),paired_comparisons=len(comparisons)+len(numeric))

if __name__=='__main__':print(build())
