"""Rendered future-data acceptance; no acquisition, fits or fabricated outcomes."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,root,receipt,expected_commit=None):
    m=json.loads((root/'data/forward-manifest.json').read_text());checks=[];receipt.parent.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url,wait_until='networkidle');page.wait_for_function('state.forwardHealthy');assert page.locator('#view-upcoming').is_visible();assert page.locator('#upcoming-categories button').count()==12
        if expected_commit:assert page.evaluate('state.build.served_commit')==expected_commit
        for c in m['categories']:
            target=c['id'];page.select_option('#upcoming-category',target);page.wait_for_function('t=>state.forwardHealthy&&state.forwardRows[0]?.category===t',arg=target)
            entry=next(x for x in m['files'] if x['category']==target);rows=json.loads((root/'data'/entry['file']).read_text());expected=page.evaluate('state.forwardRows.filter(r=>futureEligible(r)).length');assert page.locator('#upcoming tbody tr').count()==expected
            if not expected:checks.append(dict(category=target,stored_rows=len(rows),currently_unplayed_rows=0,started_games_suppressed=True));continue
            tr=page.locator('#upcoming tbody tr').first;identity=tr.get_attribute('data-forecast-id');r=next(x for x in rows if x['forecast_id']==identity);cells=tr.locator('td').all_text_contents();event=target=='anytime_td'
            assert cells[1]==('Event only' if event else page.evaluate('v=>v.toFixed(2)',r['mean']));assert cells[2]==('Event only' if event else page.evaluate('v=>v.toFixed(2)',r['median']))
            assert cells[4]==(page.evaluate('v=>(100*v).toFixed(1)+"%"',r['event_probability']) if event else 'Prop line unavailable')
            assert cells[5]=='Forecast only—prop line unavailable' and cells[6]=='Unavailable' and cells[7]=='N/A · no line'
            assert page.evaluate('()=>[...document.querySelectorAll("#upcoming tbody tr")].every(tr=>futureEligible(state.forwardRows.find(r=>r.forecast_id===tr.dataset.forecastId)))')
            tr.click();detail=page.locator('#detail-body').inner_text();assert 'Feature-information cutoff' in detail and 'GitHub server persistence' in detail and r['model_id'] in detail and r['scoring_contract_id'] in detail
            assert 'future actuals were not required' in detail;page.click('#close-detail')
            checks.append(dict(category=target,stored_rows=len(rows),currently_unplayed_rows=expected,representative_forecast_id=identity,typed_value_parity='PASS',line_venue_probability_unavailable='PASS'))
        page.select_option('#upcoming-category','rush_yd');page.wait_for_function('()=>state.forwardHealthy&&state.forwardRows[0]?.category==="rush_yd"');page.select_option('#upcoming-role','QB');assert page.locator('#upcoming tbody tr').count()==page.evaluate('state.forwardRows.filter(r=>futureEligible(r)&&r.position==="QB").length');page.select_option('#upcoming-role','RB');assert page.locator('#upcoming tbody tr').count()==page.evaluate('state.forwardRows.filter(r=>futureEligible(r)&&r.position==="RB").length');page.select_option('#upcoming-role','ALL')
        page.fill('#upcoming-search','NOT_A_REAL_PLAYER');assert page.locator('#upcoming tbody tr').count()==0 and page.locator('#upcoming-empty').is_visible();page.fill('#upcoming-search','')
        page.select_option('#timezone','America/Chicago');dst=page.evaluate('()=>[clock("2026-11-01T06:30:00Z"),clock("2026-11-01T07:30:00Z"),clock("2026-11-01T18:00:00Z")]');assert 'CDT' in dst[0] and 'CST' in dst[1] and '12:00:00 PM' in dst[2]
        page.select_option('#timezone','UTC');assert all('UTC' in text for text in page.locator('#upcoming-game option').all_text_contents()[1:]);page.locator('#upcoming tbody tr').first.click();assert 'UTC' in page.locator('#detail-body').inner_text();page.click('#close-detail');page.select_option('#timezone','America/Chicago');assert all('America/Chicago' in text for text in page.locator('#upcoming-game option').all_text_contents()[1:])
        assert page.evaluate('()=>state.forwardRows.every(r=>!futureEligible(r,Date.parse(r.kickoff_UTC)))')
        assert page.evaluate('()=>state.forwardRows.every(r=>!sourceCurrent(r,Date.parse(r.status_observed_UTC)+1800001))')
        page.evaluate('()=>{window.savedNow=Date.now;Date.now=()=>Date.parse("2026-11-04T00:00:00Z");renderForward();}');assert page.locator('#upcoming tbody tr').count()==0 and 'started-game rows suppressed' in page.locator('#upcoming-count').inner_text();page.evaluate('()=>{Date.now=window.savedNow;renderForward();}')
        page.click('nav button[data-view=prospective]');assert page.locator('#prospective-results tbody tr').count()==12;assert 'Graded outcomes: 0 (pending)' in page.locator('#prospective-summary').inner_text();assert 'NO_QUALIFIED_SIX_LEG_ENTRY' in page.locator('#view-prospective').inner_text();assert 'no qualified historical offer export' not in page.locator('#view-prospective').inner_text();page.click('#historical-accuracy-link');assert page.locator('#view-accuracy').is_visible()
        page.click('nav button[data-view=forecasts]');assert 'Synthetic Diagnostics' in page.locator('#view-forecasts h2').inner_text();assert page.locator('#threshold').is_visible() and not page.locator('#view-upcoming').is_visible()
        page.click('nav button[data-view=upcoming]');assert not page.locator('#threshold').is_visible();page.select_option('#upcoming-category','pass_yd');page.wait_for_function('()=>state.forwardHealthy&&state.forwardRows[0]?.category==="pass_yd"')
        page.screenshot(path=str(receipt.parent/'future-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390;page.screenshot(path=str(receipt.parent/'future-mobile.png'),full_page=True)
        context=browser.new_context();bad=context.new_page();bad.route('**/data/forward/pass_yd.json',lambda route:route.fulfill(status=503,body='unavailable'));bad.goto(url);bad.wait_for_selector('#upcoming-empty:not([hidden])');assert bad.locator('#upcoming tbody tr').count()==0 and 'HTTP503' in bad.locator('#upcoming-empty').inner_text().replace(' ','');context.close()
        context=browser.new_context();bad=context.new_page();entry=next(x for x in m['files'] if x['category']=='pass_yd');rows=json.loads((root/'data'/entry['file']).read_text());rows[0]['mean']=999999;bad.route('**/data/'+entry['file'],lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(rows)));bad.goto(url);bad.wait_for_selector('#upcoming-empty:not([hidden])');assert 'checksum mismatch' in bad.locator('#upcoming-empty').inner_text() and bad.locator('#upcoming tbody tr').count()==0;context.close()
        browser.close();assert not errors
    receipt.write_text(json.dumps(dict(id='C-FUTURE-RENDERED-ACCEPTANCE-v4',URL=url,expected_served_commit=expected_commit,category_checks=checks,default_upcoming=True,synthetic_diagnostics_separate=True,no_synthetic_defaults_in_props=True,all_prospective_results_pending=True,server_clock_and_feature_clock_distinct=True,role_search_masks=True,started_games_suppressed=True,stale_status_fail_closed=True,Chicago_DST_repeated_hour_disambiguated=dst,desktop1440_mobile390=True,no_global_overflow=True,HTTP_failure_closed=True,checksum_failure_closed=True,page_errors=errors,new_fits=0,tests_are='UI/software checks, not outcomes or wins'),indent=2)+'\n');print('FORWARD_BROWSER_ACCEPTANCE_PASS',len(checks))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);p.add_argument('--commit');a=p.parse_args();check(a.url,a.root,a.receipt,a.commit)
