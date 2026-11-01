"""Append independent played-zero corrections without touching saved forecasts."""
import argparse,csv,gzip,json
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from actual_accuracy_v6 import ROOT,sha,digest,stable_write,validate_row
from contracts_v2 import CATEGORIES,integer,grade
from data_v2 import PHYSICAL

OUT=ROOT/'reports/propline-v7'
def run(inputs):
    target=OUT/'CORRECTIONS_GRADED_ROWS_V7_1.json';assert not target.exists(),'APPEND_ONLY_CORRECTION_ALREADY_EXISTS'
    assert sha(inputs/'facts.csv.gz')=='9abc681265b6bec413de2d9002aa72ac19b1a48ea2e57d4f38698b1cc8717a11'
    assert sha(inputs/'schedule.csv')=='5ac3af003131a316eadba4bf90f9758953cef7a41bb6359fb5eb7d90d8a170f0'
    with gzip.open(inputs/'facts.csv.gz','rt') as f:facts={(r['game_id'],r['player_id']):r for r in csv.DictReader(f)}
    with (inputs/'schedule.csv').open() as f:games={r['game_id']:r for r in csv.DictReader(f)}
    original=json.loads((OUT/'GRADED_ROWS.json').read_text());changes=[];conflicts=[]
    for r in original['rows']:
        if r['method_id']!='P2_LAW':continue
        fact=facts.get((r['game_id'],r['player_id']))
        if not fact or fact['position']==r['position']:continue
        proof={k:integer(fact.get(k),k in ['passing_yards','rushing_yards','receiving_yards']) for k in PHYSICAL+['passing_yards','rushing_yards','receiving_yards']}
        played=any((v is not None and v>0) for k,v in proof.items() if k not in ['passing_yards','rushing_yards','receiving_yards']) or any(proof[k] not in [None,0] for k in ['passing_yards','rushing_yards','receiving_yards'])
        g=games[r['game_id']];final=g['home_score']!='' and g['away_score']!=''
        actual=integer(fact.get(CATEGORIES[r['category']][1]),CATEGORIES[r['category']][2]=='signed') if played and final else None
        conflicts.append(dict(offer_id=r['offer_id'],game_id=r['game_id'],player_id=r['player_id'],category=r['category'],historical_roster_position=r['position'],stat_source_position=fact['position'],played_evidence=proof,final_score_evidence={'home_score':g['home_score'],'away_score':g['away_score']},qualified_actual=actual,model_availability_unchanged=True))
        if actual is None:continue
        for old in original['rows']:
            if old['offer_id']!=r['offer_id']:continue
            new=deepcopy(old);new.update(grade_id=old['record_id']+'-STAT-G2',supersedes_grade_id=old['grade_id'],graded_UTC=datetime.now(timezone.utc).isoformat(),actual=actual,appearance='PLAYED',outcome_correction_id='C-PROPLINE-OUTCOME-ROLE-v7.1')
            if old['status']=='UNKNOWN_PARTICIPATION':new['status']=grade(actual,old['line'],old['selected_side'])
            validate_row(new);changes.append(new)
    assert len(conflicts)==3 and len(changes)==12,'UNEXPECTED_CORRECTION_SCOPE_REQUIRES_REVIEW'
    audit=dict(id='C-PROPLINE-OUTCOME-ROLE-v7.1',original_graded_rows_SHA256=sha(OUT/'GRADED_ROWS.json'),reason='Outcome labels must not inherit the fitted forecast population filter. Two rosterRB/sourceFB played-zero outcomes were excluded by data_v2.load; forecasts remain unavailable. A rosterWR/sourceCB all-zero evidence row remains unknown.',conflicts=conflicts,changed_offer_cases=2,changed_method_grade_versions=len(changes),original_forecasts_changed=0,new_fits=0,statistically_decided_fitted_procedures_unchanged=914,statistically_decided_constant_controls=916)
    stable_write(OUT/'SOURCE_ROLE_AUDIT_V7_1.json',audit)
    data=dict(schema=original['schema'],source_review_id=original['source_review_id'],retained_evidence=original['retained_evidence']+[dict(path='reports/propline-v7/SOURCE_ROLE_AUDIT_V7_1.json',SHA256=sha(OUT/'SOURCE_ROLE_AUDIT_V7_1.json'))],rows=changes);stable_write(target,data)
    review=json.loads((OUT/'SOURCE_REVIEW.json').read_text());review['approved_dataset_SHA256'].append(sha(target));review['correction']='C-PROPLINE-OUTCOME-ROLE-v7.1: append12grade versions for2played-zero cases; no changed forecasts or offers.';stable_write(OUT/'SOURCE_REVIEW_V7_1.json',review)
    path=ROOT/'reporting/actual-props-v6/DATASETS.json';m=json.loads(path.read_text());m['datasets'].append(dict(dataset_id='C-PROPLINE-OUTCOME-ROLE-v7.1',path=target.relative_to(ROOT).as_posix(),SHA256=sha(target)))
    for d in m['datasets']:d.update(review_path='reports/propline-v7/SOURCE_REVIEW_V7_1.json',review_SHA256=sha(OUT/'SOURCE_REVIEW_V7_1.json'))
    m['trusted_review_SHA256'][review['review_id']]=digest(review);stable_write(path,m)
    print(json.dumps(audit,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);a=p.parse_args();run(a.inputs)
