"""One append-only reporting view of retained outputs; no fitting or grading."""
import csv,gzip,hashlib,io,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
D=Path(__file__).resolve().parent
P=D/'pilot'
REL=D.relative_to(ROOT).as_posix()
def read(p):
    p=Path(p)
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def write(p,x):
    Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def bind(p):
    p=Path(p);b=p.read_bytes()
    return dict(path=p.relative_to(ROOT).as_posix(),bytes=len(b),SHA256=hashlib.sha256(b).hexdigest())

def main():
    results=read(P/'scores/RESULTS.json.gz')['rows']
    actual=[x for x in results if x['arm'] in ['C0_SAVED_P3','C1_SUPPORT','C2_VALUE']]
    old=ROOT/'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V10.csv.gz'
    new=old.with_name('W1_W9_AND_HISTORY_COVERAGE_V11.csv.gz')
    raw=gzip.decompress(old.read_bytes());header=next(csv.reader(io.StringIO(raw.decode())))
    extra=[]
    for arm in ['C0_SAVED_P3','C1_SUPPORT','C2_VALUE']:
        for w in list(range(1,10))+['ALL']:
            x=next((x for x in actual if x['arm']==arm and x['week']==w),None)
            r={k:'' for k in header}
            r.update(row_id=hashlib.sha256(f'C_DYAD_V2|{arm}|{w}'.encode()).hexdigest(),owner='C',category='rec',procedure_id='C-DYAD-MIX-VALUE-01/v2::'+arm,
                product='LAW_DIRECTION_AND_EXACT_LINE_EVENT_PROBABILITY',history='UNCHANGED_PARENT_PLUS_REGISTERED_LAST8_DYAD_PROXY;STRICT_7DAY',role_scope='WR_TE_NATIVE_PANEL',
                source_panel='NATIVE_REC_295_W2_W3',book='RETAINED_SOURCE_BOOK_PER_OFFER;NO_HOMOGENEOUS_BOOK_CLAIM',evidence_tier='TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC',
                season='2026',week=str(w),status='COMPLETED_NO_INCREMENTAL_GAIN_RESEARCH_SHADOW' if x else 'MISSING_REAL_LINE_FOR_THIS_PROCEDURE',
                source_artifacts=REL+'/pilot/scores/RESULTS.json.gz',verification_limit='W2C2 independent numeric fit; all590 C1C2 manualgrade/probability arithmetic; no authentic historical-vintage or quoteclock proof',
                source_evidence_class='RETAINED_REAL_LINES_UNKNOWN_QUOTE_CLOCK_AND_MAINNESS',new_procedure_coverage_not_new_games='TRUE',
                required_next_owner_action='C retain exact negative result; missing offers need permitted exact-procedure join under separate authority; no primary promotion',
                coverage_entry_id='EXECUTION_AUTHORIZATION_02',row_kind='C_DYAD_FROZEN_PROCEDURE_COVERAGE',grading_version='ADOPTED_CORRECTED_GRADER;ORIGINALS_UNCHANGED',issuance_state='CURRENT_VINTAGE_CHRONOLOGICAL_RECONSTRUCTION_EXPOSED')
            if x:
                r.update(eligible=x['eligible'],available=x['eligible']-x['unavailable'],selected=x['COMBINED']['selected'],scored=x['COMBINED']['decided'],unknown=x['unknown'],abstained=x['abstentions'],fallback=x['fallback_selected'],games=x['games'],player_games=x['player_games'])
                for side in ['over','under']:
                    q=x[side.upper()]
                    for k in ['wins','losses','decided','rate']:r[side+'_'+k]=q.get(k)
                for k in ['wins','losses','decided','rate']:r['combined_'+k]=x['COMBINED'].get(k)
                r['additional_metrics']=json.dumps(dict(probability_quality={k:x['probability_quality'].get(k) for k in ['probability_scored','Brier_half_multiclass','log_loss']},actual_weeks=[2,3],missing_weeks=[1,4,5,6,7,8,9],new_NFL_games=0),separators=(',',':'))
            extra.append(r)
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=header);writer.writerows(extra)
    wire=raw+buf.getvalue().encode();assert wire.startswith(raw)
    if new.exists():assert gzip.decompress(new.read_bytes())==wire,'DO_NOT_OVERWRITE_DIFFERENT_V11'
    else:new.write_bytes(gzip.compress(wire,mtime=0))
    write(D/'COVERAGE_APPEND.json',dict(previous=bind(old),current=bind(new),previous_decoded_bytes=len(raw),previous_decoded_prefix_preserved=True,added_rows=len(extra),actual_new_procedure_offer_weeks=[2,3],new_games_observed=0,missing_offer_weeks=[1,4,5,6,7,8,9]))
    queue=[
      dict(id='A_FROZEN_C_M3_RECOVERY',executor='A registered protected-join owner',artifact='Existing seven-body immutable recovery manifest and approved durable cache',action='Reuse admitted local bodies else at most seven exact rereads under cumulative39; verify hash/length and reopen; prove full CPU1660/wall2250/reserves fit; raw grades before summaries',completion='Durable recovered bytes plus new raw-grade receipt or measured safe stop',dependency='A current exact private ledger, source/cache permissions; grant creates no retries'),
      dict(id='B_TABICLV2',executor='B registered pilot owner',artifact='3a169a8bb39cc45f4f1dead0f2c9b18166ae3437 frozen proposal/request; publication7350a9b',action='Execute expressly approved exact safe/runtime-qualified canary and cost-projected frozen pilot under600CPU/1200wall',completion='Owner-published learned/fallback separate result or exact measured runtime/security stop',dependency='No runtime result received by C; no C lease or model download'),
      dict(id='OWNER_HISTORY',executor='A/B/original-website owners for their own histories; C intake',artifact=REL+'/intake/METHOD_HISTORY_RELAY_MESSAGES.json',action='Use precise unsent relay contribution requests through existing routes, retain PARTIAL catalog now',completion='Immutable owner-verified family/procedure/execution contributions actually retrieved and scoped',dependency='Cross-chat delivery/control unavailable; no private transcript/archives assumed'),
      dict(id='OPPORTUNITY_EARLY',executor='A registered owner-local join; B exact output supplier',artifact='opportunity-v1 exact OPP_BASE/OPP_MEAN/OPP_JOINT/DIRECT_ATT typed early outputs',action='Supply exact handoff/source qualification and separate task allocation; reuse saved outputs only',completion='Exact-product early grades and permitted independent review',dependency='Not funded by frozen C M3 or C dyad; SKILL84 is a different completed join'),
      dict(id='PERSONNEL_AND_M4',executor='Existing A/C personnel source owners; B independent-price owner',artifact='Authenticated vintage/event-effective teammate universe; exact contemporaneous independent price pair respectively',action='Preserve source-blocked dispositions and existing prospective capture; no repeated closed search',completion='Genuinely new qualifying source contract before a separately registered fit',dependency='Historical authenticity/universe and independent quote access remain absent'),
      dict(id='COUNT_A_DELIVERY',executor='Existing authorized connection owner, registered A producer, original-site consumer',artifact='Fresh readable corrected-mean feed and upload authorization/readback receipt',action='Resolve actual connection authorization without secrets/bypass; produce durable corrected point mean with once-only corrector; website retrieves/admit/served-verifies',completion='Source/issue/hash/run/feed retrieval and exact consumer/served receipt',dependency='No new fresh feed verified; normal code merge cannot itself resolve401'),
      dict(id='FUTURE_AND_HISTORY',executor='Existing capture/history owners; C common intake',artifact='Qualified original future offers/forecasts and exact missing historical source cells',action='Continue already-authorized jobs and supported2022–25/missing2026 periods; preserve original clocks and unknowns',completion='New real scored periods or genuine later frozen decisions/grades',dependency='No new collector/scheduler, backdating, nine-week/all-category release gate')]
    write(D/'FINITE_QUEUE.json',dict(state='FINITE_EXISTING_OWNER_QUEUE;NO_NEW_SEARCH_COMMISSIONED',tasks=queue))
    write(D/'RESOURCE_CLOSURE.json',dict(pilot=bind(P/'LEDGER.json'),caps=dict(CPU=120,wall=300,fit_attempts=5,RSS=1288490188,new_public_bytes=33554432,whole_C_bytes=2684354560,raw_GETs=0),reporting=dict(previous600CPU_charge=555.35995406,initial_plan_charge=40,conservative_this_package_charge=44,final_cumulative_charge=599.35995406,remaining=0.64004594,parts=dict(initial_catalog=12,quality_followup=2,peer_intake=6,pilot_catalog_result_intake=2,independent_metadata_review=1,root_reporting_metadata_validation_retention=21),no_pilot_reserve_used=True,metering_limit='Conservative bounded reporting charges; not complete assistant/tool orchestration timing certificate'),preserves_all_failures=True,no_budget_transfer=True))
    admission_path=ROOT/'reports/abc-championship/ADMISSION_LEDGER.json'
    a=read(admission_path)
    record=dict(id='EXECUTION-AUTHORIZATION-02',state='C_FROZEN_PILOT_EXECUTED_NO_GAIN;PEER_AUTHORIZATION_AND_LAST_RECEIPTS_RECONCILED;PARTIAL_HISTORY',report=bind(D/'README.md'),result=bind(P/'EXECUTED_RESULT.json'),history=bind(D/'method-history/METHOD_HISTORY.json.gz'),coverage=bind(new),verification=bind(D/'verification/independent-fit/RESULT.json'),independent_raw_aggregate=bind(D/'verification/independent-fit/AGGREGATE_CHECK.json'),A=bind(D/'intake/A_RECEIPT.json'),B=bind(D/'intake/B_RECEIPT.json'),website=bind(D/'intake/WEBSITE_RECEIPT.json'),admitted_scope='C exact W2/W3 retained-line diagnostic and independent representative fit/all-new-row arithmetic; peers public receipt scope only, no private fit/row access',primary_promotion=False,live_research_activation=False,publication='C checked branch retention; final PR/readback receipt separate',old_failed_reproductions='B C1 and opportunity team-fit remain FAILED; no scope transfer')
    a['execution_authorization_02']=record;write(admission_path,a)
    tasks_path=ROOT/'reports/abc-championship/TASK_LEDGER.json';tasks=read(tasks_path)
    updates={
      'C_DYAD_MIX_VALUE_01':dict(state='EXECUTED_FROZEN;C1_C2_TIE_C0;NO_INCREMENTAL_VALUE;RESEARCH_SHADOW_NO_PRIMARY',artifact=REL+'/pilot/EXECUTED_RESULT.json',next_action='Retain raw outputs/negative result; no repeat tracing, retuning or primary activation',budget='Dedicated120CPU/300wall/5fits; actual ledger linked in execution_authorization_02; no budget transfer'),
      'A_FROZEN_C_M3_OWNER_LOCAL_JOIN':dict(state='OWNER_REPORTED_FIXTURE_PASS;SEVEN_INPUT_BODIES_MISSING_AT_RETRIEVED_STOP;RECOVERY39_AUTHORIZED_ONCE;NO_NEW_GRADES_RECEIVED',artifact=REL+'/intake/A_RECEIPT.json',next_action=queue[0]['action'],budget=dict(CPU_cap=1660,wall_cap=2250,source_read_cumulative_cap=39,incremental_reads_once=7,expected_seven_body_bytes=9643639,retention_CPU_reserve=120,reporting_CPU_reserve=20,actual_current_charge='Owner exact private ledger; reference1169.146 is not reset permission',no_transfer=True))}
    for t in tasks:
        if t.get('task_id') in updates:t.update(updates[t['task_id']])
    for ident,owner,state,artifact,action in [
      ('B_TABICLV2_CMP_DIRECT_PILOT_V1','B','APPROVED_ONCE;PREEXECUTION_PUBLIC_RECEIPT_RETRIEVED;RUNTIME_RESULT_NOT_VERIFIED',REL+'/intake/B_RECEIPT.json',queue[1]['action']),
      ('C_RECOVERABLE_METHOD_HISTORY','C coordinator; owner contributions retain actual owners','PARTIAL_47_FAMILY_GROUPS_633_PROCEDURES_WITH_EXPLICIT_GAPS',REL+'/method-history/README.md','Retrieve actual owner contributions through permitted routes; do not delay ready pilots or claim full lifetime access'),
      ('C_EXECUTION_AUTHORIZATION_02','C','EXECUTED_C_PILOT_AND_SCOPED_INTAKE;NORMAL_PUBLICATION',REL+'/README.md','Complete C checked retention/readback; no original-site changes')]:
        newtask=dict(task_id=ident,owner=owner,state=state,artifact=artifact,next_action=action)
        oldtask=next((t for t in tasks if t.get('task_id')==ident),None)
        if oldtask:oldtask.update(newtask)
        else:tasks.append(newtask)
    write(tasks_path,tasks)
    cp_path=ROOT/'reports/abc-championship/CURRENT_PROTOCOL.json';cp=read(cp_path)
    cp['execution_authorization_02']=dict(**record,task_queue=bind(D/'FINITE_QUEUE.json'),resource=bind(D/'RESOURCE_CLOSURE.json'),actual_new_offer_weeks=[2,3],new_NFL_observations=0,method_history_markdown=bind(D/'method-history/README.md'),method_history_CSV=bind(D/'method-history/PROCEDURES.csv.gz'))
    cp['predictive_value_next_01']['stage']='HISTORICAL_PREAUTHORIZATION_SNAPSHOT;SUPERSEDED_BY_EXECUTION_AUTHORIZATION_02'
    cp['predictive_value_next_01']['proposal_request']['state']='HISTORICAL_REQUEST;GRANTED_ONCE_AND_EXECUTED_UNDER_EXECUTION_AUTHORIZATION_02'
    cp['admission']=bind(admission_path);cp['tasks']=bind(tasks_path);write(cp_path,cp)
    epath=ROOT/'reports/abc-championship/EXPORT_INDEX.json';e=read(epath)
    e['execution_authorization_02']=cp['execution_authorization_02'];e['current_execution_report']=bind(D/'README.md')
    e['current_shared_intake_report']=bind(D/'README.md');e['common_protocol']=bind(cp_path);write(epath,e)
    print(json.dumps(dict(coverage_added_rows=len(extra),coverage=bind(new),catalog=bind(D/'method-history/METHOD_HISTORY.json.gz'))))

if __name__=='__main__':main()
