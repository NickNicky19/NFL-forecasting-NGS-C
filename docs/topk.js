"use strict";
Object.assign(state,{topk:null,topkHealthy:false,topkMembers:null});
async function startTopk(){
 try{
  const m=await fetchJSON("data/topk-reference-v9.json",state.build.topk_reference_v9_SHA256);
  if(m.schema!=="C-TOPK-REFERENCE-COMPARISON-v9"||m.weekly.length!==810||!m.no_common_pregame_board||!m.no_entry_or_payout)throw Error("Invalid ranking evidence");
  state.topk=m;state.topkHealthy=true;
  for(const id of ["tk-book","tk-week","tk-scope","tk-category","tk-side","tk-k"])$("#"+id).onchange=renderTopk;
  renderTopk();
 }catch(e){state.topkHealthy=false;$("#tk-state").textContent="Reference comparison unavailable: "+e.message;$("#tk-results tbody").replaceChildren();$("#tk-overlap tbody").replaceChildren();}
}
function tkMatch(r){return r.book===$("#tk-book").value&&r.scope===$("#tk-scope").value&&r.category===($("#tk-scope").value==="GLOBAL"?"ALL":$("#tk-category").value)&&r.side_variant===$("#tk-side").value&&r.K===Number($("#tk-k").value);}
function tkRow(body,values){const tr=node("tr");for(const v of values)tr.append(node("td",String(v)));body.append(tr);return tr;}
function renderTopk(){
 if(!state.topkHealthy)return;const m=state.topk,week=$("#tk-week").value;$("#tk-category").disabled=$("#tk-scope").value==="GLOBAL";
 $("#tk-state").textContent="EXPLORATORY LAST-RECORDED-LINE RANKING DIAGNOSTIC · 2026 Weeks 2–3, same 32 games. Common pool "+m.run.common_cases+" quote-cases; "+m.run.excluded_cases+" technically unavailable. All 810 weekly lists are saved. No simultaneous pregame board, entry, payout or validated confidence claim.";
 const body=$("#tk-results tbody");body.replaceChildren();const rows=(week==="ALL"?m.cumulative:m.weekly).filter(r=>tkMatch(r)&&(week==="ALL"||r.week===Number(week)));
 for(const r of rows){const ci=r.uncertainty?.interval,tr=tkRow(body,[r.method,week==="ALL"?"Two weekly lists":"Week "+week,r.common_eligible+" / "+r.side_eligible+" / "+r.selected_count,rateRecord(r),pct(r.mean_confidence_decided),fmt(r.expected_wins_decided,3)+" / "+fmt(r.all_selected_expected_wins,3),JSON.stringify(r.states),JSON.stringify(r.role_composition)+" / "+JSON.stringify(r.category_composition),r.games+" / "+r.weeks,ci?pct(ci[0])+"–"+pct(ci[1])+" · "+r.uncertainty.kind:"N/A"]);tr.dataset.tkMethod=r.method;tr.tabIndex=0;tr.onclick=()=>topkDetail(r);tr.onkeydown=e=>{if(e.key==="Enter")topkDetail(r);};}
 const ob=$("#tk-overlap tbody");ob.replaceChildren();for(const r of m.overlaps.filter(r=>tkMatch(r)&&(week==="ALL"||r.week===Number(week))))tkRow(ob,["W"+r.week+" · "+r.methods.join(" / "),r.selected.join(" / "),r.exact_offer_overlap+" / "+pct(r.exact_offer_Jaccard),r.player_game_overlap+" / "+pct(r.player_game_Jaccard)]);
}
async function topkDetail(r){
 const root=$("#detail-body");root.replaceChildren(node("h2",r.method+" · saved ranking members"),node("p","Exploratory last-recorded-line diagnostic. Each method keeps its own list. Unknowns are not replaced. Not an executable ticket or six-of-six record."));$("#detail").showModal();
 try{
  if(!state.topkMembers){const d=state.topk.membership,response=await fetch(d.path,{cache:"no-store"});if(!response.ok)throw Error("HTTP "+response.status);const bytes=await response.arrayBuffer(),hash=[...new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))].map(x=>x.toString(16).padStart(2,"0")).join("");if(hash!==d.SHA256)throw Error("Membership checksum mismatch");if(typeof DecompressionStream!=="function")throw Error("Browser cannot decode retained gzip; use the GitHub membership link");const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));const members=JSON.parse(await new Response(stream).text());if(members.length!==d.rows)throw Error("Membership count mismatch");state.topkMembers=members;}
  const ids=state.topk.weekly.filter(w=>["book","scope","category","side_variant","K","method"].every(k=>w[k]===r[k])&&(!r.week||w.week===r.week)).map(w=>w.diagnostic_id),members=state.topkMembers.filter(x=>ids.includes(x.diagnostic_id));const t=node("table"),h=node("tr");for(const x of ["Week / rank / player","Role / game / market","Exact line / selected side / model estimate","Actual / statistical grade","Quote clock / forecast cutoff"])h.append(node("th",x));t.append(h);
  for(const x of members){const tr=node("tr");tr.dataset.tkRecord=x.record_id;for(const v of ["W"+x.week+" / "+x.rank+" / "+x.player_name,x.role+" / "+x.game_id+" / "+x.category,x.line+" / "+x.side+" / "+pct(x.p_selected),fmt(x.actual)+" / "+x.statistical_status,JSON.stringify(x.source_closing_clocks)+" / "+clock(x.forecast_cutoff)])tr.append(node("td",v));t.append(tr);}root.append(t,node("p","Recorded model estimates are not validated selected-side confidence. Same-line/time/open paired market prices remain unavailable. Main/alternate/promotion tiers are unverified."));
 }catch(e){root.append(node("p","Membership unavailable: "+e.message+". No reconstructed or substitute list is shown."));}
 const a=node("a","Canonical membership, all policies and overlap evidence ↗");a.href=state.topk.evidence_URL;root.append(a);
}
