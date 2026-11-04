"""Rendered canonical-row parity, timezone and fail-closed checks for C's page."""
import argparse
import hashlib
import json
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from verified_https_browser import verified_public_transport

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url',required=True)
    p.add_argument('--commit')
    p.add_argument('--receipt',required=True,type=Path)
    args = p.parse_args()
    base = args.url.rstrip('/')+'/'
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True,args=['--no-sandbox'])
        transport = verified_public_transport(base) if base.startswith('https://') else nullcontext([])
        with transport as received:
            for width,height in [(1440,960),(390,844)]:
                context = browser.new_context(viewport={'width':width,'height':height})
                page = context.new_page()
                errors = []
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'championship.html',wait_until='networkidle')
                page.wait_for_selector('#records tr')
                assert page.locator('#records tr').count()==12
                assert '521-396/917/56.82%' in page.locator('[data-category="rec"]').inner_text()
                assert '83-60/143/58.04%' in page.locator('[data-category="pass_int"]').inner_text()
                assert 'N/A' in page.locator('[data-category="anytime_td"]').inner_text()
                chicago = page.locator('#clock').inner_text()
                assert 'CST' in chicago
                page.select_option('#zone','UTC')
                utc = page.locator('#clock').inner_text()
                assert chicago != utc and 'UTC' in utc
                page.select_option('#panel','B')
                assert page.locator('#records tr').count()==12
                assert '56-45/101/55.45%' in page.locator('[data-category="rec"]').inner_text()
                page.select_option('#panel','C')
                assert page.locator('#records tr').count()==12
                assert '1532 graded,981 participation-unknown,0 pending' in page.locator('#details').inner_text()
                assert 'N/A — forecast only' in page.locator('[data-category="pass_yd"]').inner_text()
                served = page.locator('#served').inner_text()
                if args.commit:
                    assert args.commit in served
                assert not errors,errors
                results.append(dict(viewport=[width,height],category_rows=12,A_representative_counts=True,B_original_counts=True,C_final_not_prop=True,Chicago_DST_CST_and_UTC=True,served_commit_text=served,page_errors=errors))
                context.close()
            # Deliberately corrupt only the local browser response; no server data changes.
            context = browser.new_context(viewport={'width':390,'height':844})
            page = context.new_page()
            page.route('**/data/championship-period-v2.json',lambda route:route.fulfill(status=200,body='{}',content_type='application/json'))
            page.goto(base+'championship.html',wait_until='networkidle')
            assert page.locator('#records tr').count()==0
            assert 'checksum mismatch' in page.locator('#error').inner_text()
            results.append(dict(corrupt_projection='FAIL_CLOSED_NO_ROWS_OR_SYNTHETIC_DEFAULTS'))
            context.close()
            if base.startswith('https://'):
                for artifact in ['championship.html','championship.js','style.css','data/championship-period-v2.json']:
                    matches = [r for r in received if r['path']==artifact]
                    assert matches and all(r['status']==200 and r['SHA256']==hashlib.sha256((ROOT/'docs'/artifact).read_bytes()).hexdigest() for r in matches), ('SERVED_ASSET_PARITY',artifact)
                results.append(dict(exact_asset_parity=['championship.html','championship.js','style.css','data/championship-period-v2.json']))
        browser.close()
    receipt = dict(id='C-PERIOD-WEBSITE-VERIFICATION-v2-1',verified_UTC=datetime.now(timezone.utc).isoformat(),url=base,expected_commit=args.commit,checks=results,verified_system_TLS_transport=base.startswith('https://'),native_Chromium_TLS='Not asserted; managed browser uses verified system TLS transport for public responses',received_responses=received,new_NFL_outcomes_or_selections=0,scope='Rendered count parity/status/timezone/integrity only; no predictive improvement or A/B common acknowledgement')
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print('PERIOD_RENDERED_PARITY_PASS',len(results),base)


if __name__=='__main__':
    main()
