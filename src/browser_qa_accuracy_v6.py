"""Actual-prop headline/leader parity. No NFL acquisition, fitting or grading."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,root,receipt,commit=None):
    m=json.loads((root/'data/actual-accuracy-v6.json').read_text());v=next(v for v in m['views'] if v['period']=='2026_W1_W7' and v['method']=='PRIMARY');errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url);page.wait_for_function('state.accuracyHealthy&&state.paperHealthy&&state.forwardHealthy')
        assert page.locator('#view-accuracy').is_visible() and page.locator('nav button').first.get_attribute('data-view')=='accuracy'
        assert page.locator('#accuracy-message').inner_text()==m['message']
        assert ('N/A' in page.locator('#accuracy-last-graded').inner_text())==(m['last_graded_update_UTC'] is None)
        assert page.locator('#accuracy-headline tbody tr').count()==12
        for i,c in enumerate(v['cells']):
            cells=page.locator('#accuracy-headline tbody tr').nth(i).locator('td').all_text_contents();assert cells[0]==c['label'] and c['method_version'] in cells[1]
            expected=[f"{c[s]['wins']}-{c[s]['losses']} / {c[s]['decided']} / {100*c[s]['rate']:.1f}%" if c[s]['decided'] else 'N/A / 0 / N/A' for s in ['OVER','UNDER','COMBINED']]
            expected_coverage=f"{c['eligible_offers']} / {c['scored_offers']}"+(f" · {c['strata_count']} disclosed strata" if c['strata_count']>1 else '')
            assert cells[2:5]==expected;assert cells[5:7]==[expected_coverage,f"{c['games']} / {c['weeks']}"];assert c['evidence_tier']==cells[8]
            if c['eligible_offers']:
                page.locator('#accuracy-headline tbody tr').nth(i).click();shown=page.locator('#detail-body tr[data-accuracy-record-id]').first;identity=shown.get_attribute('data-accuracy-record-id');r=next(r for r in m['records'] if r['record_id']==identity);values=shown.locator('td').all_text_contents()
                assert r['game_id'] in values[0] and r['venue'] in values[1] and str(r['line']) in values[1]
                expected_probs=' / '.join(f"{100*r['p_'+s]:.1f}%" for s in ['under','push','over']) if r['status']!='UNAVAILABLE_FORECAST' else 'N/A / N/A / N/A'
                assert values[3]==expected_probs
                assert r['status'] in values[4];page.click('#close-detail')
        leader_text=page.locator('#accuracy-leaders').inner_text()
        for group in v['leader_groups']:
          for key,leader in group['leaders'].items():
            for r in leader.get('observed',[]):assert r['category'] in leader_text and r['method_version'] in leader_text and f"{r['wins']}-{r['losses']} / {r['decided']}" in leader_text
        if not m['retained_rows']:assert leader_text.count('NOT ESTABLISHED')==4
        assert page.evaluate('document.querySelector("#view-accuracy").compareDocumentPosition(document.querySelector(".stats")) & Node.DOCUMENT_POSITION_FOLLOWING')
        page.locator('#accuracy-headline tbody tr').first.click();detail=page.locator('#detail-body').inner_text();assert 'OVER selected' in detail and 'Intentional abstentions' in detail;page.click('#close-detail')
        page.select_option('#accuracy-method','P1_MEAN');assert 'P1_MEAN' in page.locator('#accuracy-headline tbody tr').first.inner_text();page.select_option('#accuracy-method','P1_MEDIAN');assert 'P1_MEDIAN' in page.locator('#accuracy-headline tbody tr').first.inner_text()
        page.select_option('#accuracy-policy','GLOBAL_TOP6_MIXED');page.locator('#accuracy-headline tbody tr').first.click();assert 'Frozen slate' in page.locator('#detail-body').inner_text();page.click('#close-detail');page.select_option('#accuracy-policy','ALL_ELIGIBLE_OFFERS')
        for period in ['2026_W1','2025','2026_W8_PLUS']:
            page.select_option('#accuracy-period',period);assert page.locator('#accuracy-headline tbody tr').count()==12
        assert page.locator('#accuracy-tier').input_value()=='GENUINE_PROSPECTIVE_W8_PLUS';page.select_option('#accuracy-period','2026_W1_W7');page.select_option('#accuracy-method','PRIMARY')
        page.screenshot(path=str(receipt.parent/'accuracy-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390;page.screenshot(path=str(receipt.parent/'accuracy-mobile.png'),full_page=True)
        page.select_option('#timezone','UTC');page.select_option('#timezone','America/Chicago');assert page.evaluate('clock("2026-11-01T06:30:00Z").includes("CDT")&&clock("2026-11-01T07:30:00Z").includes("CST")')
        page.click('nav button[data-view=upcoming]');assert page.locator('#view-upcoming').is_visible();assert page.locator('#actual-props tbody tr').count()==0
        if commit:assert page.evaluate('state.build.served_commit')==commit
        ctx=browser.new_context();bad=ctx.new_page();bad.route('**/data/actual-accuracy-v6.json',lambda route:route.fulfill(status=503,body='unavailable'));bad.goto(url);bad.wait_for_function('document.querySelector("#accuracy-message").textContent.includes("unavailable")');assert bad.locator('#accuracy-headline tbody tr').count()==0 and 'NOT ESTABLISHED' in bad.locator('#accuracy-leaders').inner_text();ctx.close()
        ctx=browser.new_context();bad=ctx.new_page();bad.route('**/data/actual-accuracy-v6.json',lambda route:route.fulfill(status=200,content_type='application/json',body='{}'));bad.goto(url);bad.wait_for_function('document.querySelector("#accuracy-message").textContent.includes("checksum mismatch")');assert bad.locator('#accuracy-headline tbody tr').count()==0;ctx.close()
        browser.close();assert not errors,errors
    receipt.write_text(json.dumps(dict(id='C-ACTUAL-ACCURACY-RENDERED-v6',URL=url,served_commit=commit,default_accuracy_first=True,headline_categories=12,retained_row_parity=True,observed_leaders_match_ledger=True,evidence_supported_leaders_not_established=True,mean_median_distinct=True,periods_tiers_separate=True,TopK_missing_membership_unavailable=True,source_facets_separate=True,last_graded_clock_not_build_clock=True,Chicago_DST=True,desktop_mobile=True,HTTP_and_checksum_failure_closed=True,page_errors=errors,NFL_unique_offers=len({r['offer_id'] for r in m['records']}),primary_decided=sum(c['COMBINED']['decided'] for c in v['cells']),new_NFL_fits=0),indent=2)+'\n');print('ACTUAL_ACCURACY_BROWSER_PASS')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);p.add_argument('--commit');a=p.parse_args();a.receipt.parent.mkdir(parents=True,exist_ok=True);check(a.url,a.root,a.receipt,a.commit)
