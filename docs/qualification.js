"use strict";
(()=>{
const byId=id=>document.getElementById(id);
let ledger,shown=50;
const record=x=>x?.decided?`${x.wins}–${x.losses}/${x.decided} (${(100*x.rate).toFixed(2)}%)`:"N/A — no decided selections";
function render(){
 byId("qualification-clock").textContent="Ledger prepared "+new Intl.DateTimeFormat("en-US",{timeZone:byId("zone").value,dateStyle:"medium",timeStyle:"long"}).format(new Date(ledger.generated_UTC))+". Count A: seven scored weeks; owner-local restoration verified, hosted/current-query consumer delivery unverified. C value recipes are closed without increment. New Week 9 forecasts are shadow-only; no real-prop paper selections.";
 const body=byId("qualification-records");body.replaceChildren();
 const owner=byId("q-owner").value,category=byId("q-category").value,product=byId("q-product").value,floor=byId("q-floor").value;
 const rows=ledger.rows.filter(r=>(!owner||r.owner===owner)&&(!category||r.category===category)&&(!product||r.product===product)&&(!floor||r.five_week_floor===floor));
 for(const r of rows.slice(0,shown)){
  const tr=document.createElement("tr");tr.dataset.qualificationId=r.row_id;
  const seasons=r.season_records.map(s=>`${s.season}: W${s.scored_weeks.join(",")} · ${s.scored_cases} scored / ${s.selected??"N/A"} selected / ${s.eligible??"N/A"} eligible`).join("; ");
  const own=r.own_side_record;
  const values=[`${r.owner} · ${r.category}`,`${r.procedure_id} · ${r.product} · ${r.role_scope} · ${r.history} · ${r.policy}`,seasons,own?`Over ${record(own.OVER)}; Under ${record(own.UNDER)}; Combined ${record(own.COMBINED)}`:"N/A — numerical/probability/diagnostic product, not an actual-prop hit rate",`${r.scored_week_count} total; ${r.current_2026_scored_week_count} in 2026; duration floor ${r.five_week_floor}. Not primary admission.`,`${r.operational_export}; ${r.strongest_bound_model_control||"Strong controls and exact masks in bound source; no automatic superiority."}`,`${r.source_panel}; ${r.evidence_tier}; ${r.remaining_gates}`];
  for(const value of values){const td=document.createElement("td");td.textContent=value;tr.append(td);}body.append(tr);
 }
 byId("q-more").hidden=rows.length<=shown;byId("q-count").textContent=`Showing ${Math.min(rows.length,shown)} of ${rows.length} product profiles. Profiles and output views are not independent models, games or experiments. No replacement primary admitted in this wave.`;
}
async function start(){try{
 const b=await fetch("build.json",{cache:"no-cache"});if(!b.ok)throw Error("Build binding unavailable");const build=await b.json();
 const r=await fetch("data/qualification-5w.json.gz",{cache:"no-cache"});if(!r.ok)throw Error("Qualification ledger unavailable");const bytes=await r.arrayBuffer();
 const digest=[...new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))].map(x=>x.toString(16).padStart(2,"0")).join("");if(digest!==build.qualification_5w_SHA256)throw Error("Qualification checksum mismatch");
 if(typeof DecompressionStream!=="function")throw Error("Browser cannot unpack the ledger; use the linked GitHub records");
 ledger=JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text());
 if(ledger.schema!=="ABC-PRODUCT-QUALIFICATION-5W-v1"||ledger.categories.length!==12||ledger.rule.minimum_distinct_completed_scored_weeks!==5)throw Error("Qualification schema mismatch");
 for(const [id,key] of [["q-category","category"],["q-product","product"]])for(const value of [...new Set(ledger.rows.map(x=>x[key]))].sort()){const o=document.createElement("option");o.value=value;o.textContent=value;byId(id).append(o);}
 for(const id of ["q-owner","q-category","q-product","q-floor"])byId(id).onchange=()=>{shown=50;render();};byId("q-more").onclick=()=>{shown+=50;render();};
 byId("qualification-status").textContent="Five distinct completed scored (season, week) tests are required for the exact procedure, output, role and policy. Training, folds, repeated views and parent-model weeks do not count. Historical duration does not imply current-season validation. MET is a duration floor only; rights, chronology, support, matched controls and operational admission remain separate.";
 byId("zone").addEventListener("change",render);
 render();
}catch(e){byId("qualification-records").replaceChildren();byId("qualification-status").textContent=e.message+". Qualification unavailable; no primary-admission label or inferred result.";byId("q-more").hidden=true;}}
start();
})();
