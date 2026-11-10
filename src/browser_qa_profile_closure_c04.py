"""C04 local/served consumer parity. Browser fixtures add no NFL evidence."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime,timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,root,out,executable='/usr/bin/chromium'):
 root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 payload=json.loads((root/'data/profile-closure-next-02.json').read_text());current=payload['current'];research=payload['research'];errors=[];checks=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  context=browser.new_context(viewport={'width':1440,'height':1000},timezone_id='America/Chicago');page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url);page.wait_for_function('window.c04?.healthy&&window.c04.research!==null')
  assert page.locator('#c04-actual tr').count()==len(research['actual_scores'])
  assert page.locator('#c04-numerical tr').count()==len(research['numerical_scores'])
  assert 'Weeks 2–3 only' in page.locator('#c04-actual-scope').inner_text()
  for model in current['models']:
   page.select_option('#c04-model',model['model_id']);expected=[r for r in current['rows'] if r['model_id']==model['model_id']];shown=page.locator('#c04-current tr');assert shown.count()==len(expected)
   for row in expected:
    cells=page.locator(f'#c04-current tr[data-forecast-id="{row["forecast_id"]}"] td');assert cells.count()==8
    assert cells.nth(2).inner_text()==f'{row["mean"]:.4f}' and cells.nth(3).inner_text()==f'{row["median"]:.4f}'
    assert cells.nth(7).inner_text()=='Unavailable / no selection'
   checks.append(dict(model=model['model_id'],rendered_rows=len(expected),all_mean_median_rows_exact=True))
  page.select_option('#c04-role','WR');chosen=current['models'][-1]['model_id'];assert page.locator('#c04-current tr').count()==sum(r['model_id']==chosen and r['position']=='WR' for r in current['rows'])
  page.select_option('#c04-role','ALL');one=next(r for r in current['rows'] if r['model_id']==chosen);page.fill('#c04-search',one['name']);assert page.locator('#c04-current tr').count()>=1;page.fill('#c04-search','UNMATCHED_SYNTHETIC_NAME');assert page.locator('#c04-current tr').count()==0;page.fill('#c04-search','')
  page.evaluate('()=>{window.c04OriginalNow=Date.now;Date.now=()=>Date.parse(window.c04.rows[0].native_status_observed_UTC)+1000;c04RenderCurrent();}')
  assert all('Fresh experimental snapshot' in s for s in page.locator('#c04-current tr td:nth-child(7)').all_inner_texts())
  page.evaluate('()=>{Date.now=()=>Date.parse(window.c04.rows[0].native_status_observed_UTC)+1801000;c04RenderCurrent();}')
  assert all('status expired' in s for s in page.locator('#c04-current tr td:nth-child(7)').all_inner_texts())
  page.evaluate('()=>{Date.now=()=>Date.parse(window.c04.rows[0].expires_UTC)+1000;c04RenderCurrent();}')
  assert all('source expiry' in s for s in page.locator('#c04-current tr td:nth-child(7)').all_inner_texts())
  page.evaluate('()=>{Date.now=()=>Math.max(...window.c04.rows.map(r=>Date.parse(r.kickoff_UTC)))+1000;c04RenderCurrent();}')
  assert all('game started' in s for s in page.locator('#c04-current tr td:nth-child(7)').all_inner_texts())
  page.evaluate('()=>{Date.now=window.c04OriginalNow;c04RenderCurrent();}')
  assert 'America/Chicago' in page.locator('#c04-current-clocks').inner_text();assert 'GitHub server persistence' in page.locator('#c04-current-clocks').inner_text()
  assert page.locator('#profile-increment-actual tr').count()>0,'PRESERVED_C03_VIEW_UNAVAILABLE'
  page.locator('#c04-current-status').scroll_into_view_if_needed();page.screenshot(path=str(out/'C04-desktop.png'),full_page=False)
  page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390,'MOBILE_GLOBAL_OVERFLOW';page.locator('.c04-filters').evaluate("e=>e.scrollIntoView({block:'start'})");page.screenshot(path=str(out/'C04-mobile.png'),full_page=False)
  context.close()
  for mode in ['HTTP','CHECKSUM']:
   context=browser.new_context();bad=context.new_page()
   if mode=='HTTP':bad.route('**/data/profile-closure-next-02.json',lambda route:route.fulfill(status=503,body='unavailable'))
   else:
    changed=json.loads(json.dumps(payload));changed['current']['rows'][0]['mean']=999999
    bad.route('**/data/profile-closure-next-02.json',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(changed)))
   bad.goto(url);bad.wait_for_function("document.querySelector('#c04-current-status').textContent.includes('unavailable:')")
   assert bad.locator('#c04-current tr').count()==0 and bad.locator('#c04-actual tr').count()==0
   bad.wait_for_function("document.querySelectorAll('#profile-increment-actual tr').length>0")
   assert 'No default forecast, line or selection' in bad.locator('#c04-current-status').inner_text()
   context.close()
  browser.close()
 assert not errors,errors
 receipt=dict(id='C04-SITE-BROWSER-PARITY-v1',executed_UTC=datetime.now(timezone.utc).isoformat(),URL=url,data_SHA256=hashlib.sha256((root/'data/profile-closure-next-02.json').read_bytes()).hexdigest(),checks=checks,canonical_actual_rows=len(research['actual_scores']),canonical_numeric_rows=len(research['numerical_scores']),Chicago_clocks=True,source_inference_issue_server_clocks_separate=True,role_and_search_masks=True,observed_zero_and_null_contract='Exporterfixturesplusallrenderedcurrentpointparity',local_clock_fresh_stale_expiry_started_fixtures=True,HTTP_and_checksum_fail_closed=True,preserved_C03_separate=True,desktop1440_mobile390_no_global_overflow=True,page_errors=errors,new_NFL_observations=0,new_fits=0)
 (out/'BROWSER_PARITY.json').write_text(json.dumps(receipt,indent=2)+'\n');print('C04_BROWSER_PARITY_PASS',sum(x['rendered_rows'] for x in checks));return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--out',type=Path,required=True);p.add_argument('--executable',default='/usr/bin/chromium');a=p.parse_args();check(a.url,a.root,a.out,a.executable)
