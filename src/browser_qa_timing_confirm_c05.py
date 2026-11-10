"""C05 browser parity; all synthetic clock/error fixtures add zero NFL evidence."""
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from playwright.sync_api import sync_playwright
OLD_DATA_SHA='1ba757dee65177db5a7b4adf16347c5cad43f4bd040312b21fd975248d3acb55'

def check(url,root,out,executable='/usr/bin/chromium'):
 root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 datafile=root/'data/timing-confirm-c05.json';data=json.loads(datafile.read_text());x=data['current'];rec=data['receipts'];errors=[];checks=[]
 oldfile=root/'data/profile-closure-next-02.json';assert hashlib.sha256(oldfile.read_bytes()).hexdigest()==OLD_DATA_SHA,'OLD_C04_BYTES_CHANGED'
 old=json.loads(oldfile.read_text())['current'];assert len(x['rows'])==69 and len(old['rows'])==75
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  context=browser.new_context(viewport={'width':1440,'height':1000},timezone_id='America/Chicago');page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url);page.wait_for_function('window.c05?.healthy&&window.c04?.healthy')
  assert page.locator('#c05-reception tr').count()==len(rec['reception_annual'])==22
  assert page.locator('#c05-completion tr').count()==len(rec['completion_annual'])==22
  correction=page.locator('#c05-source-correction').inner_text();assert 'Weeks 1–5' in correction and 'Weeks 6–7' in correction and 'mixed diagnostics' in correction
  assert '232/412 / 235/412 / 237/412' in page.locator('#c05-reception-summary').inner_text()
  assert '239/412' in page.locator('#c05-reception-summary').inner_text()
  assert '47/88 / 42/88 / 40/88 / 44/88' in page.locator('#c05-completion-summary').inner_text()
  assert '52/88' in page.locator('#c05-completion-summary').inner_text()
  assert 'NOT_IN_RECEIVED_PACKAGE' in page.locator('#c05-new-joins').inner_text()
  for table,rows in [('c05-reception',rec['reception_annual']),('c05-completion',rec['completion_annual'])]:
   for r in rows:
    cells=page.locator(f'#{table} tr[data-procedure="{r["procedure_id"]}"] td');assert cells.count()==7
    for n,side in enumerate(['OVER','UNDER','COMBINED'],1):
     v=r[side];expected=f'{v["wins"]}–{v["losses"]}/{v["decided"]}/{100*v["rate"]:.2f}%' if v['decided'] else 'N/A';assert cells.nth(n).inner_text()==expected
  old_clocks=page.locator('#c04-current-clocks').inner_text()
  assert page.evaluate('window.c04.current.rows.length')==75
  for model in x['models']:
   page.select_option('#c05-model',model['model_id']);expected=[r for r in x['rows'] if r['model_id']==model['model_id']];shown=page.locator('#c05-current tr');assert shown.count()==len(expected)==23
   for row in expected:
    cells=page.locator(f'#c05-current tr[data-forecast-id="{row["forecast_id"]}"] td');assert cells.count()==8
    assert cells.nth(2).inner_text()==f'{row["mean"]:.4f}' and cells.nth(3).inner_text()==f'{row["median"]:.4f}'
    assert cells.nth(7).inner_text()=='Unavailable / no selection'
   checks.append(dict(model_id=model['model_id'],rendered_rows=len(expected),mean_and_median_exact=True))
  page.select_option('#c05-role','WR');assert page.locator('#c05-current tr').count()==10
  page.select_option('#c05-role','ALL');chosen=x['models'][-1]['model_id'];one=next(r for r in x['rows'] if r['model_id']==chosen);page.fill('#c05-search',one['name']);assert page.locator('#c05-current tr').count()>=1
  page.fill('#c05-search','UNMATCHED_SYNTHETIC_NAME');assert page.locator('#c05-current tr').count()==0;page.fill('#c05-search','')
  page.evaluate('()=>{window.c05OriginalNow=Date.now;Date.now=()=>Date.parse(window.c05.rows[0].native_status_observed_UTC)+1000;c05RenderCurrent();}')
  assert all('Eligible recent status · frozen-football shadow'==v for v in page.locator('#c05-current tr td:nth-child(7)').all_inner_texts())
  page.evaluate('()=>{Date.now=()=>Date.parse(window.c05.rows[0].native_status_observed_UTC)+1801000;c05RenderCurrent();}')
  assert all('status expired' in v for v in page.locator('#c05-current tr td:nth-child(7)').all_inner_texts())
  page.evaluate('()=>{Date.now=()=>Date.parse(window.c05.rows[0].expires_UTC)+1000;c05RenderCurrent();}')
  assert all('source expiry' in v for v in page.locator('#c05-current tr td:nth-child(7)').all_inner_texts())
  page.evaluate('()=>{Date.now=()=>Math.max(...window.c05.rows.map(r=>Date.parse(r.kickoff_UTC)))+1000;c05RenderCurrent();}')
  assert all('game started' in v for v in page.locator('#c05-current tr td:nth-child(7)').all_inner_texts())
  page.evaluate('()=>{Date.now=window.c05OriginalNow;c05RenderCurrent();}')
  clocks=page.locator('#c05-current-clocks').inner_text()
  for label in ['Football source','model/feature cutoff','originally prepared','current roster eligibility','actually re-inferred','native status','issued','GitHub server persistence','America/Chicago']:assert label in clocks
  assert page.locator('#c04-current-clocks').inner_text()==old_clocks,'OLD_PACKET_CLOCKS_OVERWRITTEN'
  for model in old['models']:
   page.select_option('#c04-model',model['model_id']);assert page.locator('#c04-current tr').count()==25
  assert page.locator('#profile-increment-actual tr').count()>0
  assert 'does not verify Count A' in page.locator('#c05-original-site').inner_text()
  assert 'superseding immutable metadata receipt is now received' in page.locator('#c05-original-site').inner_text()
  assert 'not 24 qualified actual-offer selections' in page.locator('#c05-original-site').inner_text()
  page.locator('#c05-current-status').scroll_into_view_if_needed();page.screenshot(path=str(out/'C05-desktop.png'),full_page=False)
  page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390,'MOBILE_GLOBAL_OVERFLOW';page.locator('.c05-filters').evaluate("e=>e.scrollIntoView({block:'start'})");page.screenshot(path=str(out/'C05-mobile.png'),full_page=False)
  page.route('**/data/timing-confirm-c05.json',lambda route:route.fulfill(status=503,body='unavailable'))
  page.evaluate('c05Start()');page.wait_for_function('window.c05.healthy===false')
  assert page.locator('#c05-current tr').count()==0 and page.locator('#c05-current-clocks').inner_text()==''
  assert page.locator('#c05-original-site').inner_text()=='' and page.locator('#c05-reception-summary').inner_text()==''
  assert page.evaluate('window.c04.healthy') is True and page.locator('#c04-current-clocks').inner_text()==old_clocks
  context.close()
  for mode in ['HTTP','CHECKSUM']:
   context=browser.new_context();bad=context.new_page()
   if mode=='HTTP':bad.route('**/data/timing-confirm-c05.json',lambda route:route.fulfill(status=503,body='unavailable'))
   else:
    changed=json.loads(json.dumps(data));changed['current']['rows'][0]['mean']=999999
    bad.route('**/data/timing-confirm-c05.json',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(changed)))
   bad.on('pageerror',lambda e:errors.append(str(e)));bad.goto(url);bad.wait_for_function("document.querySelector('#c05-status').textContent.includes('C05 continuation unavailable:')&&window.c04?.healthy")
   assert bad.locator('#c05-current tr').count()==bad.locator('#c05-reception tr').count()==bad.locator('#c05-completion tr').count()==0
   assert bad.locator('#c04-current tr').count()==25
   assert 'no default point or line' in bad.locator('#c05-current-status').inner_text()
   context.close()
  browser.close()
 assert not errors,errors
 receipt=dict(id='C05-SITE-BROWSER-PARITY-v1',executed_UTC=datetime.now(timezone.utc).isoformat(),URL=url,data_SHA256=hashlib.sha256(datafile.read_bytes()).hexdigest(),model_checks=checks,annual_reception_rows=22,annual_completion_rows=22,own_side_arithmetic_rendered=True,annual_W1_W5_vs_mixed_W6_W7_correction_visible=True,new_timing_joins_not_in_received_package_visible=True,Chicago_per_batch_clocks=True,frozen_information_and_current_eligibility_separate=True,all_69_current_rows_rendered=True,original_C04_75_rows_and_data_SHA_unchanged=OLD_DATA_SHA,role_and_search_masks=True,clock_fresh_stale_expiry_started_fixtures=True,HTTP_and_checksum_fail_closed=True,previous_success_text_cleared_on_reload_failure=True,desktop1440_mobile390_no_global_overflow=True,page_errors=errors,new_NFL_observations=0,new_fits=0)
 (out/'BROWSER_PARITY.json').write_text(json.dumps(receipt,indent=2)+'\n');print('C05_BROWSER_PARITY_PASS',sum(v['rendered_rows'] for v in checks));return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--out',type=Path,required=True);p.add_argument('--executable',default='/usr/bin/chromium');a=p.parse_args();check(a.url,a.root,a.out,a.executable)
