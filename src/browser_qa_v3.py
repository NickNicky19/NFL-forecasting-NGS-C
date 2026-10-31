"""Rendered parity for the separately retained v3 calibration/2025 views."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_qa_v2 import check as check_original

def check(url,root,receipt):
    check_original(url,root,receipt.with_name('SITE_ORIGINAL_VIEWS_V3.json'))
    m=json.loads((root/'data/manifest.json').read_text());checks=[]
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url,wait_until='networkidle');page.select_option('#family','CAL_SIGMOID_2025')
        for c in m['categories']:
            t=c['id'];page.select_option('#category',t);page.wait_for_function('t=>{const s=document.querySelector("#forecasts tbody tr")?.dataset.slot;return s?.includes("-"+t+"-")&&s.includes("CAL_SIGMOID_2025")}',arg=t)
            assert page.locator('#history').input_value()=='H-MULTI'
            assert page.locator('#history option[value="H-CURRENT"]').evaluate('(o)=>o.disabled')
            e=next(e for e in m['files'] if e['target']==t and e['family']=='CAL_SIGMOID_2025' and e['week']==7);rows=json.loads((root/'data'/e['file']).read_text())
            if t in ['rush_yd','rush_att']:rows=[r for r in rows if r['position']=='RB']
            tr=page.locator('#forecasts tbody tr').first;pid=tr.get_attribute('data-player-id');r=next(r for r in rows if r['player_id']==pid);cells=tr.locator('td').all_text_contents()
            assert cells[1]==('Event only' if t=='anytime_td' else 'N/A') and cells[2]==cells[1] and cells[3]=='N/A'
            line=float(page.locator('#threshold').input_value());v=r['p_over'][r['grid'].index(line)]
            assert cells[4]==page.evaluate('v=>(100*v).toFixed(1)+"%"',v)
            assert cells[5]==('Not offered' if t=='anytime_td' else page.evaluate('v=>(100*(1-v)).toFixed(1)+"%"',v))
            assert page.locator('#forecasts tbody tr').count()==len(rows)
            tr.click();assert '2025' in page.locator('#detail-body').inner_text() and 'calibration slope' in page.locator('#detail-body').inner_text();page.click('#close-detail')
            checks.append(dict(category=t,queries=len(rows),player_id=pid,rendered_probability_parity='EXACT',numerical_products_unavailable=True))
        page.click('nav button[data-view=results]')
        for policy in ['RAW_2025','RAW_RETAINED_2026','SIGMOID_2025_TRAINED']:
            page.select_option('#wave3-policy',policy);assert page.locator('#wave3-results tbody tr').count()==12
            for i,c in enumerate(m['categories']):
                t=c['id'];h='RB' if t in ['rush_yd','rush_att'] else 'PRIMARY' if t=='rush_rec_yd' else 'ALL'
                r=next(r for r in m['wave3_summary'] if r['target']==t and r['policy']==policy and r['horizon']==h)
                cells=page.locator('#wave3-results tbody tr').nth(i).locator('td').all_text_contents()
                assert cells[2]==str(r['outcomes'])+' / '+str(r['queries']) and cells[4]==page.evaluate('v=>v.toFixed(6)',r['grid_brier'])
            page.select_option('#wave3-period','W7');assert page.locator('#wave3-results tbody tr').count()==12
            page.select_option('#wave3-role','QB');assert page.locator('#wave3-results tbody tr').count()>0
            page.select_option('#wave3-role','DEFAULT');page.select_option('#wave3-period','ALL')
        page.locator('#wave3-results tbody tr').first.click();page.wait_for_selector('#detail-body h3');assert 'Reliability' in page.locator('#detail-body').inner_text();page.click('#close-detail')
        page.select_option('#wave3-policy','RAW_2025');page.select_option('#wave3-period','W18');assert page.locator('#wave3-results tbody tr').count()==12
        page.select_option('#wave3-policy','SIGMOID_2025_TRAINED');assert page.locator('#wave3-period').input_value()=='ALL'
        page.click('nav button[data-view=methods]');assert page.locator('#wave3-pairs tbody tr').count()==12
        assert page.locator('#wave3-pairs tbody').inner_text().count('Worse +')==10
        page.screenshot(path=str(receipt.parent/'site-v3-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390;page.screenshot(path=str(receipt.parent/'site-v3-mobile.png'),full_page=True)
        b.close();assert not errors
    receipt.write_text(json.dumps(dict(url=url,served=False,original_views_receipt='SITE_ORIGINAL_VIEWS_V3.json',calibrated_category_checks=checks,raw2025_and_both2026_datasets_parity=True,week_role_views=True,unsupported2026_weeks_disabled=True,all12_calibration_comparisons=True,ten_adverse_changes_visible=True,calibration_reliability_visible=True,raw_forecasts_not_relabelled=True,no_page_errors=not errors,mobile390_and_desktop1440=True,new_fits=0),indent=2)+'\n');print('BROWSER_V3_QA_PASS',len(checks))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();check(a.url,a.root,a.receipt)
