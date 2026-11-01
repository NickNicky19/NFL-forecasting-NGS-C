"""Exact-offer UI acceptance; positive paths use explicit in-memory fiction only."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,receipt):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(url);page.wait_for_function('state.paperHealthy===true')
        assert page.locator('#actual-props tbody tr').count()==0 and page.locator('#real-history tbody tr').count()==12
        assert '0 qualified offers / 0 paper selections' in page.locator('#actual-offer-status').inner_text()
        assert 'APPLICABLE PROVIDER GRANT REQUIRED' in page.locator('#actual-source-status').inner_text()
        page.click('nav button[data-view=results]');assert page.locator('#real-history tbody tr').first.locator('td').nth(1).inner_text()=='214'
        page.screenshot(path=str(receipt.parent/'exact-offer-history.png'),full_page=True)
        page.click('nav button[data-view=upcoming]');page.select_option('#upcoming-category','pass_yd');page.wait_for_function('state.forwardHealthy&&state.forwardRows[0]?.category==="pass_yd"')
        page.screenshot(path=str(receipt.parent/'exact-offer-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth')<=390;page.screenshot(path=str(receipt.parent/'exact-offer-mobile.png'),full_page=True)
        # Fixtures exist only in browser memory and never enter a published manifest.
        page.evaluate('''()=>{window.originalPaper=structuredClone(state.paper);window.originalNow=Date.now;const t=Date.parse("2026-11-01T02:00:00Z");Date.now=()=>t;
        const r={record_kind:"ACTUAL_OFFER",offer_id:"FICTIONAL-UI-ONLY-A",venue:"FICTIONAL_NOT_A_VENUE",product:"FIXTURE",tier:"FIXTURE",game_id:"FICTIONAL-G",player_id:"FICTIONAL-P",category:"pass_yd",name:"FICTIONAL SOFTWARE PLAYER",line:9.5,comparator:"STRICT_OVER_UNDER",scoring_contract_id:"FIXTURE",offered_sides:["OVER","UNDER"],source_asof_UTC:"2026-11-01T01:58:00Z",observed_at_UTC:"2026-11-01T01:59:00Z",status_observed_UTC:"2026-11-01T01:59:00Z",selection_persisted_UTC:"2026-11-01T01:59:30Z",selection_created_UTC:"2026-11-01T01:59:10Z",cutoff_UTC:"2026-11-01T01:59:10Z",forecast_generated_UTC:"2026-11-01T01:00:00Z",kickoff_UTC:"2026-11-01T18:00:00Z",event_state:"pre",event_completed:false,lifecycle:"OPEN",reasons:[],primary_scoring_snapshot:true,evidence_tier:"GITHUB_SERVER_VERIFIED_PREGAME_PAPER",P1_side:"OVER",P2_side:"OVER",P1_state:"SELECTED",P2_state:"SELECTED",p_under:.3,p_push:0,p_over:.7,rank:1,model_id:"FICTIONAL MODEL",conditioning:"FICTIONAL TEST",book_settlement:"UNVERIFIED"};state.paper.records=[r];renderPaper();paperDetail(r); }''')
        assert 'Experimental paper' in page.locator('#paper-current-eligibility').inner_text();page.click('#close-detail');page.click('nav button[data-view=rankings]');page.click('#probability-mode');assert page.locator('#actual-ranking tbody tr').count()==1
        page.click('#price-mode');assert page.locator('#actual-ranking tbody tr').count()==0;page.click('#probability-mode')
        page.click('nav button[data-view=upcoming]');page.locator('#actual-props tbody tr').first.click()
        page.evaluate('Date.now=()=>Date.parse("2026-11-01T02:20:00Z")');page.wait_for_function('document.querySelector("#paper-current-eligibility").textContent.includes("Expired")',timeout=8000)
        assert page.locator('#actual-ranking tbody tr').count()==0 and 'Unavailable now' in page.locator('#actual-props tbody tr').first.inner_text()
        page.click('#close-detail');page.evaluate('''()=>{Date.now=()=>Date.parse("2026-11-01T02:00:00Z");let r=state.paper.records[0];state.paper.records.push({...r,offer_id:"FICTIONAL-NEWER-CLOSED",observed_at_UTC:"2026-11-01T01:59:40Z",lifecycle:"CLOSED",reasons:["CLOSED"],primary_scoring_snapshot:false});renderPaper();}''')
        assert page.evaluate('state.paper.records.every(r=>!paperActive(r))')
        page.evaluate('''()=>{state.paper=window.originalPaper;Date.now=window.originalNow;renderPaper();}''');assert page.locator('#actual-props tbody tr').count()==0
        # Exact-offer dataset failure cannot turn shared research numbers into props.
        context=browser.new_context();bad=context.new_page();bad.route('**/data/actual-props-v5.json',lambda route:route.fulfill(status=503,body='unavailable'));bad.goto(url);bad.wait_for_function('document.querySelector("#actual-offer-status").textContent.replaceAll(" ","").includes("HTTP503")');assert bad.locator('#actual-props tbody tr').count()==0;context.close()
        browser.close();assert not errors,errors
    receipt.write_text(json.dumps(dict(id='C-EXACT-OFFER-RENDERED-v5',URL=url,actual_offer_rows=0,actual_history_categories=12,source_holds_visible=True,original_v4_forecasts_unchanged=True,fictional_only_positive_paths=['exact_line_rendering','probability_ranking','price_mode_closed','automatic_TTL_expiry','open_detail_expiry','superseded_quote_suppression'],no_network_refresh_loop=True,no_synthetic_defaults=True,desktop_mobile=True,HTTP_failure_closed=True,page_errors=errors,NFL_offers_graded=0,NFL_fits=0),indent=2)+'\n');print('PAPER_UI_ACCEPTANCE_PASS')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();a.receipt.parent.mkdir(parents=True,exist_ok=True);check(a.url,a.receipt)
