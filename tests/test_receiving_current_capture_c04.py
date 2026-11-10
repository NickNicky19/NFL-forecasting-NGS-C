import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import receiving_current_capture_c04 as c

AT=c.timestamp('2026-11-10T20:00:00+00:00')
def game():
 return dict(game_id='2026_10_WAS_NYG',season=2026,week=10,home_team='NYG',away_team='WAS',espn=123,kickoff=AT+86400)
def event():
 g=game()
 return dict(espn_event_id='123',competition_id='123',home_team='NYG',away_team='WAS',season=2026,week=10,season_type=2,
             kickoff=g['kickoff'],kickoff_UTC='2026-11-11T20:00:00+00:00',state='pre',status_name='STATUS_SCHEDULED',completed=False,
             observed_UTC='2026-11-10T19:59:59+00:00',source_id='fixture',game_id=g['game_id'])
def roster(pid='00-0000001',role='WR',status='ACT',team='NYG'):
 return dict(gsis_id=pid,position=role,status=status,team=team,season=2026,full_name='Fixture')
def source_meta(**changes):
 s=dict(id='fixture',status=200,state='RECEIVED',observed_UTC='2026-11-10T20:00:00+00:00',
        HTTP_Age='0',HTTP_Date='Tue, 10 Nov 2026 20:00:00 GMT',SHA256='a'*64)
 s.update(changes);return s
def status_manifest(root,events_path,input_hash,source=None):
 s=source or source_meta(observed_UTC=event()['observed_UTC'],HTTP_Date='Tue, 10 Nov 2026 19:59:59 GMT')
 clock=c.independent_response_clock(s,c.timestamp(s['observed_UTC']))
 for k in ['effective_HTTP_Age_seconds_at_issuance','HTTP_Date_age_seconds_at_issuance']:clock.pop(k)
 clock.update(state='HTTP_RESPONSE_CLOCK_QUALIFIED',max_age_seconds=1800,future_Date_clock_skew_tolerance_seconds=5)
 return dict(events_binding=dict(path=events_path.relative_to(root).as_posix(),bytes=events_path.stat().st_size,SHA256=c.sha(events_path),
          rows=len(c.read(events_path)),source_id=s['id'],observed_UTC=s['observed_UTC'],status_response_raw_SHA256=s['SHA256']),
          status_source=s,status_HTTP_response_clock=clock,model_inputs={'SHA256':input_hash},actual_status_observed_UTC=s['observed_UTC'],
          status_execution_code_SHA256=c.sha(c.STATUS_CODE_PATH))

class CurrentCaptureTests(unittest.TestCase):
 def test_no_target_outcome_required_and_season_roster_not_future_week(self):
  r=roster();basic,q=c.query_universe([r],[game()],2026)
  self.assertEqual(len(q),1);self.assertIsNone(basic[0]['roster_week'])
  self.assertIsNone(basic[0]['individual_transaction_effective_UTC'])
  self.assertEqual(basic[0]['injury_state'],'UNKNOWN_NO_QUALIFIED_INJURY_FEED')
  for key in ['actual','values','played','available']:self.assertNotIn(key,q[0])
  changed=dict(r,actual=99,played=True,targets=100)
  self.assertEqual(c.query_universe([changed],[game()],2026),(basic,q))
 def test_all_basic_rows_preserved_hold_invalid_nonactive_qb_outside(self):
  rr=[roster(),roster('00-0000002','QB'),roster('00-0000003',status='RES'),roster(None),roster('00-0000005',team='BUF')]
  b,q=c.query_universe(rr,[game()],2026)
  self.assertEqual(len(b),5);self.assertEqual(len(q),1)
  self.assertEqual([r['state'] for r in b][1:],['B_OWNED_QB_BASIC_ONLY','CURRENT_ROSTER_RES','INVALID_NATIVE_PLAYER_ID','NO_CANDIDATE_SCHEDULE_EVENT'])
 def test_duplicate_native_ids_held(self):
  b,q=c.query_universe([roster(),roster()],[game()],2026)
  self.assertFalse(q);self.assertTrue(all(r['state']=='DUPLICATE_NATIVE_PLAYER_ID' for r in b))
 def test_native_identity_time_and_status_gates(self):
  g=game();e=event();accepted,rejected=c.qualified_events([g],[e],AT,after=AT-2)
  self.assertEqual(list(accepted),[g['game_id']]);self.assertFalse(rejected)
  for key,value in [('espn_event_id','wrong'),('game_id','wrong'),('home_team','BUF'),('week',9),('season_type',3),('kickoff',AT+100),('state','in'),('completed',True),('observed_UTC','2026-11-10T19:00:00+00:00'),('observed_UTC','2026-11-10T20:00:01+00:00')]:
   a,r=c.qualified_events([g],[dict(e,**{key:value})],AT,after=AT-2)
   self.assertFalse(a,(key,value));self.assertEqual(len(r),1)
  self.assertFalse(c.qualified_events([g],[e,e],AT)[0])
 def test_fresh_status_must_follow_clean_start(self):
  self.assertFalse(c.qualified_events([game()],[event()],AT,after=AT)[0])
 def test_partial_verified_slate_not_invented_full_week(self):
  g2=dict(game(),game_id='2026_10_BUF_NYJ',home_team='NYJ',away_team='BUF',espn=456)
  a,r=c.qualified_events([game(),g2],[event()],AT)
  self.assertEqual(len(a),1);self.assertEqual(r,[dict(game_id=g2['game_id'],reason='NATIVE_EVENT_MISSING_OR_DUPLICATED')])
 def test_explicit_null_survives_safe_immutable_roundtrip(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'fixture.json.xz';row=dict(line=None,selected_side=None,probability_at_line=None,mean=0.,unknown=float('nan'))
   c.write(p,row,exclusive=True);got=c.read(p)
   self.assertEqual(got['mean'],0.);self.assertIsNone(got['line']);self.assertIsNone(got['unknown'])
   with self.assertRaises(FileExistsError):c.write(p,{},exclusive=True)
 def test_draft_requires_specific_root_authorization_before_work(self):
  with patch.object(c,'read',return_value={'current_capture':{'future_fits_max':3,'execution_authorized':False}}):
   with self.assertRaisesRegex(RuntimeError,'ROOT_AUTHORIZATION'):c.fit_draft('not-a-source','not-a-draft')
 def test_issue_refuses_existing_run_before_any_model_loading(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(FileExistsError):c.issue('missing','missing',td,'run','missing')
 def test_timezone_aware_clocks_required(self):
  with self.assertRaisesRegex(ValueError,'TIMEZONE'):c.timestamp('2026-11-10T20:00:00')
 def test_http_age_date_independent_receipt_and_issue_checks(self):
  self.assertEqual(c.independent_response_clock(source_meta(HTTP_Age='1800',HTTP_Date=None),AT)['HTTP_Age_seconds'],1800)
  self.assertEqual(c.independent_response_clock(source_meta(HTTP_Age=None),AT)['HTTP_Age_seconds'],None)
  self.assertEqual(c.independent_response_clock(source_meta(HTTP_Date=None),AT)['HTTP_Date_UTC'],None)
  bad=[{'HTTP_Age':'1801'},{'HTTP_Age':'7200'},{'HTTP_Age':'-1'},{'HTTP_Age':'nan'},{'HTTP_Age':'inf'},
       {'HTTP_Age':'unknown'},{'HTTP_Age':None,'HTTP_Date':None},{'HTTP_Date':'bad'},
       {'HTTP_Date':'Tue, 10 Nov 2026 20:00:06 GMT'},{'HTTP_Date':'Tue, 10 Nov 2026 19:29:59 GMT'}]
  for values in bad:
   with self.assertRaises(ValueError,msg=str(values)):c.independent_response_clock(source_meta(**values),AT)
  with self.assertRaises(ValueError):c.independent_response_clock(source_meta(HTTP_Age='1800',HTTP_Date=None),AT+1)
  with self.assertRaises(ValueError):c.independent_response_clock(source_meta(HTTP_Age=None,HTTP_Date='Tue, 10 Nov 2026 19:30:00 GMT'),AT+1)
 def test_status_manifest_events_raw_clock_and_code_bindings(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'events.json';c.write(p,[event()]);m=status_manifest(root,p,'input')
   c.write(root/'SOURCE_MANIFEST.json',m)
   with patch.object(c,'ROOT',root):
    self.assertEqual(c.validate_status_snapshot(p,AT,input_manifest_SHA256='input')[0],[event()])
    for field,bad in [('events_binding',dict(m['events_binding'],SHA256='b'*64)),('events_binding',dict(m['events_binding'],source_id='wrong')),
                     ('events_binding',dict(m['events_binding'],observed_UTC='2026-11-10T19:59:58+00:00')),
                     ('events_binding',dict(m['events_binding'],status_response_raw_SHA256='b'*64)),
                     ('status_execution_code_SHA256','bad')]:
     c.write(root/'SOURCE_MANIFEST.json',dict(m,**{field:bad}))
     with self.assertRaises(ValueError,msg=field):c.validate_status_snapshot(p,AT,input_manifest_SHA256='input')
    bad=copy.deepcopy(m);bad['status_source']['HTTP_Age']='7200';c.write(root/'SOURCE_MANIFEST.json',bad)
    with self.assertRaises(ValueError):c.validate_status_snapshot(p,AT,input_manifest_SHA256='input')
 def test_recent_finality_requires_native_match_old_scores_keep_separate(self):
  import pandas as pd
  old=dict(game(),game_id='2026_08_WAS_NYG',week=8,kickoff=AT-8*86400,home_score=20,away_score=10)
  recent=dict(game(),game_id='2026_09_WAS_NYG',week=9,kickoff=AT-86400,home_score=20,away_score=10)
  unknown=dict(recent,game_id='2026_09_BUF_NYJ',home_team='NYJ',away_team='BUF',espn=456)
  e=dict(event(),game_id=recent['game_id'],week=9,kickoff=recent['kickoff'],state='post',completed=True,status_name='STATUS_FINAL',observed_UTC='2026-11-10T20:00:00+00:00')
  s=source_meta();clock=c.independent_response_clock(s,AT)
  m=dict(target_season=2026,actual_input_cutoff_UTC='2026-11-10T20:00:00+00:00',completed_game_ids=[old['game_id'],recent['game_id']])
  proof=dict(actual_information_cutoff_UTC=m['actual_input_cutoff_UTC'],status_source=s,status_HTTP_response_clock=clock,
    status_execution_code_SHA256=c.sha(c.STATUS_CODE_PATH),events=[e],completed_game_ids=m['completed_game_ids'],
    older_final_game_ids=[old['game_id']],recent_native_final_game_ids=[recent['game_id']],held_recent_game_ids=[unknown['game_id']])
  accepted,receipt=c.qualified_completed_games(pd.DataFrame([old,recent,unknown]),m,proof,AT)
  self.assertEqual(accepted,{old['game_id'],recent['game_id']});self.assertEqual(receipt['held_recent_games'],[unknown['game_id']])
  for field,bad in [('state','pre'),('completed',False),('status_name','STATUS_SCHEDULED'),('home_team','BUF'),('kickoff',AT-86400+2),('week',8),('espn_event_id','wrong')]:
   changed=copy.deepcopy(proof);changed['events']=[dict(e,**{field:bad})]
   with self.assertRaises(ValueError,msg=field):c.qualified_completed_games(pd.DataFrame([old,recent,unknown]),m,changed,AT)
  # A fresh observed time with old cache Age cannot qualify historical labels.
  changed=copy.deepcopy(proof);changed['status_source']['HTTP_Age']='7200'
  with self.assertRaises(ValueError):c.qualified_completed_games(pd.DataFrame([old,recent,unknown]),m,changed,AT)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);oldsource=dict(id='fixture',HTTP_status=200,raw_SHA256='a'*64,HTTP_Age=None,
      HTTP_Date='Tue, 10 Nov 2026 19:59:58 GMT',observed_UTC='2026-11-10T19:59:58.657819+00:00')
   oldevent=dict(e,observed_UTC=oldsource['observed_UTC']);saved=root/'retained.json';c.write(saved,dict(event=oldevent,source=oldsource))
   clock=c.independent_response_clock(dict(oldsource,SHA256=oldsource['raw_SHA256']),c.timestamp(oldsource['observed_UTC']))
   clock['HTTP_Date_age_seconds_at_observation']=.657819
   retained=dict(path='retained.json',bytes=saved.stat().st_size,SHA256=c.sha(saved),event=oldevent,status_source=oldsource,HTTP_response_clock_at_original_observation=clock)
   p=copy.deepcopy(proof);p.update(status_source=None,status_HTTP_response_clock=None,events=[],native_request_failure='HTTP400',retained_native_final_proofs=[retained])
   with patch.object(c,'ROOT',root):
    got,r=c.qualified_completed_games(pd.DataFrame([old,recent,unknown]),m,p,AT)
    self.assertEqual(got,{old['game_id'],recent['game_id']});self.assertTrue(r['retained_finality_clocks_not_relabeled'])
    # A present contradictory current event cannot be replaced by the old FINAL.
    p.update(status_source=s,status_HTTP_response_clock=proof['status_HTTP_response_clock'],events=[dict(e,state='pre',completed=False)])
    with self.assertRaises(ValueError):c.qualified_completed_games(pd.DataFrame([old,recent,unknown]),m,p,AT)
 def test_issue_draft_packet_filters_events_and_keeps_clocks_and_nulls(self):
  # Synthetic filesystem fixture only: no source request, NFL fit or issuance.
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);draft=root/'draft';source=root/'source';out=root/'run'
   draft.mkdir();source.mkdir();bind=dict(code_commit='fixture',code_SHA256={'fixture':'fixture'},registration_SHA256='fixture')
   original=dict(actual_input_cutoff_UTC='2026-11-10T18:55:00+00:00',sources=[dict(id='CURRENT_SEASON_ROSTER',HTTP_Last_Modified='Tue, 10 Nov 2026 15:34:29 GMT')])
   c.write(source/'MODEL_INPUT_MANIFEST.json',original)
   c.write(draft/'MODEL_INPUT_MANIFEST.json',original)
   row=dict(game_id=game()['game_id'],model_id='fixture',player_id='00-0000001',kickoff=game()['kickoff'],
            kickoff_UTC=event()['kickoff_UTC'],line=None,selected_side=None,probability_at_line=None,
            inference_UTC='2026-11-10T19:00:00+00:00',mean=0.)
   c.write(draft/'DRAFT_FORECASTS.json.xz',[row])
   c.write(draft/'BASIC_UNIVERSE.json.xz',[dict(candidate_game_ids=[game()['game_id']],state='DRAFT_CANDIDATE_PENDING_NATIVE_EVENT')])
   files={p.name:dict(SHA256=c.sha(p),bytes=p.stat().st_size) for p in draft.iterdir()}
   m=dict(**bind,files=files,input_manifest_SHA256=c.sha(source/'MODEL_INPUT_MANIFEST.json'),input_cutoff_UTC=original['actual_input_cutoff_UTC'],
          created_UTC='2026-11-10T19:00:00+00:00',candidate_games=[game()],models=[],new_fits=0)
   c.write(draft/'DRAFT.json',m);c.write(root/'events.json',[event()])
   c.write(root/'SOURCE_MANIFEST.json',status_manifest(root,root/'events.json',m['input_manifest_SHA256']))
   c.write(root/'proof.json',dict(**bind,git_status='',created_UTC='2026-11-10T19:59:58+00:00'))
   c.write(root/'reg.json',{'current_capture':{'budget':{'new_public_bytes_max':1000000}}})
   with patch.object(c,'ROOT',root),patch.object(c,'SOURCE',source),patch.object(c,'REG',root/'reg.json'),patch.object(c,'committed_bindings',return_value=bind),patch.object(c,'validate_inputs',return_value=original),patch.object(c,'now',return_value='2026-11-10T20:00:00+00:00'),patch.object(c.subprocess,'check_output',return_value=''):
    result=c.issue(draft,root/'events.json',out,'FIXTURE',root/'proof.json')
   self.assertEqual(result['real_offers'],0);self.assertEqual(result['real_selections'],0)
   got=c.read(out/'FORECASTS.json.xz')[0]
   self.assertIsNone(got['line']);self.assertIsNone(got['selected_side']);self.assertEqual(got['mean'],0.)
   self.assertEqual(got['inference_UTC'],'2026-11-10T19:00:00+00:00')
   self.assertEqual(got['issued_UTC'],'2026-11-10T20:00:00+00:00')
   self.assertEqual(got['lead_seconds_at_issuance'],86400)

if __name__=='__main__':unittest.main()
