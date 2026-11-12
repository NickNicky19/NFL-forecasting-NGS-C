// Read-only source fixtures; no NFL observations or producer execution.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(__dirname+'/CURRENT_APP_JS.decoded.js','utf8');
function span(a,b){return src.slice(src.indexOf(a),src.indexOf(b,src.indexOf(a)));}
const code=[span('function isClassicBaseline(','function rankingCanonical('),span('function baselineTdProbability(','function selectedPlayerGap('),span('function compareSelectedRankingItems(','async function validateSelectedRankings(')].join('\n');
const c={S:{data:{execution_model:{model:'sleeper-matchup-classic-presence-strict-v2'}},lines:{}},selectedPropForecast:()=>null};vm.createContext(c);vm.runInContext(code,c);
let checks=0;const ok=(v)=>{assert(v);checks++;};const eq=(a,b)=>{assert.strictEqual(a,b);checks++;};
const p={id:'fixture',reference_model:'sleeper-matchup-classic-presence-strict-v2'};
const policy=c.selectedRankingPolicy();eq(policy.version,'selected-projection-gap-classic-presence-v2');eq(policy.top_n,12);eq(policy.minimum_score,.35);eq(policy.minimum_games,2);eq(policy.minimum_snap_share,.5);
for(const [key,cat] of Object.entries(policy.categories)){
 const line=cat.minimum_line+10;let r=c.selectedPropGap(p,{key,line,line_from:'dk',adj:line+cat.lean/2});eq(r.lean,null);
 r=c.selectedPropGap(p,{key,line,line_from:'dk',adj:line+cat.lean*2});eq(r.lean,'over');
 r=c.selectedPropGap(p,{key,line,line_from:'sleeper',adj:line-cat.lean*2});eq(r.lean,'under');
 eq(c.selectedPropGap(p,{key,line,line_from:'ours',adj:line+cat.lean*2}),null);
}
eq(c.baselineTdProbability({proj:null,td_chance:0}),null);eq(c.baselineTdProbability({proj:0,td_chance:0}),0);eq(c.baselineTdProbability({proj:1,td_chance:NaN}),null);eq(c.baselineTdProbability({proj:1,td_chance:1.1}),null);
eq(c.selectedPropGap(p,{key:'pass_int',line:.5,line_from:'dk',adj:0}).lean,'under');
ok(c.compareSelectedRankingItems({score:.5,game_id:'a',player_id:'1',key:'rec'},{score:.5,game_id:'b',player_id:'1',key:'rec'})<0);
console.log(JSON.stringify({id:'CATEGORY-WEBSITE-CONSUMER-SOURCE-FIXTURES-v1',status:'PASS',checks,exact_source_SHA256:require('crypto').createHash('sha256').update(src).digest('hex'),selected_policy:policy,scope:'Invoked exact retained consumer functions with fictional rows. Not a full selector replay, production-board/served-value verification, candidate admission or NFL evidence.',new_NFL_observations:0,new_fits:0}));
