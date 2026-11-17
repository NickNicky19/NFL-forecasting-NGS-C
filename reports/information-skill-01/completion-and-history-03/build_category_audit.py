"""Readable audit view of retained aggregates; never fit, infer or grade."""
from pathlib import Path
import datetime
import gzip
import hashlib
import json
import time

ENTRY=time.process_time()
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
HISTORY='reports/information-skill-01/execution-authorization-02/method-history/METHOD_HISTORY.json.gz'
DECISIONS='reports/category-decision-release-01/CATEGORY_PRODUCT_DECISIONS.json'
OPPORTUNITY='reports/information-skill-01/executed-receipts-gap-closure-01/intake/B_RECEIPT.json'


def read(path):
    b=(ROOT/path).read_bytes()
    return json.loads(gzip.decompress(b) if str(path).endswith('.gz') else b)


def binding(path):
    p=ROOT/path
    return dict(path=path,bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())


def link(path,label=None):
    return '['+(label or path)+'](../../../'+path+')'


def explanation(name):
    if 'absolute-loss' in name:return 'Shared HGB predicts a point under absolute loss from registered ordinary-history and optional qualified NGS blocks. It tests whether richer inputs improve the same point learner; a point is not a probability.'
    if 'Leaf' in name:return 'Shared tree leaves estimate a conditional response distribution from earlier outcomes, with registered role-prior/tail fallback. Mean, median and exact-line law are distinct products beneath this family.'
    if 'Histogram boosting' in name:return 'A monotone threshold classifier learns P(outcome≤line|earlier features); larger compatible Over/Under mass gives direction. It can learn nonlinear relationships without pretending a projection gap is confidence.'
    if 'logistic threshold' in name:return 'A regularized threshold-logistic CDF is a simpler probability control; fixed transforms and the threshold coefficient are fitted only on admitted earlier cases.'
    if 'sigmoid' in name:return 'An earlier-season out-of-time sigmoid changes the probability scale, not the underlying football information. The failed calibration finding is retained; numerical or calibration changes are not direction gains.'
    if 'Constant-side' in name:return 'Always-Over/Under are same-case difficulty/prevalence controls. Winning a panel does not automatically approve them as live rules.'
    if 'prevalence' in name:return 'Earlier-only event prevalence is a sparse-history/probability control; the target game never supplies its own baseline.'
    if 'workload' in name.lower():return 'The passing-workload family links forecast opportunity to downstream passing output. Different workload/linked-law policies remain separate; later actual attempts are an oracle diagnostic only.'
    if 'history point' in name:return 'Earlier-history mean/median is a strong simple point/fallback comparator. Its own line crossings are retained without invented per-pick probabilities.'
    if 'P4_HYBRID' in name:return 'A named proposed hybrid is preserved as a proposal/source-dependent record, not proof of a fitted model or a qualified independent-market reference.'
    if 'Poisson' in name:return 'A shared/partially pooled Poisson model regularizes feature and player/team/opponent effects. It tests pooling/representation, with explicit sparse/unseen fallback rather than an unrestricted model per player.'
    if 'target-share' in name:return 'The receiver target-share study forecasts allocation from earlier usage/context. Its completed no-gain result is not renamed as authenticated teammate-availability research.'
    if 'completion context' in name:return 'The team-completion study tests opportunity/context information beyond the retained direct procedure; opportunity, conversion and their uncertainty remain different components.'
    if 'negative-binomial' in name:return 'Distributional boosting learns reception mean and dispersion from features, testing count-law shape beyond an empirical Leaf law. Native evidence remains research/shadow and stronger direct controls stay visible.'
    if 'Student-t' in name:return 'Signed-yard distributional boosting estimates location/scale/tails and discrete CDF bin masses. The exact frozen recipe is closed to tuning; this does not reject every Student-t formulation.'
    if 'passer-mixture' in name:return 'A change in an earlier usage-based passer mixture interacts with shrunk receiver-specific targeting preference. It is not injury/starter knowledge; a same-window marginal-share identity was explicitly excluded.'
    if 'Count A' in name:return 'A source-owned count law supplies a corrected expected mean and separate law products. Exact preprocessing/corrector/output/fallback bindings matter; legacy_point, a median or an all-null mean field cannot substitute.'
    if 'Backfield' in name:return 'A source-owned backfield count/CDF procedure separates count opportunity and selection policy. Top-6 results are selected-policy evidence, not the whole board or website Top Picks.'
    if 'CatBoost' in name:return 'A source-owned CatBoost procedure is a retained learned comparator; objective, output and selected-opportunity mask stay bound to its exact owner recipe.'
    if 'TabICL' in name:return 'The pinned pretrained in-context classifier uses earlier exact-offer examples to predict the offered event. It supplies event probabilities/directions, not a count mean; learned and fallback weeks must be separate.'
    if 'Same-information logistic' in name:return 'The simple logistic classifier is the same-information control for the frozen in-context learner, with earlier transforms and grouped chronological contexts.'
    if 'Website' in name:return 'The production provider/reference baseline, direction margins, ranking and fallback are operational products. Retention/capture does not prove scientific superiority.'
    return 'The source gives this exact owner label/configuration; its private kernel or correction path is not reconstructed from the alias. Preserve the separate procedure and require the owner explanation before declaring equivalence or superiority.'


LESSONS={
'pass_yd':('Workload and conditional gain can fail separately. Native C point/law evidence and A/B archived comparisons use different offered populations; a numerical winner is not a universal direction winner. Provider/market assistance must remain labelled throughout the input path.',
            'A source-feasible diagnostic is forecast pass-depth/opportunity mixture × conditional signed gain using eligible earlier PBP, with workload held fixed first. This is only a candidate: compare against existing passing-workload studies and obtain the owning execution lease before any fit. Do not supply realized target-game depth or attempts.'),
'pass_td':('Count A is an exact corrected-mean delivery task as well as a research contender. Historical duration does not prove fresh native inference, feed publication, consumer admission or a Top Picks upgrade. A missing/legacy mean field is a typing problem, not a model comparison.',
            'No additional predictive fit is justified by the catalog alone. First complete the existing authorized corrected-mean producer/consumer route and compatible exact-line evaluation; a later opportunity/conversion hypothesis needs a distinct source-qualified block and owner no-duplication check.'),
'pass_cmp':('The fixed-attempt M2 variance extension did not establish a direction upgrade. SKILL mean R0 improved its weak parent by two wins over226 cases but lost to stronger retained controls; its law and full-window proper scores worsened. C1 and opportunity team-fit strict reproductions remain FAILED in their exact scope.',
            'Finish the already-authorized frozen B TabICLv2 comparison and its same-information logistic control; do not commission a second classifier or another variance/offset/confidence sweep. Newer owner runtime/result/history receipts are consolidated by root, not guessed here.'),
'pass_att':('Attempt error is an observed limitation, not an additive causal percentage. Opportunity-v1 had a small mean-direction gain over its parent but did not beat strong same-case controls; completion means/joint probability quality could worsen. Exact means, medians and law directions are not interchangeable.',
            'The next distinct information candidate is origin-known team/QB/personnel availability and role, but authenticated historical vintages/full event-effective identity/status remain a source gate. Current depth load dates are not injury clearance; preserve prospective observations through existing owners instead of repeating usage proxies.'),
'pass_int':('Corrected source-presence and explicit-zero evidence are essential for rare interceptions. Appearance alone cannot fill a missing pass_int value. Original frozen predictions and corrected grades are different versions; a corrected grade is not improved forecasting.',
            'No new probability offset is justified. First preserve the qualified corrected interception board and source/identity overlap. A later FTN interception-worthy/exposure block would need its exact prior-use and availability contract checked by B; the completed completion-ball-quality result is not automatically an INT experiment.'),
'rush_yd':('A direct yardage forecast and an allocation×gain pipeline answer different questions. Signed gains, QB scrambles/kneels and RB-only carries must keep their registered populations. A2/A3 and other negative allocation findings cannot be erased by a new label.',
            'A bounded future-context gain relationship is source-feasible as a current-vintage diagnostic using retained direction/down/distance PBP. A must first reconcile its owned matchup equivalents and forecast the context mixture; this audit authorizes no fit and no target-game run mix.'),
'rush_att':('Broad board, RB-only and mixed-position masks differ. The completed usage-state addition and the adverse 2023 Backfield extension did not establish an upgrade. An earlier frozen Top-6 success does not validate a new allocation or personnel recipe.',
            'A’s distinct personnel-conditioned carry hypothesis remains the priority, but it needs authentic injury/practice/inactive/transaction observations and a complete event-effective teammate universe. The completed depth-history inspection is not that feed; no new history search or fit is commissioned here.'),
'rec':('Target-share, contextual-profile, raw/adjusted defense, timing, pooling and distributional experiments have different identities. The used role-depth scalar changed14 law decisions with7wins each—zero net gain, not the older unused-feature finding. The latest passer-mixture scalar and its missing flag had zero fitted splits; C0/C1/C2 share the same268-decided predictions, so no substantive gain was established.',
       'Do not force the frozen learner to use the scalar. A credible distinct next question is genuinely observed role/personnel-conditioned target redistribution; it remains gated by authenticated teammate/status history. A different relationship learner on dyad exposure would first need earlier component evidence and an exact prior-equivalence check, not an automatic refit.'),
'rec_yd':('Opportunity and conditional gain/tails must stay separate. Leaf/Response-CDF, direct points and the frozen signed Student-t law are different products. Failure of the exact Student-t recipe does not disprove source-qualified depth/QB/gain interactions or every tail law.',
          'A possible later source-feasible diagnostic is forecast depth/target-area mixture × conditional signed gain, using earlier QB/receiver/defense context with shrinkage. It is not route alignment. Existing C01/C03/M3 equivalents must be reconciled before treating it as new; no fit is authorized here.'),
'rush_rec_yd':('Combined outcomes require both qualified components; absent rec/rush statistics are not zeros. Means add under a common event/contract, but medians do not generally add and component laws do not supply their dependence. Sparse actual-line coverage cannot be repaired with internal thresholds.',
                'A coherent joint residual/opportunity law on complete earlier paired outcomes is a source-feasible numerical candidate, not a qualified new actual-line experiment. Reconcile existing allocation/joint/Astra equivalents and obtain matching real combined-yard offers; inaccessible Astra evidence remains an explicit novelty gap.'),
'anytime_td':('The inherited event is at least one rushing-or-receiving TD, not passing TD or a generic touchdown label. Binary event scores can exist without an offered NO side. No authentic missing NO/Under market or settlement rule is invented.',
              'The concrete next dependency is a compatible observed YES/event offer and timing/participation contract through existing sources, not a new model or synthetic Under threshold. Preserve event-only evidence separately; no additional predictive fit is justified by absent offers.'),
'nick-chart-ppr-v1':('This is the exact source-defined Nick chart contract/lattice, not a league fantasy/PPR proxy. Complete required components and their known/null states are prerequisites for an outcome. Existing numerical/grid evidence does not create an authentic matching prop contract.',
                     'First qualify the exact chart scoring, full component outcomes and genuine matching offered contract. A coherent joint-statistic forecast is only a later numerical hypothesis after prior-method reconciliation; no substituted fantasy weights, internal lines or new fit are commissioned.')}


def own_record(row):
    own=row.get('own_sides',row.get('own',{}))
    if not own:own={k:row[k] for k in ['OVER','UNDER','COMBINED'] if k in row}
    return own


def short_metric(value):
    if value is None:return 'N/A'
    try:return format(float(value),'.6g')
    except (ValueError,TypeError):return str(value)


def record_string(value):
    if not isinstance(value,dict) or value.get('wins') is None or value.get('losses') is None:return 'N/A'
    n=value.get('decided')
    rate=value.get('rate')
    return f"{value['wins']}–{value['losses']} / {n if n is not None else 'N/A'} / {100*rate:.2f}%" if isinstance(rate,(int,float)) else f"{value['wins']}–{value['losses']} / {n if n is not None else 'N/A'} / N/A"


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    history=read(HISTORY);decisions=read(DECISIONS);opp=read(OPPORTUNITY)
    registry={r['id']:r for r in read('reports/CATEGORY_REGISTRY_V3.json')}
    by_decision={r['category']:r for r in decisions['categories']}
    categories=[]
    for cat in history['categories']:
        ps=[p for p in history['procedures'] if p['category']==cat]
        families=[f for f in history['families'] if cat in f['categories']]
        mechanisms=[dict(owner=f['owner'],name=f['name'],relationship_and_reason=explanation(f['name']),
                         exact_procedure_keys=[p['procedure_key'] for p in ps if p['family_id']==f['family_id']],
                         retained_stages=sorted(set(s for p in ps if p['family_id']==f['family_id'] for s in p['milestones']))) for f in families]
        numerical=[]
        for e in history['executions']:
            if e.get('source_path')!='reports/all12-v2.1/SCORES.csv':continue
            r=e.get('retained_aggregate',{})
            if r.get('target')==('fpts' if cat=='nick-chart-ppr-v1' else cat) and r.get('history')=='H-MULTI' and r.get('arm')=='E0_OP' and r.get('horizon')=='ALL':
                numerical.append(dict(source=e['source_path'],execution_id=e['execution_id'],procedure_key=e['procedure_key'],record=r,
                                      scope='Fixed metadata-selected reference slot, not best-score selection;2026W1–7 numerical/synthetic-grid evidence, not actual offered lines'))
        decision=by_decision[cat];panels=[]
        for index,panel in enumerate(decision.get('highest_observed_panels',[])):
            panels.append(dict(source=DECISIONS,source_record=f'categories[{cat}].highest_observed_panels[{index}]',
                panel_id=panel.get('panel_id','NOT_RETAINED'),origin=panel.get('origin',decision.get('origin')),
                procedure_id=panel.get('procedure_id',panel.get('exact_procedure','NOT_RETAINED')),
                own_sides=own_record(panel),coverage=panel.get('coverage','NOT_RETAINED'),
                actual_season_weeks=panel.get('actual_season_weeks',panel.get('actual_weeks_as_reported','NOT_RETAINED')),
                source_week_qualification=panel.get('source_week_qualification','SOURCE_PANEL_TIER_APPLIES'),
                evidence_tier=panel.get('evidence_tier','NOT_RETAINED_IN_PANEL'),
                numerical_metrics=panel.get('numerical_same_offered_player_rows','NOT_RETAINED_IN_PANEL'),
                matched_controls_and_uncertainty=panel.get('matched_strong_control_pairs','SOURCE_LINKED_NOT_RETAINED_IN_PANEL'),
                limits=panel.get('limits','Not pooled with other panels; original source/grade/admission overlays remain authoritative.')))
        latest=[]
        if cat in ['pass_att','pass_cmp']:
            for r in opp['own_side_cumulative']:
                if r['target']==cat:latest.append(dict(source=OPPORTUNITY,exact_procedure_output=r['exact_output'],
                    actual_weeks=[5,6,7,8,9],evidence_tier=opp['actual_line_scope']['evidence_tier'],
                    own_sides={'OVER':r['Over'],'UNDER':r['Under'],'COMBINED':r['Combined']},
                    coverage=opp['actual_line_scope'],offered_MAE=r.get('offered_MAE'),scope='Earlier retained opportunity-v1 report; current root owner intake may supersede status, not these original grades.'))
        if cat=='rec':latest.append(dict(source=history['current_C_pilot_result']['source'],exact_procedure_output='C0/C1/C2 direct-threshold products',record=history['current_C_pilot_result']))
        lessons,next_hypothesis=LESSONS[cat]
        reg=registry['fpts' if cat=='nick-chart-ppr-v1' else cat]
        categories.append(dict(category=cat,scoring_contract=reg['scoring_contract_id'],eligible_roles=reg['primary_roles'],
            what_was_actually_tested=mechanisms,exact_procedure_keys=[p['procedure_key'] for p in ps],
            inputs_history_and_clocks='Ordinary role-appropriate histories; registered NGS/PBP/profile blocks only where qualified. Legacy/current-vintage seven-day reconstruction remains distinct from authentic observation clocks. Each exact source procedure keeps its training/update/preprocessing/role/fallback binding; no final participation or target-game workload defines a pregame query.',
            fixed_numerical_reference_slots=numerical,named_actual_line_panel_records=panels,
            additional_retained_experiment_records=latest,main_lesson_and_limit=lessons,
            source_scoped_research_decision=decision.get('research_recommendation',decision.get('decision')),
            source_scoped_operational_decision=decision.get('website_operational_decision','SOURCE_LINKED'),
            current_status_warning='These are existing source-scoped decisions, not a new global championship or current served-value check. Root consolidates newer owner contributions separately.',
            five_week_status=decision.get('five_week_status','SOURCE_LINKED'),
            current_query_readiness=decision.get('current_query','SOURCE_LINKED'),
            actual_live_source=decision.get('actual_live_method','SOURCE_LINKED'),
            remaining_owner_action=decision.get('remaining_owner_action','SOURCE_LINKED'),
            next_distinct_question=next_hypothesis,next_question_authority='PROPOSED_ONLY_NOT_COMMISSIONED;source/novelty/resource gates explicitly retained'))
    report=dict(schema='C-CATEGORY-AUDIT-NARRATIVE-v1',recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        completeness='PARTIAL_WITHIN_RETAINED_SOURCE_VIEW;NEW_PEER_OWNER_HISTORY_PENDING_ROOT_INTAKE',
        purpose='Readable method/evidence audit from the existing registry, not a new database, evaluator, score calculation or fit.',
        sources=[binding(p) for p in [HISTORY,DECISIONS,OPPORTUNITY,'reports/CATEGORY_REGISTRY_V3.json']],
        categories=categories,old_strict_reproduction_failures='C1 and opportunity team-fit remain FAILED in their frozen scopes; other component passes are not full-fit parity.',
        catalog_gaps=history['limitations'],original_forecast_only_evidence=history.get('original_forecast_only_execution_reference'),
        new_fits=0,new_inference=0,new_grading=0,new_network=0,new_scored_weeks=0)
    (OUT/'CATEGORY_AUDIT.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    text=['# Category-by-category method and evidence audit','',
          '**This is a partial reporting audit of retained evidence, not new predictive progress.** It explains what the methods attempted and what the available records support. '+link(HISTORY,'The existing detailed method-history view')+' keeps every normalized exact ID/source linkage and explicit coverage-gap records. Root adds newer A/B/website owner contributions separately; this file does not claim their lifetime completeness or private fit parity.','',
          'The fixed numerical references below are the metadata-defined H-MULTI / E0_OP / ALL slots for the three original C law/CDF families, applied uniformly to each category. They were not picked for winning scores. Their numerical/synthetic-grid metrics are separate from actual offered-line records. All named source-panel records below remain non-additive: overlapping source/player-game/line records are never summed into a new result.','',
          'Inputs include ordinary historical statistics and qualified prior NGS/PBP/profile blocks. Historical reconstructed kickoff+seven-day availability is not an authenticated publication vintage. Training outcomes, transforms and priors must remain earlier-only; target-game actual workloads, final starters, future injuries and realized context are not inputs. Source support/missingness and learned/fallback behavior remain part of each exact procedure.','',
          '**Shared kernel guide.** Earlier-history/prior methods are simple point or event controls; Leaf estimates an empirical conditional response law; monotone HGB/logistic estimate threshold CDFs; absolute-loss HGB estimates a point; earlier-season sigmoid changes probability scale rather than football information. The exact mean, median, CDF/law, point crossing, selector and fallback remain different products. Profile/context, workload, pooling and distributional variants are explained in their category below.', '',
          '**Failure scope:** the old C1 and opportunity team-fit strict reproductions remain FAILED. A passing saved-row calculation, share fit, source check or different model is not a full-fit reproduction. Calibration, allocation, timing, unused-feature and used-but-zero-net-gain findings remain distinct. Low accuracy is not itself an arithmetic defect.','']
    for row in categories:
        cat=row['category'];text+=['## '+cat,'',
            '**Contract and population.** '+str(row['scoring_contract'])+'; registered roles '+', '.join(row['eligible_roles'])+'. Actual eligibility, participation and offer tier stay source-specific.','',
            '**Mechanisms and why they were tried.**']
        common={'HGB absolute-loss point forecast','Empirical Leaf response law','Histogram boosting threshold/direct procedure','Regularized logistic threshold CDF','Earlier-season sigmoid calibration','Constant-side control','Earlier-only prevalence','Earlier-history point reference'}
        core=[m['name'] for m in row['what_was_actually_tested'] if m['owner']=='C' and m['name'] in common]
        if core:text+=['- **C shared controls/kernels:** '+', '.join(core)+'. Numerical/grid execution and exact-line evidence are separated below; exact variants/stages remain in the JSON.']
        for owner in ['A','B','website','control']:
            group=[m for m in row['what_was_actually_tested'] if m['owner']==owner]
            if group:text+=['- **'+owner+' retained method labels:** '+ '; '.join(m['name'].replace('Owner-labelled mechanism — ','') for m in group)+'. These are source-owned records, not newly reproduced kernels or a pooled ranking.']
        for m in row['what_was_actually_tested']:
            if m['owner']=='C' and m['name'] not in common:
                text+=['- **C — '+m['name'].replace('Owner-labelled mechanism — ','')+'**: '+m['relationship_and_reason']]
        text+=['','**Fixed numerical / synthetic-grid reference records.** These are not O/U wins on actual offers.','',
               '| Exact source family/history/input | Outcomes / games / weeks | Median MAE | Mean MSE | Grid Brier / log loss |',
               '| --- | --- | --- | --- | --- |']
        for n in row['fixed_numerical_reference_slots']:
            r=n['record'];text.append('| '+r['family']+' / '+r['history']+' / '+r['arm']+' | '+str(r.get('outcomes','N/A'))+' / '+str(r.get('games','N/A'))+' / '+str(r.get('weeks','N/A'))+' | '+short_metric(r.get('median_mae'))+' | '+short_metric(r.get('mean_mse'))+' | '+short_metric(r.get('grid_brier'))+' / '+short_metric(r.get('grid_logloss'))+' |')
        if not row['fixed_numerical_reference_slots']:text.append('| No compatible retained fixed slot | N/A | N/A | N/A | N/A |')
        text+=['','**Named source panels.** Actual offered lines and mixed/reference diagnostics are labelled separately; these overlapping records are not a pooled ranking or authenticated original issuance.','',
               '| Named panel / procedure | Period / evidence qualification | Own Over W–L / N / rate | Own Under W–L / N / rate | Own combined W–L / N / rate |',
               '| --- | --- | --- | --- | --- |']
        for p in row['named_actual_line_panel_records']:
            own=p['own_sides'];name=p['panel_id']+' / '+p['procedure_id'].split('::')[-1]
            qualification='Mixed: realW1–5; W6–7reference' if 'ARCHIVED_W1_W7' in p['panel_id'] else 'Source diagnostic; exactweeks/tier inJSON'
            if any(k in (p['panel_id']+' '+str(p['evidence_tier'])).upper() for k in ['REFERENCE_THRESHOLD','INTERNAL_THRESHOLD','SYNTHETIC_THRESHOLD']):qualification='Reference/internal threshold; notactualofferqualification'
            text.append('| '+name.replace('|','/')+' | '+qualification+' | '+record_string(own.get('OVER'))+' | '+record_string(own.get('UNDER'))+' | '+record_string(own.get('COMBINED'))+' |')
        if not row['named_actual_line_panel_records']:text.append('| No qualified matching offered-line record retained | Missingactualoffer/contract | N/A | N/A | N/A |')
        text+=['','Full coverage, true weeks, same-offered-row numerical metrics, matched controls/disagreements/uncertainty and evidence tier for each of these source panels are retained in the '+link('reports/information-skill-01/completion-and-history-03/CATEGORY_AUDIT.json','matching JSON')+' and '+link(DECISIONS,'original category decision record')+'. An empty or unsupported side stays N/A; no equal-weight averaging or hindsight side splicing occurs.']
        if cat in ['pass_att','pass_cmp']:
            text+=['','**Distinct retained opportunity-v1 outputs, W5–9 only** (142 cases/target; 71 games; zero selected unknown/unavailable; one parent fallback/arm; unverified clocks/unclassified line tier). The separate W1–4 handoff must not borrow SKILL84 grades.','',
                   '| Exact procedure/output | Own Over | Own Under | Own combined |','| --- | --- | --- | --- |']
            for r in row['additional_retained_experiment_records']:
                o=r['own_sides'];text.append('| '+r['exact_procedure_output']+' | '+record_string(o['OVER'])+' | '+record_string(o['UNDER'])+' | '+record_string(o['COMBINED'])+' |')
        if cat=='rec':
            text+=['','**Completed C passer-mixture test.** C0/C1/C2 each score155–113/268: Over38–22 and Under117–91; W2:74–58/132, W3:81–55/136. Brier0.2641086577930243 and log loss0.728988341457127 match on those decided rows. C0 has272available/4selectedunknown/23technicalunavailable on295offers; C1/C2 have295available/27selectedunknown, no fallback. The scalar and its missing flag have0splits. This is no incremental direction/probability value under the fixed learner, not proof every dyad representation fails. Own-list results remain separately linked in the original pilot table; identical paired directions do not establish identical selection ability.']
        text+=['','**What the evidence says.** '+row['main_lesson_and_limit'],'',
               '**Support, failures and decision.** Retain '+str(row['source_scoped_research_decision'])+' at its source scope; operational retention is separate. The existing source contender’s duration status is '+str(row['five_week_status'].get('status','SOURCE_LINKED') if isinstance(row['five_week_status'],dict) else row['five_week_status']).replace('_',' ')+'. This does not transfer to newer pilots. Exact remaining owner action: '+str(row['remaining_owner_action'])+'. Current native-feed/consumer/served admission is separate; this audit grants no primary switch.','',
               '**Credible next question / gate—not a commissioned fit.** '+row['next_distinct_question'],'']
    text+=['## Completeness and use','',
           'This audit uses the existing C633 normalized view, retained original score/configuration records, named category-panel aggregates and prior opportunity-v1 owner summaries. It does not recover private chats/archives, prove unlocated Astra equivalence, infer that absent catalog entries were never tested, or create a new master ranking. The full source-specific original/corrected/admission trail remains linked in the history view. Newer owner-verified contributions are a root-intake dependency, not a reason to delay authorized pilots or eligible releases.','',
           'Any next fit requires the exact nearest prior procedure, material information/relationship difference, qualified earlier fields/denominators/clocks, fixed controls and finite owner allocation. None of the next-question paragraphs authorizes execution. Missing personnel/routes/prices/actual offers are specific source gates, not evidence that all such mechanisms were disproved. Five scored product weeks remain necessary for a new primary product; numerical, probability, direction and complete Top Picks cannot borrow one another’s duration.','']
    (OUT/'CATEGORY_AUDIT.md').write_text('\n'.join(text))
    receipt=dict(status='AUDIT_FROM_RETAINED_EVIDENCE_ONLY',categories=len(categories),
        actual_script_process_CPU_seconds=time.process_time(),prior_metadata_normalization_script_CPU_seconds=[0.408124666,0.462066251,0.709022035],conservative_total_reporting_CPU_charge=6,
        allocated_reporting_CPU_cap=6,pilot_or_scientific_reserve_used=0,
        measurement_limit='Script CPU plus bounded read/schema/preparation/retention bookkeeping; not an independent complete process/tool certificate.',
        no_new_fits=True,no_grader_or_rescoring=True,no_network=True,
        outputs={p.name:dict(bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [OUT/'CATEGORY_AUDIT.md',OUT/'CATEGORY_AUDIT.json']})
    (OUT/'CATEGORY_AUDIT_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert time.process_time()<3.5,'CATEGORY_AUDIT_PROCESS_CPU_LIMIT'
    print(json.dumps(receipt))


if __name__=='__main__':main()
