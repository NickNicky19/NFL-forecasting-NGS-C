"""Render original grade overlays and all three saved ranking procedures, without fits."""
import argparse,gzip,json
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,root,receipt,commit=None):
    grades=json.loads((root/'data/week8-results-v9.json').read_bytes());top=json.loads((root/'data/topk-reference-v9.json').read_bytes());members=json.loads(gzip.decompress((root/top['membership']['path']).read_bytes()));checked=[];errors=[]
    receipt.parent.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url);page.wait_for_function('state.week8Healthy&&state.topkHealthy');page.click('nav button[data-view=prospective]')
        if commit:assert page.evaluate('state.build.served_commit')==commit
        assert '1441 graded' in page.locator('#prospective-summary').inner_text();assert '873 unknown' in page.locator('#prospective-summary').inner_text();assert '199 pending' in page.locator('#prospective-summary').inner_text()
        assert 'NOT ESTABLISHED' in page.locator('#week8-leaders').inner_text()
        for product in ['ORIGINAL_ACTUAL_LINE','RETROSPECTIVE_ACTUAL_LINE_REPLAY']:
          page.select_option('#week8-prop-product',product)
          for method in ['P2_EXACT_LINE_SELECTOR-v4.1','P1_MEAN','P1_MEDIAN']:
            page.select_option('#week8-prop-method',method);rows=page.locator('#prospective-results tbody tr');assert rows.count()==12
            assert all('N/A / 0 / N/A' in rows.nth(i).inner_text() and 'No qualified lines' in rows.nth(i).inner_text() for i in range(12))
        for i,c in enumerate(grades['categories']):
            tr=page.locator('#week8-numerical tbody tr').nth(i);assert tr.get_attribute('data-week8-category')==c['category'];values=tr.locator('td').all_text_contents();assert values[2]==f"{c['issued']} / {c['completed_game_forecasts']} / {c['graded']}";assert values[3]==f"{c['unknown_participation']} / {c['pending']}";assert values[4]==('N/A' if c['median_MAE'] is None else f"{c['median_MAE']:.4f}");checked.append(dict(category=c['category'],issued=c['issued'],graded=c['graded'],median_MAE=c['median_MAE']))
        page.locator('#week8-numerical tbody tr').first.click();row=page.locator('#detail-body tr[data-week8-forecast-id]').first;identity=row.get_attribute('data-week8-forecast-id');stored=next(r for r in grades['rows'] if r['forecast_id']==identity);assert stored['name'] in row.inner_text() and stored['state'] in row.inner_text() and 'prop line unavailable' in row.inner_text();page.click('#close-detail')
        page.select_option('#week8-role','QB');qb=next(r for r in grades['groups'] if r['category']=='rush_yd' and r['role']=='QB' and r['group']=='ORIGINAL_PREGAME_ROLE');assert f"{qb['issued']} / {qb['completed_game_forecasts']} / {qb['graded']}" in page.locator('#week8-numerical tr[data-week8-category=rush_yd]').inner_text();page.select_option('#week8-role','ALL')
        assert page.locator('#week8-status tbody tr').count()==13;assert 'Chicago–Seattle pending' in page.locator('#prospective-summary').inner_text();assert '0.158110' in page.locator('#week8-event').inner_text()
        page.select_option('#timezone','UTC');assert 'UTC' in page.locator('#week8-clock').inner_text();page.select_option('#timezone','America/Chicago');assert 'CST' in page.locator('#week8-clock').inner_text();dst=page.evaluate('()=>[clock("2026-11-01T06:30:00Z"),clock("2026-11-01T07:30:00Z")]');assert 'CDT' in dst[0] and 'CST' in dst[1]
        page.screenshot(path=str(receipt.parent/'week8-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390;page.screenshot(path=str(receipt.parent/'week8-mobile.png'),full_page=True);page.set_viewport_size({'width':1440,'height':1000})
        page.click('nav button[data-view=reliability]');rank_checks=[]
        for book in ['pinnacle','draftkings','fanduel']:
          page.select_option('#tk-book',book)
          for week in ['ALL','2','3']:
            page.select_option('#tk-week',week)
            for side in ['MIXED','OVER_ONLY','UNDER_ONLY']:
              page.select_option('#tk-side',side)
              for k in ['6','10','20']:
                page.select_option('#tk-k',k);rr=(top['cumulative'] if week=='ALL' else top['weekly']);wanted=[r for r in rr if r['book']==book and r['scope']=='GLOBAL' and r['side_variant']==side and r['K']==int(k) and (week=='ALL' or r['week']==int(week))];trs=page.locator('#tk-results tbody tr');assert trs.count()==3
                for i,r in enumerate(wanted):assert trs.nth(i).get_attribute('data-tk-method')==r['method'] and f"{r['wins']}-{r['losses']} / {r['decided']}" in trs.nth(i).inner_text() and f"{100*r['mean_confidence_decided']:.1f}%" in trs.nth(i).inner_text()
                rank_checks.append((book,week,side,int(k)))
        page.select_option('#tk-book','pinnacle');page.select_option('#tk-week','2');page.select_option('#tk-side','MIXED');page.select_option('#tk-k','6');page.locator('#tk-results tr[data-tk-method=P3_DIRECT]').click();page.wait_for_selector('#detail-body tr[data-tk-record]');id='TKR9-pinnacle-W2-P3_DIRECT-GLOBAL-ALL-MIXED-K6';wanted=[r for r in members if r['diagnostic_id']==id];trs=page.locator('#detail-body tr[data-tk-record]');assert [trs.nth(i).get_attribute('data-tk-record') for i in range(trs.count())]==[r['record_id'] for r in wanted];assert 'Not an executable ticket' in page.locator('#detail-body').inner_text();page.click('#close-detail')
        page.select_option('#tk-scope','WITHIN_CATEGORY');page.select_option('#tk-category','rush_yd');page.select_option('#tk-side','OVER_ONLY');assert page.locator('#tk-results tbody tr').count()==3
        page.locator('#tk-results').scroll_into_view_if_needed();page.screenshot(path=str(receipt.parent/'topk-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390;page.screenshot(path=str(receipt.parent/'topk-mobile.png'),full_page=True)
        for path,key,selector in [('week8-results-v9.json','week8Healthy','#prospective-results tbody tr'),('topk-reference-v9.json','topkHealthy','#tk-results tbody tr')]:
          for failure in ['HTTP503','CHECKSUM']:
            ctx=browser.new_context();bad=ctx.new_page();bad.route('**/data/'+path,lambda route,f=failure:route.fulfill(status=503 if f=='HTTP503' else 200,body='unavailable' if f=='HTTP503' else '{}'));bad.goto(url);target='#prospective-summary' if key=='week8Healthy' else '#tk-state';bad.wait_for_function('s=>document.querySelector(s).textContent.includes("unavailable")',arg=target);assert not bad.evaluate('state.'+key) and bad.locator(selector).count()==0;ctx.close()
        browser.close();assert not errors,errors
    receipt.write_text(json.dumps(dict(id='C-WEEK8-AND-TOPK-RENDERED-v9',URL=url,served_commit=commit,category_checks=checked,actualprop_12categories_3methods_2products_NA=True,grade_overlay_original_unmodified=True,rank_variant_checks=rank_checks,three_own_procedure_membership_parity=True,pending_unknown_zero_distinct=True,Chicago_DST=dst,desktop_mobile=True,HTTP_and_checksum_failure_closed=True,precise_joint_or_payout_claim=False,new_NFL_fits=0,page_errors=errors),indent=2)+'\n');print('WEEK8_TOPK_RENDERED_PASS',len(checked),len(rank_checks))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);p.add_argument('--commit');x=p.parse_args();check(x.url,x.root,x.receipt,x.commit)
