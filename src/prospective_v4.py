"""Manual/on-demand future inference, durable receipt validation and grading.

Future player rows contain no actual outcome or realized participation field.
Numeric model JSON is safe to restore without downloaded-pickle execution.
"""
import argparse,gzip,hashlib,json,math,os,resource,time,subprocess
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from contracts_v2 import CATEGORIES,CHART,WEIGHTS,SIGNED,integer,grade,probs
from data_v2 import load as load_history,History,vector
from laws_v2 import LeafModel
from safe_models_v4 import export_forest,infer_forest,law_data,law_load,save,load as load_numeric,validate_training_model
from forward_sources_v4 import now,stamp,digest,scoreboard_projection,match_event,write
from forward_budget_v4 import ForwardBudget

POLICY=Path('protocol/PROSPECTIVE_V4.json')
CODE=['prospective_v4.py','forward_sources_v4.py','forward_budget_v4.py','safe_models_v4.py','laws_v2.py','data_v2.py','contracts_v2.py']
def filehash(p):return digest(Path(p).read_bytes())
def read_json(p):return json.loads(Path(p).read_text())
def pack(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(gzip.compress(json.dumps(value,separators=(',',':'),allow_nan=False).encode(),mtime=0))
def unpack(path):return json.loads(gzip.decompress(Path(path).read_bytes()))
def finite(values):return [float(v) if np.isfinite(v) else None for v in values]

class ObservedHistory(History):
    def __init__(self,rows,key,cutoff):
        q=rows[(rows.kickoff<cutoff)&rows.game_id.isin(set(rows.attrs.get('completed_game_ids',rows.game_id)))].copy();q['available']=q.kickoff
        super().__init__(q,key);self.cutoff=cutoff
    def before(self,key,cutoff,n=8):return super().before(key,min(cutoff,self.cutoff),n)

def validate_snapshot(source,asof):
    m=read_json(source/'SOURCE_MANIFEST.json')
    for name,info in m['files'].items():assert filehash(source/name)==info['SHA256'],'SOURCE_BYTES_CHANGED:'+name
    times=[pd.Timestamp(r['observed_UTC']).timestamp() for r in m['sources']]
    assert max(times)<=asof,'SOURCE_FROM_FUTURE'
    from email.utils import parsedate_to_datetime
    for r in m['sources']:
        if r['id'] in ['roster','injuries']:
            published=parsedate_to_datetime(r['HTTP_Last_Modified']).timestamp()
            assert 0<=asof-published<=36*3600,'CURRENT_ROSTER_OR_INJURY_STALE'
    assert not m.get('missing_team_coverage',[]),'INCOMPLETE_CURRENT_TEAM_ROSTER_COVERAGE'
    events=read_json(source/'events.json');roster=read_json(source/'roster.json');injuries=read_json(source/'injuries.json')
    assert len(events)==m['events'] and len({e['game_id'] for e in events})==len(events)
    teams={t for e in events for t in [e['home_team'],e['away_team']]}
    assert all(e['season']==m['season'] and e['week']==m['week'] and e['season_type']==2 for e in events)
    assert len({r['gsis_id'] for r in roster})==len(roster) and all(r['gsis_id'] and r['team'] in teams and r['season']==m['season'] and r['week']==m['week'] and r['position'] in ['QB','RB','WR','TE'] for r in roster)
    assert all(r['season']==m['season'] and r['week']==m['week'] for r in injuries)
    return m

def current_event_check(events):
    from urllib.request import Request,urlopen
    dates=sorted({e['gameday'] for e in events});items=[];sources=[]
    for day in dates:
        url='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates='+day.replace('-','')+'&limit=100'
        with urlopen(Request(url,headers={'Cache-Control':'no-cache','Accept-Encoding':'identity','User-Agent':'C-pregame-status-check-v4'}),timeout=30) as r:b=r.read(2*1024*1024);headers={k.lower():v for k,v in r.headers.items()}
        assert 0<=int(headers.get('age') or 0)<=1800,'STALE_STATUS_HTTP_CACHE'
        observed=stamp();source='PUBLISH_STATUS_'+day;items+=scoreboard_projection(json.loads(b),source,observed);sources.append(dict(url=url,observed_UTC=observed,raw_SHA256=digest(b),HTTP_Date=headers.get('date'),HTTP_Age=headers.get('age')))
    index={r['espn_event_id']:r for r in items};t=now().timestamp();kept=[];rejected=[]
    for e in events:
        r=index.get(e['espn_event_id'])
        if r is None:rejected.append(dict(game_id=e['game_id'],reason='CURRENT_STATUS_UNAVAILABLE'));continue
        pseudo=dict(e,espn=e['espn_event_id'])
        try:okay=match_event(pseudo,r,t)
        except AssertionError:okay=False
        if okay and r['kickoff']>t+300:kept.append(dict(e,**{k:r[k] for k in ['state','status_name','completed','observed_UTC','source_id']}))
        else:rejected.append(dict(game_id=e['game_id'],reason='STARTED_COMPLETED_CHANGED_OR_TOO_CLOSE'))
    return kept,dict(created_UTC=stamp(),sources=sources,facts=items,rejected=rejected)

def features_for_future(history,teams,candidate,target,arm,cutoff):
    # Restrict data at capture cutoff BEFORE using the known future kickoff for ages.
    p=ObservedHistory(history,'player_id',cutoff);t=ObservedHistory(teams,'team',cutoff)
    return vector(candidate,target,p,t,arm)

def qualified_training_frame(data,completed,cutoff):
    return data[data.game_id.isin(set(completed))&data.game_final&(data.kickoff<cutoff)].sort_values(['kickoff','game_id','player_id'])

def issue(source,out,cache,run_id,roots,categories=None):
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('COMMIT_POLICY_AND_CODE_BEFORE_ISSUANCE')
    with ForwardBudget(cache/'BUDGET.json',out,roots,read_json(POLICY)['budget']) as budget:
        return issue_wave(source,out,cache,run_id,budget,categories)

def issue_wave(source,out,cache,run_id,budget,categories=None):
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('COMMIT_POLICY_AND_CODE_BEFORE_ISSUANCE')
    policy=read_json(POLICY);start=time.monotonic();cpu=time.process_time();asof=now().timestamp();m=validate_snapshot(source,asof)
    events,status=current_event_check(read_json(source/'events.json'))
    if not events:raise RuntimeError('NO_VERIFIED_FUTURE_EVENTS')
    if out.exists():raise FileExistsError('Immutable run already exists')
    out.mkdir(parents=True);cache.mkdir(parents=True,exist_ok=True)
    roster=read_json(source/'roster.json');injuries=read_json(source/'injuries.json');inj={(r['gsis_id'],r['team']):r for r in injuries if r['gsis_id']}
    candidates=[];exclusions=[]
    for event in events:
        for r in roster:
            if r['team'] not in [event['home_team'],event['away_team']]:continue
            if r['status']!='ACT':exclusions.append(dict(game_id=event['game_id'],player_id=r['gsis_id'],reason='CURRENT_ROSTER_'+str(r['status'])));continue
            injury=inj.get((r['gsis_id'],r['team']),{});designation=injury.get('report_status') or 'UNKNOWN_NOT_LISTED_OR_BLANK'
            candidates.append(dict(game_id=event['game_id'],event_version=event['event_version'],espn_event_id=event['espn_event_id'],season=m['season'],week=m['week'],player_id=r['gsis_id'],name=r['full_name'],position=r['position'],team=r['team'],opponent_team=event['away_team'] if r['team']==event['home_team'] else event['home_team'],home_team=event['home_team'],kickoff=event['kickoff'],kickoff_UTC=event['kickoff_UTC'],roster_status=r['status'],availability=designation,practice_status=injury.get('practice_status') or 'UNKNOWN',starter_state='NOT_INFERRED_FROM_POSITION',selection_availability='BLOCKED_OUT' if str(designation).lower() in ['out','doubtful'] else 'CONDITIONAL_UNKNOWN_APPEARANCE'))
    assert len({(r['game_id'],r['player_id']) for r in candidates})==len(candidates)
    d,g,teams=load_history(source);completed=set(m['completed_game_ids']);d=qualified_training_frame(d,completed,asof);teams=teams[teams.game_id.isin(completed)&(teams.kickoff<asof)].copy()
    records=d.to_dict('records');hist,th=History(d,'player_id'),History(teams,'team');observed_hist,observed_team=ObservedHistory(d,'player_id',asof),ObservedHistory(teams,'team',asof)
    code={n:filehash(Path('src')/n) for n in CODE};policy_hash=filehash(POLICY);commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    rows=[];models=[];fit_count=0;unavailable=[]
    requested=list(CATEGORIES) if categories is None else categories
    assert requested and len(requested)==len(set(requested)) and set(requested)<=set(CATEGORIES)
    for target in requested:
        arm=policy['primary']['arms'][target];kind,scale,roles=CATEGORIES[target][2:5]
        pool=[r for r in records if r['position'] in (['QB','RB','WR','TE'] if target in ['rush_yd','rush_att','rush_rec_yd'] else roles) and r['values'][target] is not None]
        query=[r for r in candidates if r['position'] in roles]
        if not query or len(pool)<60:
            unavailable.append(dict(category=target,reason='NO_QUALIFIED_CANDIDATES' if not query else 'INSUFFICIENT_QUALIFIED_LEAGUE_TRAINING',candidate_count=len(query),training_rows=len(pool)));continue
        x=np.asarray([vector(r,target,hist,th,arm) for r in pool],float);y=np.rint([r['values'][target]*scale for r in pool]);pr=np.asarray([r['position'] for r in pool])
        qx=np.asarray([vector(r,target,observed_hist,observed_team,arm) for r in query],float)
        # A display/grading/receipt-only change must not force an identical fit.
        modelcode={n:code[n] for n in ['laws_v2.py','data_v2.py','contracts_v2.py']}
        key=digest(x.tobytes()+y.tobytes()+json.dumps(pr.tolist()).encode()+json.dumps(dict(target=target,code=modelcode,family='P2_LEAF_32_8_30_1701_PRIOR05',arm=arm),sort_keys=True).encode());modelpath=cache/(target+'-'+key+'.json.gz');metapath=cache/(target+'-'+key+'.meta.json')
        recovery=None
        if modelpath.exists() and not metapath.exists():
            assert any(r['target']==target and r['key']==key for r in budget.state['fit_attempts']),'UNREGISTERED_ORPHAN_MODEL'
            numeric=load_numeric(modelpath,filehash(modelpath));recovery=validate_training_model(numeric,x,y,pr)
            meta=dict(target=target,model_SHA256=filehash(modelpath),model_key=key,training_rows=len(pool),training_through_UTC=pd.Timestamp(max(r['kickoff'] for r in pool),unit='s',tz='UTC').isoformat(),features=len(x[0]),arm=arm,history='H-MULTI_2022_PLUS_VERIFIED_COMPLETED',policy_SHA256=policy_hash,code_SHA256=code,created_UTC=stamp(),fit_information_cutoff_UTC=None,revalidated_information_cutoff_UTC=pd.Timestamp(asof,unit='s',tz='UTC').isoformat(),original_fit_code_commit='cf2526b1bc011955d59d367ad1cc64f1ecb853dc',original_fit_clock='Not retained before validator failure; no issuance claimed',recovery=recovery,numeric_export_parity_queries=None,training_label_qualification='OFFICIAL_SUPPORTED_PLAYED_STATS')
            write(metapath,meta)
        if modelpath.exists():meta=read_json(metapath);numeric=load_numeric(modelpath,meta['model_SHA256']);reused=True
        else:
            if fit_count>=12:raise RuntimeError('FIT_CAP')
            if len(pool)<60:raise RuntimeError('INSUFFICIENT_QUALIFIED_LEAGUE_TRAINING_'+target)
            budget.reserve(target,key)
            with threadpool_limits(limits=1):model=LeafModel(kind,scale).fit(x,y,pr)
            fit_count+=1;numeric=export_forest(model);modelhash=save(modelpath,numeric)
            # Safe numeric traversal must match the in-memory newly fitted model.
            with threadpool_limits(limits=1):reference=model.laws(qx,[r['position'] for r in query])
            restored=infer_forest(numeric,qx,[r['position'] for r in query])
            for a,b in zip(reference,restored):assert a.mean()==b.mean() and a.quantile(.5)==b.quantile(.5) and a.v.tolist()==b.v.tolist() and a.w.tolist()==b.w.tolist(),'NUMERIC_EXPORT_INFERENCE_MISMATCH'
            meta=dict(target=target,model_SHA256=modelhash,model_key=key,training_rows=len(pool),training_through_UTC=pd.Timestamp(max(r['kickoff'] for r in pool),unit='s',tz='UTC').isoformat(),features=len(x[0]),arm=arm,history='H-MULTI_2022_PLUS_VERIFIED_COMPLETED',policy_SHA256=policy_hash,code_SHA256=code,created_UTC=stamp(),fit_information_cutoff_UTC=pd.Timestamp(asof,unit='s',tz='UTC').isoformat(),numeric_export_parity_queries=len(query),training_label_qualification='PARTIAL_RARE_ZERO_SUBSET' if target=='fpts' else 'OFFICIAL_SUPPORTED_PLAYED_STATS')
            write(metapath,meta);reused=False
        modeldest=out/'models'/f'{target}.json.gz';modeldest.parent.mkdir(exist_ok=True);modeldest.write_bytes(modelpath.read_bytes());write(modeldest.with_suffix('.meta.json'),meta)
        laws=infer_forest(numeric,qx,[r['position'] for r in query]);models.append(meta|dict(reused=reused,artifact='models/'+modeldest.name))
        for r,fv,law in zip(query,qx,laws):
            base={k:r[k] for k in ['game_id','event_version','espn_event_id','player_id','name','position','team','opponent_team','home_team','season','week','kickoff_UTC','roster_status','availability','practice_status','starter_state','selection_availability']};support=len(observed_hist.before(r['player_id'],asof))
            base.update(forecast_id=digest((run_id+r['game_id']+r['player_id']+target).encode())[:24],run_id=run_id,category=target,policy_id=policy['id'],policy_SHA256=policy_hash,model_id='C-FORWARD-P2-v4/'+target+'/'+key,model_SHA256=meta['model_SHA256'],family='P2_LEAF',arm=arm,information_cutoff_UTC=pd.Timestamp(asof,unit='s',tz='UTC').isoformat(),generated_UTC=stamp(),evidence_tier='LOCAL_GENERATED_AWAITING_SERVER_RECEIPT',product_type='EVENT_PROBABILITY' if kind=='event' else 'DISCRETE_OUTCOME_LAW',mean=None if kind=='event' else law.mean(),median=None if kind=='event' else law.quantile(.5),p05=None if kind=='event' else law.quantile(.05),p95=None if kind=='event' else law.quantile(.95),event_probability=law.probability(.5)['over'] if kind=='event' else None,scoring_contract_id=CHART if target=='fpts' else 'rush-or-rec-at-least-one-v1' if kind=='event' else 'official-player-fullgame-OT-v1',appearance_conditioning=policy['primary']['appearance_conditioning'],history_support=support,sparse_player=support<3,model_fallback=False,sparse_rule='Training-onlyimputation/missingindicators+rolepriorblend, no playerrowdrop',features=finite(fv),feature_schema='C-v2-'+arm+'-'+str(len(fv)),law=law_data(law),offer_state='NO_QUALIFIED_CURRENT_OFFER',selected_side=None,selection_state='UNAVAILABLE_NOT_ABSTENTION',readiness='EXPERIMENTAL_SHADOW_LABEL_COVERAGE' if target=='fpts' else 'PROVISIONAL_FORECAST_ONLY',limitation='Rarepositivechartlabels unqualified; not admitted fulltail or realoffer probability' if target=='fpts' else 'Exposedresearchprocedure; real-line accuracy not established; not a jointteamlaw')
            rows.append(base)
        print('FORWARD_MODEL',target,len(pool),len(query),'REUSED' if reused else 'FIT',flush=True)
        if time.process_time()-cpu>240 or time.monotonic()-start>600:raise RuntimeError('FORWARD_TIME_CAP')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>1073741824:raise RuntimeError('FORWARD_RSS_CAP')
        budget.check()
    # Revalidate status after fits; suppress anything that has started/changed.
    verified,finalcheck=current_event_check(events);allowed={r['game_id'] for r in verified};removed=[r['forecast_id'] for r in rows if r['game_id'] not in allowed];rows=[r for r in rows if r['game_id'] in allowed]
    if not rows:raise RuntimeError('NO_FUTURE_ROWS_AT_PUBLICATION_CHECK')
    pack(out/'forecasts.json.gz',rows);write(out/'candidates.json',candidates);write(out/'exclusions.json',exclusions);write(out/'status_at_generation.json',status);write(out/'status_before_persistence.json',finalcheck);write(out/'model_manifest.json',models)
    # Source snapshot bytes needed for restoration and prefix verification.
    sourceout=out/'sources';sourceout.mkdir()
    for p in source.iterdir():
        if p.is_file():(sourceout/p.name).write_bytes(p.read_bytes())
    manifest=dict(schema='C-PREGAME-RUN-v4',run_id=run_id,policy_id=policy['id'],policy_SHA256=policy_hash,code_commit=commit,code_SHA256=code,created_UTC=stamp(),information_cutoff_UTC=pd.Timestamp(asof,unit='s',tz='UTC').isoformat(),season=m['season'],week=m['week'],events=len(allowed),first_kickoff_UTC=min(r['kickoff_UTC'] for r in rows),candidate_players=len(candidates),forecast_rows=len(rows),categories=len({r['category'] for r in rows}),unavailable_categories=unavailable,primary_scoring_snapshot=policy['snapshot_policy']['id'],appearance_conditioning=policy['primary']['appearance_conditioning'],new_fits=fit_count,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,source_manifest_SHA256=filehash(source/'SOURCE_MANIFEST.json'),removed_started_or_changed_rows=removed,publication_state='AWAITING_GITHUB_SERVER_PROOF',real_offers=0,real_selections=0,six_leg_state='NO_QUALIFIED_SIX_LEG_ENTRY',predictive_improvement_demonstrated=False)
    budget.check();write(out/'RESOURCE_RECEIPT.json',dict(budget.state,active=False,snapshot='Resource usage at forecast generation; persistent budget continues across the registered pilot and remainder'))
    manifest['files']={p.relative_to(out).as_posix():dict(SHA256=filehash(p),bytes=p.stat().st_size) for p in out.rglob('*') if p.is_file()};write(out/'RUN.json',manifest);budget.check();print('CAPTURE_GENERATED',run_id,len(rows),manifest['first_kickoff_UTC']);return manifest

def validate_run(run,check_clock=False):
    m=read_json(run/'RUN.json')
    for name,info in m['files'].items():assert filehash(run/name)==info['SHA256'],'CAPTURE_BYTES_CHANGED:'+name
    rows=unpack(run/'forecasts.json.gz');assert len(rows)==m['forecast_rows'] and len({r['forecast_id'] for r in rows})==len(rows)
    snapshot=run/'sources';sm=validate_snapshot(snapshot,pd.Timestamp(m['information_cutoff_UTC']).timestamp())
    assert filehash(snapshot/'SOURCE_MANIFEST.json')==m['source_manifest_SHA256']
    roster={(r['gsis_id'],r['team']):r for r in read_json(snapshot/'roster.json')}
    modelmap={r['target']:r for r in read_json(run/'model_manifest.json')}
    for r in rows:
        assert 'actual' not in r and 'played' not in r and 'realized_starter' not in r
        assert pd.Timestamp(r['information_cutoff_UTC'])<=pd.Timestamp(r['generated_UTC'])<pd.Timestamp(r['kickoff_UTC'])
        law=law_load(r['law']);assert r['features'] and r['model_SHA256']
        assert roster[(r['player_id'],r['team'])]['status']=='ACT'
        assert modelmap[r['category']]['model_SHA256']==r['model_SHA256']
        if r['category']=='anytime_td':assert r['mean'] is None and r['median'] is None and r['event_probability']==law.probability(.5)['over']
        # BLAS reductions can differ in the last bits across supported machines.
        else:assert math.isclose(r['mean'],law.mean(),rel_tol=1e-12,abs_tol=1e-10) and r['median']==law.quantile(.5)
    if check_clock:assert now().timestamp()+300<min(pd.Timestamp(r['kickoff_UTC']).timestamp() for r in rows),'CAPTURE_SERVER_CHECK_TOO_LATE'
    return m,rows

def validate_receipt(run,receipt,m,rows):
    assert receipt['schema']=='C-SERVER-PREGAME-RECEIPT-v4' and receipt['qualified_prospective'] is True
    assert receipt['run_id']==m['run_id'] and receipt['forecast_blob_SHA256']==filehash(run/'forecasts.json.gz')
    assert receipt['run_manifest_SHA256']==filehash(run/'RUN.json')
    assert receipt['fresh_GitHub_bytes_verified'] is True and receipt['not_client_commit_dates'] is True
    created=pd.Timestamp(receipt['server_run_created_UTC']);started=pd.Timestamp(receipt['server_run_started_UTC']);completed=pd.Timestamp(receipt['server_check_completed_UTC'])
    assert created.tzinfo and started.tzinfo and completed.tzinfo and created<=started<=completed
    assert pd.Timestamp(m['created_UTC'])<=completed and all(completed+pd.Timedelta(seconds=300)<pd.Timestamp(r['kickoff_UTC']) for r in rows)
    return completed

def server_receipt(run,commit,workflow_run,output):
    m,rows=validate_run(run);repo='NickNicky19/NFL-forecasting-NGS-C'
    raw=subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{workflow_run}']);j=json.loads(raw)
    assert j['head_sha']==commit and j['event']=='pull_request' and j['status']=='completed' and j['conclusion']=='success' and j['path']=='.github/workflows/c-checks-pages.yml','NO_SUCCESSFUL_BOUND_SERVER_CHECK'
    jobs=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{workflow_run}/jobs']))['jobs'];check=next(r for r in jobs if r['name']=='checks');persisted=pd.Timestamp(check['completed_at'])
    assert check['conclusion']=='success' and any(s['name']=='Verify immutable prospective captures' and s['conclusion']=='success' for s in check['steps']),'NO_BOUND_FORECAST_VALIDATION_STEP'
    assert all(persisted+pd.Timedelta(seconds=300)<pd.Timestamp(r['kickoff_UTC']) for r in rows),'LATE_GITHUB_PERSISTENCE'
    relative=run.relative_to(Path.cwd()) if run.is_absolute() else run
    from urllib.request import urlopen
    url='https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+relative.as_posix()+'/forecasts.json.gz'
    b=urlopen(url,timeout=30).read();assert digest(b)==m['files']['forecasts.json.gz']['SHA256']
    manifest_url=url.rsplit('/',1)[0]+'/RUN.json';assert digest(urlopen(manifest_url,timeout=30).read())==filehash(run/'RUN.json'),'SERVER_RUN_CHAIN_MISMATCH'
    receipt=dict(schema='C-SERVER-PREGAME-RECEIPT-v4',run_id=m['run_id'],run_manifest_SHA256=filehash(run/'RUN.json'),capture_commit=commit,forecast_blob_SHA256=digest(b),forecast_bytes=len(b),server_workflow_run=workflow_run,server_run_created_UTC=j['created_at'],server_run_started_UTC=j['run_started_at'],server_check_completed_UTC=check['completed_at'],server_run_URL=j['html_url'],verified_UTC=stamp(),qualified_prospective=True,earliest_actual_lead_seconds=min((pd.Timestamp(r['kickoff_UTC'])-persisted).total_seconds() for r in rows),not_client_commit_dates=True,fresh_GitHub_bytes_verified=True,scoring_snapshot='FIRST_QUALIFIED_ON_DEMAND-v1')
    write(output,receipt);print('SERVER_PREGAME_RECEIPT',receipt['server_check_completed_UTC'],receipt['earliest_actual_lead_seconds']);return receipt

def grade_run(run,receipt_path,outcomes,output):
    m,rows=validate_run(run);receipt=read_json(receipt_path);validate_receipt(run,receipt,m,rows)
    first=first_qualified_snapshots(run.parent.parent)
    packet=read_json(outcomes);assert packet['schema']=='C-OUTCOMES-v4';lookup={(r['game_id'],r['player_id'],r['category']):r for r in packet['outcomes']};assert len(lookup)==len(packet['outcomes']),'DUPLICATE_OUTCOME_IDENTITIES';grades=[]
    for r in rows:
        key=(r['game_id'],r['player_id'],r['category'],r['policy_id'])
        if key in first and first[key][1]!=r['forecast_id']:
            grades.append(dict(forecast_id=r['forecast_id'],game_id=r['game_id'],player_id=r['player_id'],category=r['category'],state='NOT_PRIMARY_SCORING_SNAPSHOT',actual=None));continue
        a=lookup.get((r['game_id'],r['player_id'],r['category']));state='PENDING' if a is None else a['appearance']
        if a:
            assert a['scoring_contract_id']==r['scoring_contract_id']
            assert a['event_status']=='FINAL' and pd.Timestamp(r['kickoff_UTC'])<pd.Timestamp(a['observed_UTC'])<=pd.Timestamp(now())
            assert a['espn_event_id']==r['espn_event_id'],'OUTCOME_NATIVE_EVENT_MISMATCH'
            if a['kickoff_UTC']!=r['kickoff_UTC']:grades.append(dict(forecast_id=r['forecast_id'],state='EVENT_VERSION_RECONCILIATION_REQUIRED',actual=None));continue
            assert state in ['PLAYED','DNP','UNKNOWN','VOID','CANCELLED','PENDING']
        if state=='PLAYED' and a.get('actual') is not None:
            y=a['actual'];law=law_load(r['law']);error=None if r['mean'] is None else r['median']-y
            assert math.isfinite(y) and abs(y*law.scale-round(y*law.scale))<1e-8
            if CATEGORIES[r['category']][2]=='count':assert y>=0
            if r['category']=='anytime_td':assert y in [0,1]
            if r['category']=='fpts':
                components=a['score_components'];values={k:integer(components.get(k),k in SIGNED) for k in WEIGHTS};assert all(v is not None for v in values.values()) and abs(sum(WEIGHTS[k]*v for k,v in values.items())/50-y)<1e-10
                assert a.get('unique_event_credits_verified') is True,'UNQUALIFIED_CHART_CREDITS'
            nll=-law.logpmf(int(round(y*law.scale)))
            grades.append(dict(forecast_id=r['forecast_id'],game_id=r['game_id'],player_id=r['player_id'],category=r['category'],state='GRADED_PLAYED',actual=y,median_error=error,absolute_error=None if error is None else abs(error),mean_squared_error=None if r['mean'] is None else (r['mean']-y)**2,CRPS=law.crps(y),NLL=nll if math.isfinite(nll) else 'Infinity',offer_grade='NO_QUALIFIED_OFFER',book_settlement='UNVERIFIED'))
        else:grades.append(dict(forecast_id=r['forecast_id'],game_id=r['game_id'],player_id=r['player_id'],category=r['category'],state=state,actual=None,offer_grade='UNAVAILABLE',book_settlement='UNVERIFIED'))
    write(output,dict(schema='C-PROSPECTIVE-GRADING-v4',run_id=m['run_id'],created_UTC=stamp(),forecast_SHA256=receipt['forecast_blob_SHA256'],outcome_version=packet['version'],grades=grades));return grades

def first_qualified_snapshots(root):
    first={}
    for p in (root/'receipts').glob('*.json'):
        receipt=read_json(p);run=root/'runs'/receipt['run_id'];m,rows=validate_run(run);persisted=validate_receipt(run,receipt,m,rows)
        for r in rows:
            key=(r['game_id'],r['player_id'],r['category'],r['policy_id']);value=(persisted,r['forecast_id'])
            if key not in first or value<first[key]:first[key]=value
    return first

def verify_repository(root):
    count=0
    for p in root.glob('runs/*/RUN.json'):
        run=p.parent;proof=list((root/'receipts').glob(run.name+'*.json'))
        m,rows=validate_run(run,check_clock=not proof)
        for p in proof:validate_receipt(run,read_json(p),m,rows)
        count+=1
    print('FORWARD_REPOSITORY_VALID',count)

if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('issue');a.add_argument('--source',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--models-cache',type=Path,required=True);a.add_argument('--run-id',required=True);a.add_argument('--cache-root',type=Path,action='append',required=True);a.add_argument('--categories',nargs='+',choices=list(CATEGORIES))
    a=s.add_parser('verify');a.add_argument('--root',type=Path,default=Path('prospective'))
    a=s.add_parser('receipt');a.add_argument('--run',type=Path,required=True);a.add_argument('--commit',required=True);a.add_argument('--workflow-run',type=int,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('grade');a.add_argument('--run',type=Path,required=True);a.add_argument('--receipt',type=Path,required=True);a.add_argument('--outcomes',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='issue':issue(a.source,a.output,a.models_cache,a.run_id,a.cache_root,a.categories)
    elif a.command=='verify':verify_repository(a.root)
    elif a.command=='receipt':server_receipt(a.run,a.commit,a.workflow_run,a.output)
    else:grade_run(a.run,a.receipt,a.outcomes,a.output)
