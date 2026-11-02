"""Regression checks of preserved grading and outcome-blind list policies; no NFL fits."""
import copy,gzip,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from topk_reference_v9 import choose,common_pool,METHODS,ROOT
from contracts_v2 import chart,target,WEIGHTS
from test_reliability_v8 import row

def read(p):
    b=Path(p).read_bytes()
    return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)

class Week8AndRankRegressions(unittest.TestCase):
    def test_completion_correction_and_native_return_are_append_only(self):
        base=ROOT/'reports/week8-v9'
        one=read(base/'GRADED_FORECAST_ROWS.json.gz')
        two=read(base/'runs/C-W8-v9-20261102-002/GRADED_FORECAST_ROWS.json.gz')
        three=read(base/'runs/C-W8-v9-20261102-003/GRADED_FORECAST_ROWS.json.gz')
        delta=lambda a,b:[y for x,y in zip(a,b) if (x['state'],x['actual'])!=(y['state'],y['actual'])]
        self.assertEqual(len(one),2513);self.assertEqual([r['forecast_id'] for r in one],[r['forecast_id'] for r in three])
        self.assertEqual(len(delta(one,two)),31);self.assertEqual({r['category'] for r in delta(one,two)},{'pass_cmp'})
        changed=delta(two,three);self.assertEqual(len(changed),1)
        self.assertEqual((changed[0]['player_id'],changed[0]['category'],changed[0]['actual']),('00-0039407','fpts',6))
        anytime=next(r for r in three if r['player_id']=='00-0039407' and r['category']=='anytime_td');self.assertEqual(anytime['actual'],0)

    def test_pending_and_unknown_keep_no_actual_and_no_synthetic_offer(self):
        data=read(ROOT/'reports/week8-v9/SUMMARY.json');rows=read(ROOT/data['canonical_rows']['path'])
        unknown=[r for r in rows if r['state']=='UNKNOWN'];pending=[r for r in rows if r['state']=='PENDING']
        self.assertEqual(len(unknown),873);self.assertTrue(all(r['actual'] is None for r in unknown))
        self.assertEqual(len(pending),199);self.assertEqual({r['game_id'] for r in pending},{'2026_08_CHI_SEA'})
        self.assertTrue(all(r['actual'] is None and r['NLL'] is None for r in pending))
        self.assertTrue(all(r['line'] is None and r['selected_side'] is None for r in rows))
        self.assertTrue(any(r['state']=='GRADED_PLAYED' and r['actual']==0 for r in rows))
        self.assertEqual(len(data['actual_props']),72)
        self.assertTrue(all(r['OVER']['wins'] is None and r['UNDER']['losses'] is None and r['COMBINED']['hit_rate'] is None for r in data['actual_props']))

    def test_return_score_does_not_invent_rushing_receiving_event(self):
        q=read(ROOT/'sources/nfl-stats-v9/rare-return-TD/QUALIFICATION.json');f=q['score_components']
        self.assertEqual(sum(WEIGHTS[k]*v for k,v in f.items())/50,6)
        self.assertEqual(target(f,'anytime_td',True),0)
        # Legacy rare-zero ingestion must still reject a positive broad total.
        self.assertIsNone(chart(f|dict(fumble_recovery_tds=0,special_teams_tds=1),True)[0])

    def test_own_lists_remain_different_outcomes_never_select_members(self):
        a=row(1,.9,status='UNKNOWN_PARTICIPATION');b=row(2,.8,status='LOSS');c=row(3,.7)
        c['player_id']=a['player_id']
        before,_=choose([c,b,a],'MIXED',6)
        mut=copy.deepcopy([c,b,a])
        for r in mut:r.update(actual=999,status='WIN')
        after,_=choose(mut,'MIXED',6)
        self.assertEqual([r['record_id'] for r in before],['1','2'])
        self.assertEqual([r['record_id'] for r in before],[r['record_id'] for r in after])
        other=copy.deepcopy([c,b,a]);other[2]['_confidence']=.6
        alt,_=choose(other,'MIXED',1);self.assertNotEqual(before[0]['record_id'],alt[0]['record_id'])
        under,_=choose([a,b,c],'UNDER_ONLY',20);self.assertEqual(under,[])

    def test_common_pool_excludes_technical_failure_not_unknown_outcome(self):
        group=[]
        for m in METHODS:
            r=row(1,status='UNKNOWN_PARTICIPATION')|dict(method_id=m,season=2026,period='FULL_GAME',scoring_contract_id='official-player-fullgame-OT-v1');group.append(r)
        admitted,held=common_pool(group);self.assertEqual(len(admitted),1);self.assertEqual(held,[])
        group[1]['p_under']=None;admitted,held=common_pool(group);self.assertFalse(admitted);self.assertEqual(len(held),1)

    def test_unknown_member_expectations_do_not_use_the_decided_mask(self):
        q=read(ROOT/'reports/topk-reference-v9/CUMULATIVE.json.gz')
        r=next(x for x in q if x['book']=='draftkings' and x['method']=='P3_DIRECT' and x['scope']=='GLOBAL' and x['side_variant']=='MIXED' and x['K']==6)
        self.assertEqual((r['selected_count'],r['wins'],r['losses'],r['decided']),(12,8,3,11))
        self.assertAlmostEqual(r['expected_wins_decided']/11,r['mean_confidence_decided'])
        self.assertAlmostEqual(r['all_selected_expected_wins']/12,r['all_selected_mean_confidence'])
        self.assertGreater(r['all_selected_expected_wins'],r['expected_wins_decided'])

if __name__=='__main__':unittest.main()
