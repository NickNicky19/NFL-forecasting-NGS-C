"""Rendered shared-scorecard and exact-product qualification checks; no NFL fits."""
import argparse
import gzip
import hashlib
import json
import os
from datetime import datetime,timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,root,receipt,commit=None,public_build=None,assets_receipt=None):
    data=json.loads(gzip.decompress((root/'data/qualification-5w.json.gz').read_bytes()))
    named=next(r for r in data['rows'] if r.get('named_delivery_product')=='pass_td__COUNT_A_MEAN')
    errors=[]
    build_bytes=None
    if public_build:
        assert assets_receipt is not None
        assets=json.loads(assets_receipt.read_bytes());build_bytes=public_build.read_bytes()
        for obj in assets['objects']:
            actual=build_bytes if obj['path']=='build.json' else (root/obj['path']).read_bytes()
            assert hashlib.sha256(actual).hexdigest()==obj['SHA256'],obj['path']
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,args=['--no-sandbox'],executable_path=os.environ.get('C_BROWSER_EXECUTABLE'));page=b.new_page(viewport={'width':1280,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
        if build_bytes:page.route('**/build.json',lambda route:route.fulfill(status=200,content_type='application/json',body=build_bytes))
        page.goto(url);page.wait_for_function('document.querySelector("#q-count").textContent.includes("product profiles")');page.wait_for_selector('#records tr')
        assert page.locator('#records tr').count()==12
        assert page.evaluate('document.querySelector("#records").compareDocumentPosition(document.querySelector("#qualification")) & Node.DOCUMENT_POSITION_FOLLOWING')
        assert str(len(data['rows'])) in page.locator('#q-count').inner_text()
        row=page.locator(f'tr[data-qualification-id="{named["row_id"]}"]');cells=row.locator('td').all_text_contents()
        assert named['procedure_id'] in cells[1] and '43–31/74' in cells[3] and '44–24/68' in cells[3] and '87–55/142' in cells[3]
        assert '7 total' in cells[4] and 'Not primary admission' in cells[4] and 'BLOCKED' in cells[5]
        page.select_option('#q-owner','C');page.select_option('#q-category','rec');page.select_option('#q-product','ACTUAL_LINE_DIRECTION:DIRECT_THRESHOLD');page.select_option('#q-floor','NOT_MET')
        assert page.locator('#qualification-records tr').count()>0
        assert '2 total' in page.locator('#qualification-records').inner_text()
        assert 'CLOSED_NO_INCREMENT' in page.locator('#qualification-records').inner_text()
        page.select_option('#q-floor','MET');assert page.locator('#qualification-records tr').count()==0
        page.select_option('#zone','UTC');assert 'UTC' in page.locator('#qualification-clock').inner_text()
        page.select_option('#zone','America/Chicago');assert 'CST' in page.locator('#qualification-clock').inner_text()
        dst=page.evaluate('()=>[new Intl.DateTimeFormat("en-US",{timeZone:"America/Chicago",hour:"numeric",hour12:false}).format(new Date("2026-11-01T06:30:00Z")),new Intl.DateTimeFormat("en-US",{timeZone:"America/Chicago",hour:"numeric",hour12:false}).format(new Date("2026-11-01T07:30:00Z"))]');assert dst==['01','01'] or dst==['1','1']
        for width in [320,390,1280]:
            page.set_viewport_size({'width':width,'height':900});page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');assert page.evaluate('document.documentElement.scrollWidth')<=width,(width,page.evaluate('document.documentElement.scrollWidth'))
        for panel in ['A','B','C','M']:
            page.select_option('#panel',panel);assert len(set(page.locator('#records tr').evaluate_all('rr=>rr.map(r=>r.dataset.category)')))==12
        page.select_option('#panel','C');assert '1532 graded,981 participation-unknown,0 pending' in page.locator('#details').inner_text()
        if commit:assert commit in page.locator('#served').inner_text()
        for mode in ['missing','corrupt']:
            ctx=b.new_context();bad=ctx.new_page();bad.route('**/data/qualification-5w.json.gz',lambda route:route.fulfill(status=503 if mode=='missing' else 200,body='unavailable' if mode=='missing' else 'corrupt'))
            bad.goto(url);bad.wait_for_function('document.querySelector("#qualification-status").textContent.includes("Qualification unavailable")')
            assert bad.locator('#qualification-records tr').count()==0
            ctx.close()
        b.close()
    assert not errors,errors
    receipt.write_text(json.dumps(dict(id='C-POST5W-RENDERED-PARITY-v1',checked_UTC=datetime.now(timezone.utc).isoformat(),URL=url,served_commit=commit,render_route='LOCAL_MIRROR_OF_TLS_VERIFIED_BYTE_IDENTICAL_PUBLIC_ASSETS' if build_bytes else 'DIRECT_URL',public_assets_receipt=assets_receipt.name if assets_receipt else None,direct_public_browser_HTTPS='CERTIFICATE_TRUST_BLOCKED;NO_TLS_BYPASS;BROAD_PERSISTENT_TRUST_CHANGE_REJECTED' if build_bytes else None,source_ledger_SHA256=data['ledger_SHA256'],asset_SHA256=hashlib.sha256((root/'data/qualification-5w.json.gz').read_bytes()).hexdigest(),all_twelve_actual_scorecard_first=True,CountA_exact_mean_own_sides=True,duration_not_primary_admission=True,C_new_values_two_actual_weeks=True,original_v4_still_forecast_only=True,category_owner_output_floor_filters=True,mobile_desktop_widths=[320,390,1280],Chicago_DST_UTC=True,HTTP_and_checksum_failure_closed=True,page_errors=errors,NFL_fits=0,new_forecasts=0),indent=2)+'\n')
    print('POST5W_BROWSER_PARITY_PASS',commit or 'LOCAL')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);p.add_argument('--commit');p.add_argument('--verified-public-build',type=Path);p.add_argument('--verified-assets-receipt',type=Path);a=p.parse_args();check(a.url,a.root,a.receipt,a.commit,a.verified_public_build,a.verified_assets_receipt)
