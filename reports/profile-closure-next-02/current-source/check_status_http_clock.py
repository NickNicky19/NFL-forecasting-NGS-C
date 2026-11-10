"""Offline pre-issuance clock fixtures; no source request or NFL observation."""
from pathlib import Path
import importlib.util,json,datetime,hashlib
p=Path(__file__).with_name('acquire_current_sources.py')
spec=importlib.util.spec_from_file_location('c04_status_source',p);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
base={'observed_UTC':'2026-11-10T20:00:00+00:00','id':'SYNTHETIC_FIXTURE_NOT_NFL_SOURCE','SHA256':'0'*64}
fixtures=[
 ('fresh', '0','Tue, 10 Nov 2026 19:59:50 GMT',True),
 ('old_cache_receipt_fresh','7200','Tue, 10 Nov 2026 20:00:00 GMT',False),
 ('negative_age','-1','Tue, 10 Nov 2026 20:00:00 GMT',False),
 ('nan_age','nan','Tue, 10 Nov 2026 20:00:00 GMT',False),
 ('infinite_age','inf','Tue, 10 Nov 2026 20:00:00 GMT',False),
 ('unparseable_age','unknown','Tue, 10 Nov 2026 20:00:00 GMT',False),
 ('old_date_with_zero_age','0','Tue, 10 Nov 2026 18:00:00 GMT',False),
 ('future_date','0','Tue, 10 Nov 2026 20:01:00 GMT',False),
 ('malformed_date','0','not-a-date',False),
 ('both_clock_fields_unknown',None,None,False),
 ('date_establishes_response_age',None,'Tue, 10 Nov 2026 19:59:50 GMT',True),
 ('age_establishes_response_age','10',None,True),
 ('exact_1800_boundary','1800','Tue, 10 Nov 2026 19:30:00 GMT',True),
 ('beyond_boundary','1800.1','Tue, 10 Nov 2026 19:30:00 GMT',False),
]
results=[]
for label,age,date,expected in fixtures:
 meta=dict(base,HTTP_Age=age,HTTP_Date=date)
 try:
  outcome=mod.status_http_clock(meta);passed=True;error=None
  if age is None:assert outcome['HTTP_Age_seconds'] is None,'UNKNOWN_AGE_WAS_INVENTED'
 except AssertionError as e:passed=False;error=str(e)
 assert passed is expected,(label,passed,expected,error)
 results.append({'case':label,'input_HTTP_Age':age,'input_HTTP_Date':date,'expected_qualified':expected,'actual_qualified':passed,'rejection':error})
report={'id':'C04-STATUS-HTTP-CLOCK-FIXTURES-v1','executed_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fixture_only':True,'new_NFL_games_weeks_or_forecasts':0,'status_source_code_SHA256':hashlib.sha256(p.read_bytes()).hexdigest(),'fixture_code_SHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':results,'all_expected_dispositions_passed':True}
Path(__file__).with_name('STATUS_HTTP_CLOCK_FIXTURES.json').write_text(json.dumps(report,indent=2)+'\n')
print('STATUS_HTTP_CLOCK_FIXTURES',len(results),'PASS')
