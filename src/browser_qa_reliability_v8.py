"""Read rendered counts/confidence/rank membership; no fits or NFL acquisition."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,root,receipt,commit=None):
    data=json.loads((root/'data/reliability-v8.json').read_text());checks=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url);page.wait_for_function('state.reliabilityHealthy');page.click('nav button[data-view=reliability]');assert page.locator('#view-reliability').is_visible();assert page.locator('#rel-category option').count()==12
        if commit:assert page.evaluate('state.build.served_commit')==commit
        for book in data['books']:
          page.select_option('#rel-book',book)
          for cat in ['pass_yd','rush_yd','rec','rec_yd']:
            page.select_option('#rel-category',cat);r=next(r for r in data['slices'] if r['book']==book and r['category']==cat and r['method']=='P3_DIRECT' and r['week']=='ALL' and r['role']=='ALL' and r['side']=='ALL');cells=page.locator('#rel-summary tbody tr').first.locator('td').all_text_contents();assert cells[0]==str(r['known_probability_rows']) and cells[3]==f"{100*r['mean_selected_confidence']:.1f}%" and cells[4]==f"{r['wins']}-{r['losses']} / {r['decided']} / {100*r['hit_rate']:.1f}%";assert cells[6].startswith(f"{r['half_scaled_UPO_Brier']:.6f}");assert page.locator('#rel-bins tbody tr').count()==10;checks.append(dict(book=book,category=cat,n=r['known_probability_rows'],confidence_hit_Brier_parity=True))
        page.select_option('#rel-book','pinnacle');page.select_option('#rel-category','pass_yd');page.select_option('#rel-week','2');page.select_option('#rel-side','UNDER');page.select_option('#rel-role','QB');assert page.locator('#rel-summary tbody tr').count()==1
        page.select_option('#rel-role','RB');assert 'N/A' in page.locator('#rel-missing').inner_text();page.select_option('#rel-role','ALL');page.select_option('#rel-week','ALL');page.select_option('#rel-side','ALL')
        for cat in ['pass_td','pass_cmp','pass_att','pass_int','rush_att','rush_rec_yd','anytime_td','fpts']:
            page.select_option('#rel-category',cat);assert page.locator('#rel-summary tbody tr').count()==0 and 'N/A' in page.locator('#rel-missing').inner_text()
        page.select_option('#rel-category','pass_yd')
        for method in ['P2_LAW','P3_DIRECT']:
          page.select_option('#rel-method',method)
          for variant in ['MIXED','OVER_ONLY','UNDER_ONLY']:
            page.select_option('#rank-side',variant)
            for k in ['6','10','20']:
                page.select_option('#rank-k',k);shown=page.locator('#rel-ranks tbody tr');expected=[r for r in data['rankings'] if r['book']=='pinnacle' and r['method']==method and r['scope']=='GLOBAL' and r['side_variant']==variant and r['K']==int(k)];assert shown.count()==len(expected)
                for i,r in enumerate(expected):assert shown.nth(i).get_attribute('data-ranking-id')==r['diagnostic_id'] and 'DIAGNOSTIC' in shown.nth(i).inner_text() and f"{r['wins']}-{r['losses']} / {r['decided']}" in shown.nth(i).inner_text()
        page.select_option('#rel-method','P2_WORKLOAD_V8');assert 'N/A' in page.locator('#rel-ranks').inner_text();page.select_option('#rank-scope','WITHIN_CATEGORY');assert page.locator('#rel-ranks tbody tr[data-ranking-id]').count()==2;assert 'P2_WORKLOAD_V8' in page.locator('#rel-workload').inner_text()
        page.screenshot(path=str(receipt.parent/'reliability-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390;page.screenshot(path=str(receipt.parent/'reliability-mobile.png'),full_page=True)
        ctx=browser.new_context();bad=ctx.new_page();bad.route('**/data/reliability-v8.json',lambda route:route.fulfill(status=503,body='unavailable'));bad.goto(url);bad.wait_for_function('document.querySelector("#reliability-state").textContent.includes("unavailable")');assert bad.locator('#rel-summary tbody tr').count()==0;ctx.close()
        ctx=browser.new_context();bad=ctx.new_page();bad.route('**/data/reliability-v8.json',lambda route:route.fulfill(status=200,body='{}'));bad.goto(url);bad.wait_for_function('document.querySelector("#reliability-state").textContent.includes("checksum mismatch")');assert bad.locator('#rel-ranks tbody tr').count()==0;ctx.close();browser.close();assert not errors,errors
    receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text(json.dumps(dict(id='C-RELIABILITY-BROWSER-v8',served_commit=commit,category_book_checks=checks,all12category_states=True,selected_side_confidence_masks_distinct=True,top6_10_20_own_side_global_and_category=True,unknowns_no_forcedK=True,no_executable_slate_claim=True,workload_passing_only=True,desktop_mobile=True,failure_closed=True,page_errors=errors,new_fits=0),indent=2)+'\n');print('RELIABILITY_BROWSER_PASS',len(checks))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);p.add_argument('--commit');x=p.parse_args();x.receipt.parent.mkdir(parents=True,exist_ok=True);check(x.url,x.root,x.receipt,x.commit)
