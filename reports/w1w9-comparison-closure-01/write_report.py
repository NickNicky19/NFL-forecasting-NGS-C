"""Render the existing scoped records; never invent missing category cells."""
import json,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_bytes())
def wl(s):
 if not s or not s.get('decided'):return 'N/A'
 return f"{s['wins']}-{s['losses']}/{s['decided']}/{100*s['rate']:.2f}%"
def main():
 h=load(B/'TWELVE_CATEGORY_HEADLINE.json');c=load(B/'completion/NINE_WEEK_COMPLETION.json');a=load(B/'attempt-check/EIGHT_WEEK_ATTEMPTS.json');side=load(B/'ANNUAL_SOURCE_SIDE_RECONCILIATION.json')
 columns=['CATEGORY','ORIGIN SESSION','EXACT PROCEDURE/OUTPUT/POLICY','ACTUAL WEEKS','OVER W-L/N/%','UNDER W-L/N/%','COMBINED W-L/N/%','ELIGIBLE/SELECTED/DECIDED/UNAVAILABLE/UNKNOWN','GAMES','AVAILABLE/FALLBACK','MATCHED CONTROL/PAIRED CHANGE','UNCERTAINTY','EVIDENCE TIER','NINE-WEEK COVERAGE STATUS','RECOMMENDATION/EXACT REMAINING ACTION']
 out=[]
 for r in h['rows']:
  cov=r['coverage'];combo=r['own_sides']['combined'];rec=[r['category'],str(r['origin'] or 'N/A'),str(r['exact_procedure'])+' / '+str(r['output'])+' / '+str(r['decision_policy']),','.join(map(str,r['actual_weeks'])) or 'None',wl(r['own_sides']['over']),wl(r['own_sides']['under']),wl(combo),'/'.join('N/A' if z is None else str(z) for z in [cov.get('eligible'),cov.get('selected'),combo.get('decided') if combo else None,cov.get('unavailable'),cov.get('unknown')]),str(cov.get('games') or 'N/A'),'/'.join('N/A' if cov.get(k) is None else str(cov[k]) for k in ['available','fallback']),json.dumps(r['matched_control'],separators=(',',':')),str(r['uncertainty']),str(r['evidence_tier']),r['nine_week_status'],r['recommendation']+'; '+r['exact_next_action']];out.append(rec)
 with (B/'HEADLINE_TWELVE_CATEGORY.csv').open('w',newline='') as f:w=csv.writer(f,lineterminator='\n');w.writerow(columns);w.writerows(out)
 short={'pass_yd':'A HGB MAE point','pass_td':'A corrected Count-A mean','pass_cmp':'B2 lower median / saved law (tie)','pass_att':'B common-exposure lower median','pass_int':'A Leaf mean','rush_yd':'A equal-CDF/Cat/HGB point','rush_att':'A Backfield mean','rec':'C P1 pooled mean; WR/TE common mask','rec_yd':'A Leaf mean','rush_rec_yd':'A Response mean','anytime_td':'No exact qualified offer product','nick-chart-ppr-v1':'No exact qualified chart offer'}
 table=['| Category | Origin / procedure-output-policy | Actual weeks | Over W-L/N/% | Under W-L/N/% | Combined W-L/N/% | E / selected / decided / unavailable / unknown | Games | Matched control / change | Uncertainty | Tier | Nine-week status | Recommendation / remaining action |','|---|---|---|---|---|---|---|---|---|---|---|---|---|']
 for r in h['rows']:
  cov=r['coverage'];s=r['own_sides'];cat=r['category'];n=s['combined']['decided'] if s['combined'] else None
  controls=r['matched_control'];ct='N/A'
  if cat=='pass_cmp':ct='Over115/226; B0mean119/226; +7 / +3 wins'
  elif cat=='pass_att':ct='Under99/195; tie; native adjusted69/112 > median55/112'
  else:
   opts=[(k,v) for k,v in controls.items() if isinstance(v,dict) and isinstance(v.get('wins'),int) and isinstance(v.get('decided'),int)]
   if opts:
    k,v=max(opts,key=lambda kv:kv[1]['wins']/kv[1]['decided']);ct=f"{k} {v['wins']}/{v['decided']}; "+(str(s['combined']['wins']-v['wins'])+' wins' if s['combined'] else 'N/A')
  status='9/9 named B-subroster; A/C incomplete' if cat=='pass_cmp' else '8/9; exact W9 output missing' if cat=='pass_att' else 'SOURCE_BLOCKED' if not r['actual_weeks'] else 'PARTIAL; W6-9 common comparison missing'
  action='A/B: later142 strong-A/C joins' if cat=='pass_cmp' else 'B: exact W9 median on known30 offers' if cat=='pass_att' else 'A/native auth + exact-head approvals; website admission' if cat=='pass_td' else 'Exact event/market/components needed' if not r['actual_weeks'] else 'Owner: same-procedure later real-line panel/output bindings'
  es='/'.join('N/A' if z is None else str(z) for z in [cov.get('eligible'),cov.get('selected'),n,cov.get('unavailable'),cov.get('unknown')]);weeks='1-9' if cat=='pass_cmp' else '1-8' if cat=='pass_att' else '1-5' if r['actual_weeks'] else 'None'
  table.append('| '+' | '.join([cat,short[cat]+'; [exact bindings](TWELVE_CATEGORY_HEADLINE.json)',weeks,wl(s['over']),wl(s['under']),wl(s['combined']),es,str(cov.get('games') or 'N/A'),ct,'Paired intervals descriptive; no proven global superiority' if r['actual_weeks'] else 'N/A','Retrospective / clocks and main-alt unverified' if r['actual_weeks'] else 'No qualified exact offers',status,r['recommendation']+'; '+action])+' |')
 weekly=['| Week / source | Offers | Games / scheduled | B0 mean W-L | B2 median/law Over W-L | Under W-L | Combined W-L |','|---|---|---|---|---|---|---|']
 x=[r for r in c['rows'] if r['procedure_id'].endswith(':B0') and r['product']=='P1_MEAN'][0];y=[r for r in c['rows'] if r['procedure_id'].endswith(':B2') and r['product']=='P2_STATISTICAL_LAW'][0];wc=load(B/'completion/WEEK_COVERAGE.json')['weeks']
 for l,r,g in zip(x['weekly'],y['weekly'],wc):
  def pair(v):return f"{v['wins']}-{v['losses']}"
  weekly.append(f"| {r['week']} / {'A annual' if r['week']<=4 else 'B native'} | {r['eligible']} | {r['games']}/{g['scheduled_games']} | {pair(l['own_sides']['combined'])} | {pair(r['own_sides']['over'])} | {pair(r['own_sides']['under'])} | {pair(r['own_sides']['combined'])} |")
 intro='''# Weeks 1–9 comparison closure — scoped results and exact remaining cells

The completion comparison now represents **all nine weeks: 226 real-line diagnostic opportunities, 119 covered games out of 136 scheduled**. B2's lower-median and exact-law direction products tie at **122–104/226 (53.98%)**. Their own Over record is **33–22/55 (60.00%)**, Under **89–82/171 (52.05%)**. B0 mean scores119–107, B0 median/law117–109, B2 mean112–114. Always-Over scores115–111 and Always-Under111–115 on the identical226 cases. No forecast is technically unavailable or unresolved on this panel; all6 modeled products have226 available/selected/decided outputs and zero declared charting fallbacks.

This is a **complete named-panel result for those six B products**, not a complete A/B/C championship. A's CatBoost and HGB controls both score51–33 on the early84 cases; their exact points remain unverified on the later142. The separate old A W1–5 panel scores52–36/88 for both; it cannot be compared directly with122/226 or used to fill B's missing counterpart. C's retained mean/median comparison baseline now has saved outputs for all nine weeks after its two missing origins were executed. Its protected-board joins remain unscored, with the original CMP/ATT primary-selection and conditional-population holds preserved.

The passing-attempt median comparison also extends to **W1–8:99–96/195**, Over5–5/10 and Under94–91/185, covering104 of121 scheduled games. It ties Always-Under99/195; Always-Over scores96/195. On the later112 cases the saved-adjusted reference scores69/112 versus median55/112. Week9 already has30 retained attempt offers but lacks this exact common-exposure output/score binding. No law result was substituted for a median.

The table gives each listed procedure's own sides. **Other categories remain partial**, and no unique all-session nine-week winner or automatic release is certified. The full machine table includes exact hashes, history/output/policy, fallback, source limits and owner actions. Different panels/roles below are not a common global leaderboard.

'''
 text=intro+'\n'.join(table)+'''

[Full requested-column CSV](HEADLINE_TWELVE_CATEGORY.csv), [typed headline records](TWELVE_CATEGORY_HEADLINE.json), [all143contenders ×9week cells](CANDIDATE_WEEK_MATRIX.csv), [detailed source slices/actions](CANDIDATE_WEEK_MATRIX.json).

## Completion source policy and weekly results

The fixed source calendar uses A's completed84-offer W1–4 join and B's142-offer W5–9 native panel. A annual W5 is excluded from the primary union; its overlapping opportunities remain a separate sensitivity cell. No source was chosen by outcome or model score. Exact producer `d79acddf5f094c85001c9b17a525ac7d9e25f9ec`, history/update, QB/full-game target, mean/lower-median/law rules and corrected-outcome semantics match. Official season-week slices are disjoint. Source/operator commitments support conditional aggregation; C did not inspect A/B private row vectors or authenticate original quote clocks.

Different books/files are not a veto. Unknown quote clocks, main/alternate classification, venue settlement and book-key normalization remain explicitly unknown. These are retained real-line, current-vintage chronological **retrospective diagnostics**, not original issued picks, an authenticated pregame strategy, or certified ordinary-main-line league coverage. Reaching nine weeks does not improve this evidence tier. [Completion compatibility](source-contract/COMPATIBILITY_DECISION.json) and [attempt identity bridge](source-contract/attempt/COMPATIBILITY_DECISION.json) bind the source decisions.

'''+ '\n'.join(weekly)+'''

The scope contains partial within-week boards. Missing source opportunities are not intentional abstentions. Covered-game counts and the retained current schedule are descriptive; two quarterbacks per game are not assumed to define the league's eligible offer universe.

## Own-side leaders, uncertainty and selected products

Within the common226 modeled-procedure panel, the highest own-Over rate is B0 mean18–10/28 (64.29%). The highest own-Under rate is B2 median/law89–82/171 (52.05%). These different selected pools are descriptive. They are not stitched into a router. The same B2 complete procedure's entire122–104 record remains the combined leader/tie in this scoped comparison.

B2 law exceeds B0's same-law direction by5/226 and B0 mean by3/226. The paired whole-week sensitivity interval versus B0 mean is approximately−2.03 to+4.89percentage points; versus Always-Over,−4.90 to+10.60points. Against Always-Over there are171 disagreements,89 candidate-only wins and82 control-only wins, derivable from the original own-Under group. Individual B2/B0 disagreement vectors are not exposed to C; source-specific counts/intervals remain linked. Nine exposed week clusters, repeated players, source composition and repeated method selection limit inference. No significance rule or accuracy gate was added after the result.

Week bootstrap uses registered500 resamples/seed1703 of integer paired same-mask weekly sufficient counts. It does not average unequal-denominator percentages, reproduce a private game bootstrap, or adjust for all prior model selection. Source-stratified results and adverse weeks remain visible. B2's primary mean-direction information test remains unsuccessful:112/226 versus B0 mean119/226. The secondary median/law result does not erase that negative finding or establish deployment superiority.

A's early probability summary uses binary Over-event Brier; B's native summary uses half-multiclass Over/Under/push Brier. They are not pooled. Native Brier worsens0.266545→0.269180 and log loss0.728903→0.735179 despite the two-decision law-direction gain there. Point outputs receive no invented probability/confidence or EV. Broad numerical error, offered-player error and median/mean typing remain separate; native attempt `numerical_mean_MAE` is not a verified median error.

[Source-bound annual side reconciliation](ANNUAL_SOURCE_SIDE_RECONCILIATION.json) preserves all prior143 aggregate views, including44 law views and original population corrections; only22 are exact frozen-A-point matches. Those143 source views are distinct from the frozen143 product records. Law ties and prior selective maxima are visible without reopening the roster or claiming identical row/side membership from identical totals.

No nine-week selective winner is established. All18 previously registered B Top6/10/20 views and both P90 gates remain in [the selected-policy table](SELECTIVE_POLICY_STATUS.json). On W5–9, B2's Combined Top20 is55/100 at100/142coverage; its Combined Top6 is14/30. Under-only/Over-only variants retain their own volumes. P90 selects zero and has N/A accuracy, with evaluated-board weeks separate from selected/decided weeks. The early84 broad-board counts cannot supply unexecuted early TopK memberships. The website's separate five-week full selector remains SHADOW with10candidate-generated and100reference-fallback selections; it is not this category-level comparison.

## Completed receipts, C outputs and missing execution

A's `5a41d2bac6027e0ac1b5a2744d52f8ec5e93c47e` receipt establishes the84-offer W1–4 join complete. B's `acd32c8e` checkpoint, with immutable receipt publication, establishes its frozen conditional packet grading and W4selector independent check complete. Older pending messages are superseded, not used to request duplicate work. The B packet has six graded arm rows for three QB appearances, two DNP forecast records and two IR-unavailable records, with zero offers/original selected sides. B0 mean MAE8.5858 versus B2 8.6898 is one-game forecast-only evidence, not a prop hit rate.

C's original242 query points throughW7 remain unchanged. Exact two missing historical origins were fitted under the same QB-only/strict7day contract, with safe JSON restoration, prior-origin membership/feature parity and target/future mutation checks. The [315-query typed mean/median handoff](C-panels/COMPLETION_HANDOFF_W1_W9.json) provides allW1–9 outputs; no probability interpolation, private offer transfer or source-clock backdating occurred. Fitting/query coverage is not offered-line scoring, a pregame roster universe or a release. A owns the early C-contender join and B the later native-board scoring after exact identity/source contracts match.

Existing A source records supply20 corrected frozen Week8 constant-side measurements;14 change substantively under presence qualification. Original/corrected records remain separate. Their original threshold/book/role provenance remains unresolved at C scope, so they do not fill qualified actual-offer weeks or become100% accuracy claims from missing labels. No blanket Week8 invalidation is inferred. [The finding-specific receipt](A-intake/LATER_ALL12_RETAINED_CELL_CHECK.json) names each category's source/output gap.

The [finite queue](FINITE_QUEUE.json) gives one executor, exact artifact/action and completion condition. A/B offer owners must score A's strong later controls and C's ready saved points on the identical native masks. B must close the exact Week9attempt output/score. Other categories need their source-specific later actual-offer/output bindings; annual W6–7 references are excluded. Inherited anytime-TD and exact chart offers remain blocked rather than receiving invented Under/NO or substitute fantasy contracts.

Existing five-week primary-product duration rules are unchanged. Nine weeks and all-category completion are not new release gates. Count A's authorized connection owner's HTTP401 diagnosis and A's exact-head protected-PR approvals remain separate from historical scoring. The original website owner alone handles fresh feeds, isolated category admission and release. No original-site product was activated or selector silently changed by C.

Existing2022–2025 robustness work, genuine future capture and original frozen packets remain in their finite owner queues. Missing later lines never become original earlier picks. No new source collector, scheduler, paid acquisition, unsafe model loading, cross-owner implementation or wagering occurred.

FTN-dependent B derived results retain attribution to **FTN Data via nflverse, CC BY-SA4.0**. Other football inputs, models and code retain their separately bound terms; this is not a license claim for the entire project. No protected raw offers or raw charting feed were redistributed.
'''
 (B/'README.md').write_text(text)
 print('Rendered all12headline CSV and consolidatedreport from exact records')
if __name__=='__main__':main()
