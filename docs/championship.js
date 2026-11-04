"use strict";
const select=s=>document.querySelector(s);
let data,build;
const labels={pass_yd:"Passing Yards",pass_td:"Passing TDs",pass_cmp:"Completions",pass_att:"Pass Attempts",pass_int:"Interceptions Thrown",rush_yd:"Rushing Yards",rush_att:"Rush Attempts",rec:"Receptions",rec_yd:"Receiving Yards",rush_rec_yd:"Rush + Rec Yards",anytime_td:"Anytime TD",fpts:"Fantasy Points (nick-chart-ppr-v1)"};
const pct=x=>typeof x==="number"?(100*x).toFixed(2)+"%":"N/A";
const rec=x=>x?.decided?`${x.wins}-${x.losses}/${x.decided}/${pct(x.rate)}`:"N/A — no decided selections";
function clock(x){return x?new Intl.DateTimeFormat("en-US",{timeZone:select("#zone").value,dateStyle:"medium",timeStyle:"long"}).format(new Date(x)):"Unknown";}
function render(){
 const panel=select("#panel").value,body=select("#records");body.replaceChildren();
 select("#leaders").textContent=panel==="A"?"Raw A W1–7 Over leader: interceptions, Leaf median 4–1/5 (80%). Under: interceptions, CatBoost 4–1/5 and Leaf mean 8–2/10 (80%), tied. Combined: passing TDs, Count A legacy/mean 87–55/142 (61.27%), tied. No evidence-supported future champion.":panel==="B"?"Original-selected Week8 diagnostic: original205–210/415 (49.40%) versus always-Under224–191/415 (53.98%), +19 wins to the constant control. Not a proposed Under policy or common-board championship.":"Over, Under and combined actual-prop leaders: NOT ESTABLISHED. C issued no qualified actual-line selections; these are forecast-only grades.";
 select("#details").textContent=panel==="A"?"A's highest observed complete point procedures on a timing-unverified actual-line panel. Requested W1–8; actually W1–7. Exact history memory needs producer binding; it is not guessed from a method name. PassingQB, rushingRB, receivingRB/WR/TE. Tied procedures and every method remain in the canonical records.":panel==="B"?"B's retained original-selected Week8 pool, not all-board/A-C overlap. Public aggregate arithmetic only. Forecast, quote and selection clocks remain distinct; venue settlement is unverified. No row-level C parity is implied.":"All13 captured Sunday/Monday games final; Thursday outside original capture. Original2513 forecasts/407 roster candidates unchanged.1532 graded,981 participation-unknown,0 pending. CMP/ATT paper blocks and chart label/tail shadow remain.";
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
 select("#served").textContent="Actually served commit: "+build.served_commit+" · protocol "+data.protocol+" · no A/B current common-row acknowledgement received.";
}
async function start(){try{
 const b=await fetch("build.json",{cache:"no-cache"});if(!b.ok)throw Error("Build binding unavailable");build=await b.json();
 const r=await fetch("data/championship-period-v2.json",{cache:"no-cache"});if(!r.ok)throw Error("Canonical projection unavailable");const text=await r.text();const digest=[...new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text)))].map(x=>x.toString(16).padStart(2,"0")).join("");if(digest!==build.championship_SHA256)throw Error("Projection checksum mismatch");data=JSON.parse(text);if(data.schema!=="ABC-C-PERIOD-CONTINUATION-SITE-v2-1"||data.A_headline.length!==12||data.C_forecast_only.original_pregame_actual_line_selections!==0)throw Error("Evidence/schema mismatch");select("#scope").textContent=data.scope;select("#panel").onchange=render;select("#zone").onchange=render;render();
 }catch(e){select("#records").replaceChildren();select("#error").hidden=false;select("#error").textContent=e.message+". Actual-prop results unavailable; no synthetic defaults, rankings or entries.";}}
start();
