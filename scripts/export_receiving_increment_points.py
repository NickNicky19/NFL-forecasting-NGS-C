"""Outcome-free typed historical handoff; no inference, fit, or selection."""
from pathlib import Path
import json,lzma,hashlib,datetime
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/profile-increment-v2';OUT=ROOT/'reports/profile-increment-v2'
def read(p):return json.loads(lzma.decompress(p.read_bytes()))
def main():
 dest=OUT/'C03_TYPED_POINTS_2025_2026_W1_W8.json.xz'
 if dest.exists():raise RuntimeError('IMMUTABLE_EXPORT_ALREADY_EXISTS')
 rows=[];models={}
 for year in [2025,2026]:
  for r in read(ART/f'NUMERICAL_ROWS-{year}.json.xz'):
   for arm in ['R1','R2','R3']:
    key=f'{year}-W{r["week"]:02}-{arm}';p=ART/(key+'.json.xz')
    if key not in models:models[key]={'path':str(p.relative_to(ROOT)),'SHA256':hashlib.sha256(p.read_bytes()).hexdigest()}
    v=r[arm];rows.append(dict(game_id=r['game_id'],player_id=r['player_id'],team=r['team'],opponent=r['opponent_team'],role=r['position'],category='rec',season=year,week=r['week'],procedure='C-RECEIVING-PROFILE-INCREMENT-v2::'+arm,model_key=key,mean=v['mean'],median=v['median'],hard_fallback=v['hard_fallback'],profile_covered=v['profile_covered'],any_imputed=v['any_imputed'],cohort=r['cohort']))
 obj={'id':'C03-TYPED-POINT-HANDOFF-v2','actual_export_created_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':rows,'models':models,'row_population':'OriginalallRBWRTEstat-row-conditionedqueries;unknownoutcomesnotdropped. Notauthenticatedpregameroster ororiginalissuedselections.','products':['UNROUNDED_EXPECTED_MEAN','LOWER_MEDIAN'],'rule':'Exactpoint>qualifiedactuallineOver;<Under;equalabstain;ownerlocalscorerqualifiedoffers/outcomesseparate','outcomes_or_selections_in_export':False,'new_fits':0,'new_inference':0,'history':'H-MULTIordinary2022expanding;newcontext2024-26;strictkickoff+7daycurrent-vintage reconstruction,per-originrollingrefit; exposeddevelopment','rights':'Cpermittedderivedfootballpredictions/GitHubretention;doesnotgrantprivatepeerlineaccess','receiver':'Aownedpermittedboardjoin;Brepresentativearithmetic;Cconsolidation;receiptNOT_ACKNOWLEDGED','no_probability_EV_or_TopPicks_duration_claim':True}
 dest.write_bytes(lzma.compress((json.dumps(obj,separators=(',',':'))+'\n').encode(),preset=6))
 (OUT/'TYPED_POINT_HANDOFF.json').write_text(json.dumps({'path':str(dest.relative_to(ROOT)),'SHA256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,'rows':len(rows),'models':len(models),'actual_export_created_UTC':obj['actual_export_created_UTC'],'status':'PREPARED_FOR_C_PUBLICATION;OWNER_RECEIPT_PENDING','private_board_access':'Aonly;newearlierjoinsuserreportedcompletecurrentreceiptnotlocated;thisnewC03joinisaseparatefollow-on','existing_scorer':'ABC-ACTUAL-PROP-CHAMPIONSHIP-v2-C-1','consumer_primary_activation':False},indent=2)+'\n')
 print('OUTCOME_FREE_HANDOFF',len(rows),dest.stat().st_size)
if __name__=='__main__':main()
