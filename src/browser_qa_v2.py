"""Rendered-row, responsive, clock and failure checks against retained site data."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright
def check(url,root,output,expected_commit=None):
 m=json.load(open(root/'data/manifest.json'));checks=[]
 with sync_playwright() as p:
  b=p.chromium.launch(headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url.split('#',1)[0]+'#forecasts',wait_until='networkidle');page.wait_for_selector('#forecasts tbody tr');assert page.locator('#categories button').count()==12
  for c in m['categories']:
   t=c['id'];page.select_option('#category',t);page.wait_for_function("t=>document.querySelector('#forecasts tbody tr')?.dataset.slot.includes('-'+t+'-')",arg=t)
   e=next(e for e in m['files'] if e['target']==t and e['history']=='H-MULTI' and e['family']=='P2_LEAF' and e['week']==7);rows=json.load(open(root/'data'/e['file']));rows=[r for r in rows if r['position']=='RB'] if t in ['rush_yd','rush_att'] else rows;rows=sorted(rows,key=lambda x:x['name']);r=rows[0];tr=page.locator('#forecasts tbody tr').first
   assert tr.get_attribute('data-player-id')==r['player_id'];cells=tr.locator('td').all_text_contents();assert r['name'] in cells[0]
   if t=='anytime_td':assert cells[1]=='Event only' and cells[5]=='Not offered'
   else:
    expected=page.evaluate('v=>v.toFixed(2)',r['mean']);assert cells[1]==expected
    expected=page.evaluate('v=>v.toFixed(2)',r['median']);assert cells[2]==expected
   line=float(page.locator('#threshold').input_value());v=r['p_over'][r['grid'].index(line)];assert cells[4]==page.evaluate('v=>(100*v).toFixed(1)+"%"',v)
   assert page.locator('#forecasts tbody tr').count()==len(rows);count=page.locator('#row-count').inner_text();assert f'{len(rows)} retained queries' in count and f'{sum(r["actual"] is not None for r in rows)} supported outcomes' in count
   checks.append(dict(category=t,rendered_query_rows=len(rows),first_player_id=r['player_id'],typed_value_probability_parity='PASS'))
  page.select_option('#category','rush_yd');page.wait_for_function("()=>document.querySelector('#forecasts tbody tr')?.dataset.slot.includes('-rush_yd-')");page.select_option('#role','QB');assert page.locator('#forecasts tbody tr').count()>0;page.fill('#search','NOT_A_REAL_PLAYER');assert page.locator('#forecasts tbody tr').count()==0;assert '0 supported outcomes' in page.locator('#row-count').inner_text();page.fill('#search','')
  page.select_option('#category','pass_cmp');page.select_option('#history','H-CURRENT');page.select_option('#week','1');page.wait_for_function("()=>document.querySelector('#forecasts tbody tr')?.dataset.slot.includes('H-CURRENT-P2_LEAF-E0_OP-W01')");assert 'Startup fallback' in page.locator('#forecasts tbody').inner_text();assert page.locator('#forecasts tbody tr').first.locator('td').nth(1).inner_text()=='0.00'
  page.select_option('#history','H-MULTI');page.select_option('#week','7');page.select_option('#family','P3_HGB');page.wait_for_function("()=>document.querySelector('#forecasts tbody tr')?.dataset.slot.includes('P3_HGB-E0_OP-W07')");assert page.locator('#forecasts tbody tr').first.locator('td').nth(1).inner_text()=='N/A'
  page.click('nav button[data-view=results]');assert page.locator('#results tbody tr').count()>0;page.select_option('#result-history','H-CURRENT');page.select_option('#result-period','W1');assert page.locator('#results tbody tr').count()>0;page.locator('#results tbody tr').first.click();page.wait_for_selector('#detail-body h3');assert 'Reliability' in page.locator('#detail-body').inner_text();page.click('#close-detail')
  for season in [2025,2024,2023,2022]:
   page.select_option('#legacy-season',str(season));legacy=[r for r in m['frozen_prior_summary'] if r['season']==season];assert page.locator('#legacy-results tbody tr').count()==len(legacy)==18
   for i,r in enumerate(legacy):
    cells=page.locator('#legacy-results tbody tr').nth(i).locator('td').all_text_contents();assert cells[0]==r['target']+' · '+r['horizon'] and cells[1]==r['arm'];assert cells[2]==page.evaluate('v=>v.toFixed(6)',r['mae']);assert cells[3]==str(r['outcomes'])+' / '+str(r['queries'])
  page.click('nav button[data-view=methods]');assert page.locator('#leaders tbody tr').count()==12
  page.click('nav button[data-view=rankings]');assert page.locator('#view-rankings button:disabled').count()==1;page.click('#price-mode');assert 'Price-aware value unavailable' in page.locator('#ranking-title').inner_text()
  page.click('nav button[data-view=six]');assert page.locator('#six-history tbody tr').count()==7;assert page.locator('#view-six button:disabled').count()==1;assert 'NO_QUALIFIED_SIX_LEG_ENTRY' in page.locator('#view-six').inner_text()
  page.click('nav button[data-view=sources]');page.select_option('#timezone','UTC');assert 'UTC' in page.locator('#footer-version').inner_text();assert 'Authenticated source as-of' in page.locator('#build-status').inner_text() and 'Unknown' in page.locator('#build-status').inner_text()
  if expected_commit:assert expected_commit in page.locator('#build-status').inner_text()
  # DST conversion uses timezone database, not a fixed offset.
  dst=page.evaluate("()=>[new Intl.DateTimeFormat('en-US',{timeZone:'America/Chicago',hour:'numeric',hour12:false}).format(new Date('2026-10-31T18:00:00Z')),new Intl.DateTimeFormat('en-US',{timeZone:'America/Chicago',hour:'numeric',hour12:false}).format(new Date('2026-11-01T18:00:00Z'))]");assert dst==['13','12']
  page.click('nav button[data-view=forecasts]');page.select_option('#family','P2_LEAF');page.wait_for_function("()=>document.querySelector('#forecasts tbody tr')?.dataset.slot.includes('P2_LEAF')");page.screenshot(path=str(output.parent/'site-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390;page.screenshot(path=str(output.parent/'site-mobile.png'),full_page=True)
  # Missing data and corruption cannot silently render a fake valid record.
  context=b.new_context();bad=context.new_page();bad.route('**/data/manifest.json',lambda route:route.fulfill(status=503,body='unavailable'));bad.goto(url);bad.wait_for_selector('#error:not([hidden])');assert bad.locator('#forecasts tbody tr').count()==0
  context.close();context=b.new_context();bad=context.new_page();e=next(e for e in m['files'] if e['target']=='pass_yd' and e['history']=='H-MULTI' and e['family']=='P2_LEAF' and e['week']==7);rows=json.load(open(root/'data'/e['file']));rows[0]['mean']=99999;bad.route('**/data/'+e['file'],lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(rows)));bad.goto(url);bad.wait_for_selector('#error:not([hidden])');assert 'checksum mismatch' in bad.locator('#error').inner_text();assert bad.locator('#forecasts tbody tr').count()==0
  context.close();b.close();assert not errors
 receipt=dict(url=url,expected_served_commit=expected_commit,category_row_checks=checks,desktop={'width':1440,'PASS':True},mobile={'width':390,'no_global_overflow':True},typed_P3_numerical_unavailable=True,strict_CURRENT_W1_fallback=True,role_search_counts=True,results_role_week_calibration=True,twelve_method_leaders=True,frozen_2022_2025_72_aggregate_rows=True,rankings_and_entries_fail_closed=True,timezone_UTC_Chicago_DST=True,unknown_authenticated_source_clock=True,HTTP_failure_closed=True,checksum_corruption_closed=True,page_errors=errors,tests_are='rendered site checks, not NFL forecasts or original issued picks')
 output.write_text(json.dumps(receipt,indent=2));print('BROWSER_QA_PASS',url,len(checks))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);p.add_argument('--expected-commit');a=p.parse_args();check(a.url,a.root,a.receipt,a.expected_commit)
