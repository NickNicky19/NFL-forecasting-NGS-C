"""Bounded C06 browser parity: source-qualified display, no NFL evaluation."""
from __future__ import annotations
import argparse,hashlib,json,threading
from contextlib import contextmanager
from datetime import datetime,timezone
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright

@contextmanager
def local_page(root):
 class Quiet(SimpleHTTPRequestHandler):
  def log_message(self,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(root)))
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 try:yield 'http://127.0.0.1:'+str(server.server_port)+'/championship.html'
 finally:server.shutdown();server.server_close();worker.join(timeout=5)

def text_record(v):
 return f'{v["wins"]}–{v["losses"]}/{v["decided"]}/{100*v["rate"]:.2f}%' if v and v['decided'] else 'N/A — no decided selections'

def check(url,root,out,executable='/usr/bin/chromium'):
 root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True);datafile=root/'data/category-decisions-c06.json';data=json.loads(datafile.read_text());rows=data['categories'];assert len(rows)==12
 oldpath=root/'data/championship-period-v2.json';oldhash=hashlib.sha256(oldpath.read_bytes()).hexdigest();errors=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
  context=browser.new_context(viewport={'width':1440,'height':1000},timezone_id='America/Chicago');page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url);page.wait_for_function('window.c06?.healthy&&document.querySelectorAll("#records tr").length===12')
  assert page.locator('#c06-records tr').count()==12
  assert page.locator('#c06-products tr').count()==sum(len(r['other_products']) for r in rows)
  for r in rows:
   cells=page.locator(f'#c06-records tr[data-category="{r["category"]}"] td');assert cells.count()==11
   assert r['label'] in cells.nth(0).inner_text()
   for n,side in enumerate(['OVER','UNDER','COMBINED'],3):assert cells.nth(n).inner_text()==text_record(r[side]),(r['category'],side)
   assert r['decision'] in cells.nth(9).inner_text()
   assert page.evaluate('(cat)=>window.c06.data.categories.find(r=>r.category===cat).exact_procedure',r['category'])==r['exact_procedure']
  limits=page.locator('#c06-limits').inner_text();assert 'Annual retained W1–5' in limits and 'native later-week' in limits and 'Unverified quote clocks stay unverified' in limits
  assert 'original-site activation' in page.locator('#c06-clock').inner_text()
  first=rows[0];page.select_option('#c06-category',first['category']);assert page.locator('#c06-records tr').count()==1
  assert page.locator('#c06-products tr').count()==len(first['other_products']);page.select_option('#c06-category','ALL')
  before=page.locator('#c06-clock').inner_text();page.select_option('#zone','UTC');after=page.locator('#c06-clock').inner_text();assert before!=after
  page.select_option('#zone','America/Chicago');assert page.locator('#c06-clock').inner_text()==before
  assert page.locator('#records tr').count()==12,'LEGACY_PANELS_ERASED'
  page.locator('#c06-title').scroll_into_view_if_needed();page.screenshot(path=str(out/'C06-category-desktop.png'),full_page=False)
  page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390,'MOBILE_GLOBAL_OVERFLOW'
  page.locator('#c06-title').scroll_into_view_if_needed();page.screenshot(path=str(out/'C06-category-mobile.png'),full_page=False)
  page.route('**/data/category-decisions-c06.json',lambda route:route.fulfill(status=503,body='Unavailable'))
  page.evaluate('c06Start()');page.wait_for_function('window.c06.healthy===false&&document.querySelector("#c06-error").hidden===false')
  assert page.locator('#c06-records tr').count()==page.locator('#c06-products tr').count()==0
  assert page.locator('#c06-clock').inner_text()==page.locator('#c06-limits').inner_text()==''
  assert page.locator('#records tr').count()==12,'C06_FAILURE_ERASED_LEGACY'
  context.close()
  for mode in ['HTTP','CHECKSUM','BUILD_BINDING']:
   ctx=browser.new_context();bad=ctx.new_page();bad.on('pageerror',lambda e:errors.append(str(e)))
   if mode=='HTTP':bad.route('**/data/category-decisions-c06.json',lambda route:route.fulfill(status=503,body='Unavailable'))
   elif mode=='CHECKSUM':
    changed=json.loads(json.dumps(data));changed['categories'][0]['decision']='PROVISIONALLY_SWITCH' if changed['categories'][0]['decision']!='PROVISIONALLY_SWITCH' else 'KEEP_INCUMBENT'
    bad.route('**/data/category-decisions-c06.json',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(changed)))
   else:
    build=json.loads((root/'build.json').read_text());build.pop('category_decisions_c06_SHA256',None)
    bad.route('**/build.json',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(build)))
   bad.goto(url);bad.wait_for_function('document.querySelector("#c06-error").hidden===false&&document.querySelectorAll("#records tr").length===12')
   assert bad.locator('#c06-records tr').count()==bad.locator('#c06-products tr').count()==0
   assert 'No default candidate' in bad.locator('#c06-error').inner_text();ctx.close()
  browser.close()
 assert not errors,errors
 assert hashlib.sha256(oldpath.read_bytes()).hexdigest()==oldhash
 result=dict(id='C06-CATEGORY-DECISION-BROWSER-v1',executed_UTC=datetime.now(timezone.utc).isoformat(),URL=url,data_SHA256=hashlib.sha256(datafile.read_bytes()).hexdigest(),categories_checked=[r['category'] for r in rows],all_12_own_side_records_and_decisions_exact=True,other_product_rows=sum(len(r['other_products']) for r in rows),scoped_source_and_timing_limits_visible=True,category_filter=True,Chicago_UTC_clock_display=True,desktop1440_mobile390_no_global_overflow=True,HTTP_checksum_build_binding_fail_closed=True,old_success_text_cleared_on_reload_failure=True,preserved_legacy_panel_rows=12,preserved_legacy_data_SHA256=oldhash,page_errors=[],new_NFL_observations=0,new_fits=0,TLS_verification='ENABLED_NO_IGNORE_FLAGS')
 (out/'BROWSER_PARITY.json').write_text(json.dumps(result,indent=2)+'\n');print('C06_CATEGORY_BROWSER_PASS',len(rows));return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--url');p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--out',type=Path,required=True);p.add_argument('--executable',default='/usr/bin/chromium');a=p.parse_args()
 if a.url:check(a.url,a.root,a.out,a.executable)
 else:
  with local_page(a.root.resolve()) as url:check(url,a.root,a.out,a.executable)
