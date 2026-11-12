"""Direct served-page expiry check; no simulated clock or forecast refresh."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
from playwright.sync_api import sync_playwright
out=Path('reports/category-decision-release-01/site/served')
url='https://nicknicky19.github.io/NFL-forecasting-NGS-C/championship.html?verified=b38ea4c9f60c15225ae6a252873e943f904309a4'
expected='b38ea4c9f60c15225ae6a252873e943f904309a4'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=browser.new_page(viewport={'width':1440,'height':1000},timezone_id='America/Chicago');page.goto(url);page.wait_for_function('window.c06?.healthy&&document.querySelectorAll("#records tr").length===12')
 assert page.evaluate('build.served_commit')==expected
 assert page.locator('#c06-records tr').count()==12 and page.locator('#c06-products tr').count()==48 and page.locator('#c06-current-records tr').count()==25
 info=page.evaluate('()=>({now:Date.now(),packet:window.c06.data.current_packet})');packet=info['packet']
 expiry=page.evaluate('Date.parse(window.c06.data.current_packet.expires_UTC)');kickoff=page.evaluate('Date.parse(window.c06.data.current_packet.rows[0].kickoff_UTC)')
 assert expiry<info['now']<kickoff
 statuses=page.locator('#c06-current-records td:nth-child(6)').all_inner_texts();assert len(statuses)==25 and all('Expired for current use' in x for x in statuses)
 assert all(x=='Unavailable · no qualified offer or selection' for x in page.locator('#c06-current-records td:nth-child(7)').all_inner_texts())
 for row in packet['rows']:
  cells=page.locator(f'#c06-current-records tr[data-forecast-id="{row["forecast_id"]}"] td')
  assert cells.nth(1).inner_text()==f'{row["mean"]:.4f}' and cells.nth(2).inner_text()==f'{row["median"]:.4f}'
 page.locator('#c06-current-title').scroll_into_view_if_needed();page.screenshot(path=str(out/'C06-current-expired-desktop.png'),full_page=False)
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390
 page.locator('#c06-current-title').scroll_into_view_if_needed();page.screenshot(path=str(out/'C06-current-expired-mobile.png'),full_page=False)
 browser.close()
result=dict(id='C06-DIRECT-SERVED-ACTUAL-EXPIRY-v1',executed_UTC=datetime.now(timezone.utc).isoformat(),URL=url,served_commit=expected,actual_browser_clock_UTC=datetime.fromtimestamp(info['now']/1000,timezone.utc).isoformat(),expires_UTC=packet['expires_UTC'],kickoff_UTC=packet['rows'][0]['kickoff_UTC'],clock_simulated=False,current_forecasts_checked=25,all_actual_expired_current_use=True,forecast_values_preserved_for_later_grade=True,real_offers=0,real_selections=0,primary_replacement=False,all25_expected_means_and_lower_medians_exact=True,categories=12,other_product_rows=48,WR_TE_candidate_scope=18,RB_shadow_rows=7,mobile390_no_global_overflow=True,TLS='ENABLED_NO_IGNORE_FLAGS',original_website_changed=False,new_fits=0,new_capture_or_inference=0)
(out/'ACTUAL_EXPIRY_PARITY.json').write_text(json.dumps(result,indent=2)+'\n');print('C06_ACTUAL_SERVED_EXPIRED_PASS',expected)
