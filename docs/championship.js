"use strict";
const select=s=>document.querySelector(s);
let data,build,shared;
const labels={pass_yd:"Passing Yards",pass_td:"Passing TDs",pass_cmp:"Completions",pass_att:"Pass Attempts",pass_int:"Interceptions Thrown",rush_yd:"Rushing Yards",rush_att:"Rush Attempts",rec:"Receptions",rec_yd:"Receiving Yards",rush_rec_yd:"Rush + Rec Yards",anytime_td:"Anytime TD",fpts:"Fantasy Points (nick-chart-ppr-v1)"};
const pct=x=>typeof x==="number"?(100*x).toFixed(2)+"%":"N/A";
const rec=x=>x?.decided?`${x.wins}-${x.losses}/${x.decided}/${pct(x.rate)}`:"N/A — no decided selections";
function clock(x){return x?new Intl.DateTimeFormat("en-US",{timeZone:select("#zone").value,dateStyle:"medium",timeStyle:"long"}).format(new Date(x)):"Unknown";}
function renderShared(panel){
 const p=shared.panels[panel],body=select("#records");select("#details").textContent=p.details;select("#leaders").textContent=p.leaders;
 for(const [category,label] of Object.entries(labels)){
  const rows=p.rows.filter(r=>r.category===category);
  for(const r of rows.length?rows:[null]){
   let cells;
   if(!r?.COMBINED?.decided)cells=[label,"N/A — no qualified matching market/procedure",r?.period||"Unsupported in this panel","N/A","N/A","N/A","Unknown","N/A","N/A","NOT ESTABLISHED","No invented threshold, side or fantasy contract"];
   else{
    const own=r.OVER?.decided&&r.UNDER?.decided?(r.OVER.rate===r.UNDER.rate?"Own sides tied":(r.OVER.rate>r.UNDER.rate?"Over":"Under")+" higher by "+(100*Math.abs(r.OVER.rate-r.UNDER.rate)).toFixed(2)+"pp; different selected pools"):"One side only";
    const states=r.full_system?.states||r.states||{};
    const ci=r.uncertainty||r.full_system?.uncertainty;
    let uncertainty=ci?.low!==undefined?`${pct(ci.low)}–${pct(ci.high)} · ${ci.kind}`:"Owner-local or paired sensitivity in canonical records; limited clusters";
    const extra=panel==="M"?`Brier ${r.Brier??"N/A"}; no new-value improvement`:panel==="E"?`Equal-season ${pct(r.COMBINED.equal_season_rate)}; selected-pool constants in report`:"Exact masks/strong controls and ties in canonical report";
    cells=[label,r.method,r.period,rec(r.OVER),rec(r.UNDER),rec(r.COMBINED),`${r.eligible??"Unknown"}/${r.selected??r.COMBINED.selected}/${r.COMBINED.decided}`,r.games??"See season source",extra,uncertainty+" · "+own,`Timing-unverified actual-line diagnostic; ${r.unavailable??"unknown"} unavailable; states ${JSON.stringify(states)}; venue settlement unverified`];
   }
   const tr=document.createElement("tr");tr.dataset.category=category;if(r?.method)tr.dataset.method=r.method;
   for(const value of cells){const td=document.createElement("td");td.textContent=String(value);tr.append(td);}body.append(tr);
  }
 }
 select("#clock").textContent="Shared evidence prepared "+clock(shared.prepared_UTC)+". Build/publication clocks do not authenticate historical quotes. No new original C actual-line selections.";
 select("#served").textContent="Actually served commit: "+build.served_commit+" · protocol "+shared.protocol+" · A/B acknowledgements received; temporal/private-inference limits remain.";
}
function render(){
 const panel=select("#panel").value,body=select("#records");body.replaceChildren();
 if(shared.panels[panel]){renderShared(panel);return;}
 select("#leaders").textContent=panel==="A"?"Raw A W1–7 Over leader: interceptions, Leaf median 4–1/5 (80%). Under: interceptions, CatBoost 4–1/5 and Leaf mean 8–2/10 (80%), tied. Combined: passing TDs, Count A legacy/mean 87–55/142 (61.27%), tied. No evidence-supported future champion.":panel==="B"?"Original-selected Week8 diagnostic: original205–210/415 (49.40%) versus always-Under224–191/415 (53.98%), +19 wins to the constant control. Not a proposed Under policy or common-board championship.":"Over, Under and combined actual-prop leaders: NOT ESTABLISHED. C issued no qualified actual-line selections; these are forecast-only grades.";
 select("#details").textContent=panel==="A"?"A's highest observed complete point procedures on a timing-unverified actual-line panel. Requested W1–8; actually W1–7. Exact history memory needs producer binding; it is not guessed from a method name. PassingQB; the335-offer carry panel is mixedposition, with239RBoffers in a separate panel. Other rushing/receiving role scopes are source-specific; see exact qualification profiles. Tied procedures and every method remain in the canonical records.":panel==="B"?"B's retained original-selected Week8 pool, not all-board/A-C overlap. Public aggregate arithmetic only. Forecast, quote and selection clocks remain distinct; venue settlement is unverified. No row-level C parity is implied.":"All13 captured Sunday/Monday games final; Thursday outside original capture. Original2513 forecasts/407 roster candidates unchanged.1532 graded,981 participation-unknown,0 pending. CMP/ATT paper blocks and chart label/tail shadow remain.";
 for(const [category,label] of Object.entries(labels)){
  let cells;
  if(panel==="C"){
   const r=data.C_forecast_only.categories.find(r=>r.category===category);
   cells=[label,"C-FORWARD-P2-v4 · original law / mean / median","W8, 13 captured games","N/A — line unavailable","N/A — line unavailable","N/A — forecast only",`${r.issued} issued / ${r.graded} graded`,"13",`Median MAE ${r.median_MAE===null?"N/A":r.median_MAE.toFixed(4)}; mean RMSE ${r.mean_RMSE===null?"N/A":r.mean_RMSE.toFixed(4)}`,`CRPS ${r.CRPS.toFixed(6)}; not a hit rate`,`${r.states.UNKNOWN||0} unknown;0pending; no prop lines`];
  }else{
   const r=panel==="A"?data.A_headline.find(r=>r.category===category):data.B_original.find(r=>r.target===category);
   if(!r?.COMBINED?.decided){cells=[label,"N/A — no qualified matching market","None","N/A","N/A","N/A","Universe unknown","N/A","N/A","N/A","Contract/offer unavailable; no invented NO/fantasy market"];}
   else{
    const ci=panel==="A"?r.uncertainty.intervals.COMBINED:r.uncertainty?.game_interval;
    const u=ci?ci.map(pct).join("–")+" · descriptive sensitivity":"No independent common-mask uncertainty";
    const difference=panel==="A"?`${r.matched_control.change_vs_best_constant>=0?"+":""}${r.matched_control.change_vs_best_constant} wins vs better constant on own decided pool`:"See same-pool overall constant control above";
    const method=panel==="A"?`${r.method} / ${r.product} · ${r.procedure_id}`:`${r.procedure_id} / ${r.product_id} / ${r.strategy}`;
    cells=[label,method,panel==="A"?"2026 W1–7":"2026 W8",rec(r.OVER),rec(r.UNDER),rec(r.COMBINED),`${r.eligible}/${r.selected}/${r.COMBINED.decided}`,r.games,difference,u+(panel==="A"?" · "+r.higher_observed_side+" higher by "+r.side_difference_percentage_points.toFixed(2)+"pp (different selected pools)":""),panel==="A"?`Timing-unverified aggregate; ${r.unknown_participation} unknown,${r.played_missing} missing;${r.no_lean} no-lean;${r.missing_offer_or_prediction} unavailable`:`Owner-local original-selected aggregate; ${r.COMBINED.states.UNKNOWN_PARTICIPATION||0} unknown; settlement unverified`];
   }
  }
  const tr=document.createElement("tr");tr.dataset.category=category;
  for(const value of cells){const td=document.createElement("td");td.textContent=String(value);tr.append(td);}body.append(tr);
 }
 select("#clock").textContent="Page evidence prepared "+clock(data.prepared_UTC)+" · C final grading source observed "+clock(data.C_forecast_only.source_observed_UTC)+". A's original clocks are unverified; these display/build clocks do not authenticate past quotes.";
 select("#served").textContent="Actually served commit: "+build.served_commit+" · protocol "+data.protocol+" · A/B scoped acknowledgements now received; this retained panel remains unchanged.";
}
async function start(){try{
 const b=await fetch("build.json",{cache:"no-cache"});if(!b.ok)throw Error("Build binding unavailable");build=await b.json();
 const r=await fetch("data/championship-period-v2.json",{cache:"no-cache"});if(!r.ok)throw Error("Canonical projection unavailable");const text=await r.text();const digest=[...new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text)))].map(x=>x.toString(16).padStart(2,"0")).join("");if(digest!==build.championship_SHA256)throw Error("Projection checksum mismatch");data=JSON.parse(text);if(data.schema!=="ABC-C-PERIOD-CONTINUATION-SITE-v2-1"||data.A_headline.length!==12||data.C_forecast_only.original_pregame_actual_line_selections!==0)throw Error("Evidence/schema mismatch");
 const sr=await fetch("data/championship-shared-c01.json",{cache:"no-cache"});if(!sr.ok)throw Error("Shared projection unavailable");const st=await sr.text();const sd=[...new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(st)))].map(x=>x.toString(16).padStart(2,"0")).join("");if(sd!==build.championship_shared_C01_SHA256)throw Error("Shared projection checksum mismatch");shared=JSON.parse(st);if(shared.schema!=="ABC-SHARED-PREDICTIVE-C01-SITE-v1"||shared.panels.S.rows.length!==12)throw Error("Shared evidence/schema mismatch");
 select("#scope").textContent="Partial actual-line evidence; source-specific historical and shared masks stay distinct. No future champion, verified probability confidence, ticket, profit or90% claim.";select("#panel").onchange=render;select("#zone").onchange=render;render();
 }catch(e){select("#records").replaceChildren();select("#error").hidden=false;select("#error").textContent=e.message+". Actual-prop results unavailable; no synthetic defaults, rankings or entries.";}}
start();

// C06 is an independent, bound current-decision projection. It never changes
// the historical panels, live producer, forecasts or selection implementation.
window.c06={healthy:false,data:null};
function c06Text(x){if(x===null||x===undefined)return 'N/A — not established';if(typeof x!=='object')return String(x);if(Array.isArray(x))return x.length?x.map(c06Text).join(' · '):'None reported';return Object.entries(x).map(([k,v])=>k.replaceAll('_',' ')+': '+c06Text(v)).join('; ');}
function c06Record(x){if(!x||!x.decided)return 'N/A — no decided selections';return `${x.wins}–${x.losses}/${x.decided}/${(100*x.rate).toFixed(2)}%`;}
function c06Cell(tr,value){const td=document.createElement('td');td.textContent=c06Text(value);tr.append(td);return td;}
function c06Details(td,title,value){const detail=document.createElement('details'),summary=document.createElement('summary'),p=document.createElement('p');summary.textContent=title;p.textContent=c06Text(value);detail.append(summary,p);td.append(detail);}
function c06Check(x){
 if(x.schema!=='C-CATEGORY-PRODUCT-DECISIONS-SITE-v1'||x.model_or_policy_activation!==false||x.publication_scope!=='C_COORDINATOR_RESEARCH_DECISIONS;ORIGINAL_WEBSITE_OWNER_ALONE_RELEASES')throw Error('Unexpected decision publication scope');
 if(!Array.isArray(x.categories)||x.categories.length!==12)throw Error('Twelve category decisions required');
 const ids=x.categories.map(r=>r.category==='fpts'?'nick-chart-ppr-v1':r.category),expected=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','nick-chart-ppr-v1'];
 if(new Set(ids).size!==12||expected.some(k=>!ids.includes(k)))throw Error('Missing or duplicate category');
 c06CheckCurrent(x.current_packet);
 const decisions=['KEEP_INCUMBENT','PROVISIONALLY_SWITCH','SHADOW','ABSTAIN','BLOCKED'];
 for(const r of x.categories){
  if(!decisions.includes(r.decision))throw Error('Unknown category decision');
  for(const side of ['OVER','UNDER','COMBINED']){const v=r[side];if(v!==null){if(!v||!['wins','losses','decided'].every(k=>Number.isInteger(v[k])&&v[k]>=0)||v.wins+v.losses!==v.decided)throw Error('Invalid own-side counts');if(v.decided===0?v.rate!==null:typeof v.rate!=='number'||!Number.isFinite(v.rate)||Math.abs(v.rate-v.wins/v.decided)>1e-12)throw Error('Invalid own-side rate');}}
  if(r.OVER&&r.UNDER&&r.COMBINED&&['wins','losses','decided'].some(k=>r.OVER[k]+r.UNDER[k]!==r.COMBINED[k]))throw Error('Combined record does not sum counts');
 }
}
function c06ClearCurrent(){if(window.c06ExpiryTimer)clearTimeout(window.c06ExpiryTimer);window.c06ExpiryTimer=null;window.c06NextTransitionUTC=null;select('#c06-current-section').hidden=true;select('#c06-current-records').replaceChildren();select('#c06-current-status').textContent='';select('#c06-current-clock').textContent='';}
function c06CheckCurrent(x){
 if(x===null||x===undefined)return;
 if(x.schema!=='C06-CURRENT-P1-SITE-PACKET-v1'||x.state!=='SERVER_QUALIFIED_FORECAST_SHADOW_ONLY'||x.primary_replacement!==false||x.real_offers!==0||x.real_selections!==0||x.forecast_rows!==25||x.players!==25||x.WR_TE_direction_candidate_rows!==18||x.RB_shadow_rows!==7||!Array.isArray(x.rows)||x.rows.length!==25)throw Error('Invalid typed current-query shadow contract');
 if(new Set(x.rows.map(r=>r.forecast_id)).size!==25||new Set(x.rows.map(r=>r.player_id+'|'+r.game_id)).size!==25)throw Error('Duplicate current-query identity');
 if(x.rows.filter(r=>['WR','TE'].includes(r.position)).length!==18||x.rows.filter(r=>r.position==='RB').length!==7)throw Error('Wrong current-query role scope');
 for(const r of x.rows){
  if(!['mean','median','p05','p95'].every(k=>typeof r[k]==='number'&&Number.isFinite(r[k])&&r[k]>=0)||!['line','selected_side','probability_at_line','confidence','EV'].every(k=>r[k]===null))throw Error('Untyped current projection or invented offer');
  if(r.direction_candidate_role_eligible!==['WR','TE'].includes(r.position))throw Error('Current role qualification mismatch');
  const t=k=>Date.parse(r[k]);if(!(t('model_fit_cutoff_UTC')<=t('information_cutoff_UTC')&&t('information_cutoff_UTC')<t('inference_UTC')&&t('inference_UTC')<t('issued_UTC')&&t('issued_UTC')<=Date.parse(x.server_persisted_UTC)&&Date.parse(x.server_persisted_UTC)<t('kickoff_UTC')))throw Error('Invalid current packet clocks');
 }
}
function c06CurrentUse(r){const now=Date.now();if(now>=Date.parse(r.kickoff_UTC))return 'Game started · preserved grading snapshot';if(now>=Date.parse(r.expires_UTC))return 'Expired for current use · preserved forecast';if(now<Date.parse(r.issued_UTC))return 'Clock before issuance · no current use';return 'Within source/status expiry · forecast shadow';}
function c06RenderCurrent(){
 const x=window.c06.data?.current_packet;if(!window.c06.healthy||!x){c06ClearCurrent();return;}select('#c06-current-section').hidden=false;const role=select('#c06-current-role').value,rows=x.rows.filter(r=>role==='ALL'||(role==='WR_TE'?['WR','TE'].includes(r.position):r.position==='RB'));select('#c06-current-records').replaceChildren();
 for(const r of rows){const tr=document.createElement('tr');tr.dataset.forecastId=r.forecast_id;c06Cell(tr,`${r.name} · ${r.team} vs ${r.opponent_team} · ${r.position}`);c06Cell(tr,r.mean.toFixed(4));c06Cell(tr,r.median.toFixed(4));c06Cell(tr,`${r.p05}–${r.p95} · conditional count quantiles, not confidence`);c06Cell(tr,`${c06Text(r.history_support)} known prior reception games · latest ${c06Text(r.latest_admitted_game)} · age ${c06Text(r.latest_game_age_at_current_feature_cutoff_days)} days; sparse ${c06Text(r.sparse_history)}, imputed ${c06Text(r.any_imputed)}, incumbent fallback ${c06Text(r.hard_incumbent_fallback)}`);c06Cell(tr,`${r.position==='RB'?'RB forecast shadow; no WR/TE qualification inheritance':'WR/TE historical candidate role; current packet remains shadow'} · ${c06CurrentUse(r)}`);c06Cell(tr,'Unavailable · no qualified offer or selection');select('#c06-current-records').append(tr);}
 select('#c06-current-status').textContent=`${x.run_id} · ${x.model_id}: 25 forecast-only players, 18 WR/TE candidate-scope rows and 7 RB shadow rows; 0 actual offers, 0 selected directions, no primary switch. Expected mean, lower median and conditional count quantiles are separate products.`;
 select('#c06-current-clock').textContent=`Model fit information cutoff ${clock(x.model_fit_cutoff_UTC)} · current roster observed ${clock(x.roster_observed_UTC)} · current football/source admission ${clock(x.information_cutoff_UTC)} · actually re-inferred ${clock(x.first_inference_UTC)} to ${clock(x.last_inference_UTC)} · native status ${clock(x.native_status_observed_UTC)} · issued ${clock(x.issued_UTC)} · GitHub server persistence ${clock(x.server_persisted_UTC)} · current use expires ${clock(x.expires_UTC)} · timezone ${select('#zone').value}. Exact eligible feature-basis parity retained the older fit; newer source observation is not a new fit or authenticated historical publication clock.`;
 select('#c06-current-role').onchange=c06RenderCurrent;if(window.c06ExpiryTimer)clearTimeout(window.c06ExpiryTimer);const next=[Date.parse(x.expires_UTC),...x.rows.map(r=>Date.parse(r.kickoff_UTC))].filter(t=>t>Date.now()).sort((a,b)=>a-b)[0];window.c06NextTransitionUTC=next?new Date(next).toISOString():null;if(next)window.c06ExpiryTimer=setTimeout(c06RenderCurrent,Math.min(next-Date.now()+50,2147483647));
}
function c06Render(){
 const x=window.c06.data;if(!window.c06.healthy||!x)return;const chosen=select('#c06-category').value,rows=x.categories.filter(r=>chosen==='ALL'||r.category===chosen);select('#c06-records').replaceChildren();select('#c06-products').replaceChildren();
 for(const r of rows){
  const tr=document.createElement('tr');tr.dataset.category=r.category;
  c06Cell(tr,`${r.label} · ${c06Text(r.role_scope)}`);
  c06Cell(tr,`${c06Text(r.exact_procedure)} · ${c06Text(r.output)} · ${c06Text(r.history_policy)} · origin ${c06Text(r.origin)}`);
  c06Cell(tr,`${c06Text(r.actual_weeks_by_season)} · ${c06Text(r.evidence_tier)}`);
  for(const side of ['OVER','UNDER','COMBINED'])c06Cell(tr,c06Record(r[side]));
  c06Cell(tr,r.coverage);
  const lead=c06Cell(tr,'Preferred eligible: '+c06Text(r.preferred_eligible_candidate));c06Details(lead,'Highest observed within named panels',r.highest_observed_panels);
  const control=c06Cell(tr,r.controls);c06Details(control,'Uncertainty and comparison limits',r.uncertainty);
  c06Cell(tr,`C research: ${r.research_recommendation||r.decision} · Original website: ${r.website_operational_decision||"Not verified"} · ${c06Text(r.admission_reconciliation?.reason)} · ${c06Text(r.five_week_status)} · ${c06Text(r.current_query)}`);
  c06Cell(tr,`${c06Text(r.actual_live_method)} · Next owner action: ${c06Text(r.remaining_owner_action)}`);select('#c06-records').append(tr);
  for(const p of r.other_products){const pr=document.createElement('tr');pr.dataset.category=r.category;pr.dataset.product=typeof p==='object'?(p.product||p.product_id||p.type||'Separate product'):'Separate product';c06Cell(pr,r.label);c06Cell(pr,pr.dataset.product);c06Cell(pr,p);select('#c06-products').append(pr);}
 }
 select('#c06-clock').textContent='Decision evidence prepared '+clock(x.prepared_UTC)+'. This is a coordinator record, not an original-site activation receipt or a new NFL observation.';c06RenderCurrent();
}
async function c06Start(){
 window.c06.healthy=false;window.c06.data=null;c06ClearCurrent();select('#c06-records').replaceChildren();select('#c06-products').replaceChildren();select('#c06-clock').textContent='';select('#c06-limits').textContent='';select('#c06-error').hidden=true;
 try{
  const br=await fetch('build.json',{cache:'no-cache'});if(!br.ok)throw Error('Build binding unavailable');const b=await br.json();if(!/^[a-f0-9]{64}$/.test(b.category_decisions_c06_SHA256||''))throw Error('Decision checksum binding unavailable');
  const response=await fetch('data/category-decisions-c06.json',{cache:'no-cache'});if(!response.ok)throw Error('Canonical decisions unavailable');const text=await response.text();const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))].map(v=>v.toString(16).padStart(2,'0')).join('');if(digest!==b.category_decisions_c06_SHA256)throw Error('Decision checksum mismatch');
  const x=JSON.parse(text);c06Check(x);window.c06.data=x;window.c06.healthy=true;
  const menu=select('#c06-category'),previous=menu.value;menu.replaceChildren();const all=document.createElement('option');all.value='ALL';all.textContent='All twelve categories';menu.append(all);for(const r of x.categories){const o=document.createElement('option');o.value=r.category;o.textContent=r.label;menu.append(o);}menu.value=x.categories.some(r=>r.category===previous)?previous:'ALL';menu.onchange=c06Render;
  select('#c06-status').textContent=x.status;select('#c06-limits').textContent='Current exact-version joins are admitted only to their stated public/owner-local verification scope. Annual retained W1–5 offers, archived seven-week panels with their recorded source-week qualifications, and separate native later-week panels remain distinct. Unverified quote clocks stay unverified; no universal cross-panel champion or automatic release is inferred.';c06Render();
 }catch(e){window.c06.healthy=false;window.c06.data=null;c06ClearCurrent();select('#c06-records').replaceChildren();select('#c06-products').replaceChildren();select('#c06-clock').textContent='';select('#c06-limits').textContent='';select('#c06-status').textContent='Current category decisions unavailable';select('#c06-error').hidden=false;select('#c06-error').textContent=e.message+'. No default candidate, primary switch or confidence will be invented.';}
}
select('#zone').addEventListener('change',()=>{if(window.c06.healthy)c06Render();});
c06Start();
