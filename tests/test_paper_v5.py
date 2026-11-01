"""Explicit fictional software fixtures: no NFL offers, wins or performance."""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import test_actual_offers_v4 as fixtures
import paper_v5 as p

class PaperGates(unittest.TestCase):
    def setUp(self):
        a=fixtures.ExactOffers();a.setUp();self.f=a.f;self.o=a.o|dict(availability_review='CURRENT_ACTIVE_OR_UNKNOWN_CONDITIONAL');self.cutoff=a.cutoff
        self.status=dict(state='pre',status_name='STATUS_SCHEDULED',completed=False,espn_event_id='fixture-e',kickoff_UTC=self.f['kickoff_UTC'],observed_UTC='2026-10-31T23:59:00Z')
    def evaluate(self,o=None,f=None,**kw):return p.exact_directions(o or self.o,f or self.f,'PROSPECTIVE',self.cutoff,self.status,**kw)
    def test_exact_players_lines_and_probability_change(self):
        a=self.evaluate();b=self.evaluate(self.o|dict(player_id='p2',line=19.5),self.f|dict(player_id='p2'))
        self.assertEqual((a['line'],b['line']),(9.5,19.5));self.assertGreater(a['p_over'],b['p_over']);self.assertEqual((a['P2_side'],b['P2_side']),('OVER','UNDER'))
    def test_point_direction_works_without_law_or_price(self):
        f={k:v for k,v in self.f.items() if k!='law'};r=self.evaluate(f=f)
        self.assertEqual(r['P1_side'],'OVER');self.assertEqual(r['P2_reason'],'NO_PROBABILITY_LAW');self.assertIsNone(r['p_over']);self.assertIsNone(r['prices'])
        f.update(median=None,point=10,point_type='MEDIAN');self.assertEqual(self.evaluate(f=f)['P1_side'],'OVER')
    def test_missing_line_never_gets_research_default(self):
        for value in [None,float('nan'),True]:
            r=self.evaluate(self.o|dict(line=value));self.assertEqual(r['P1_state'],'UNAVAILABLE');self.assertIsNone(r['P2_side'])
    def test_synthetic_never_enters_offers_or_results(self):
        bad=self.o|dict(record_kind='SYNTHETIC_THRESHOLD')
        with self.assertRaises(ValueError):self.evaluate(bad)
        with self.assertRaises(ValueError):p.quote_universe([bad],self.cutoff)
        with self.assertRaises(ValueError):p.statistical_grades([bad],{},'P1')
    def test_changed_market_identity_and_same_clock_conflict_rejected(self):
        for patchrow in [dict(game_id='different-event',observed_at_UTC='2026-10-31T23:59:30Z'),dict(line=20.5)]:
            with self.assertRaises(ValueError):p.quote_universe([self.o,self.o|patchrow],self.cutoff)
    def test_newer_closed_and_suspended_cannot_fall_back_open(self):
        for life in ['CLOSED','SUSPENDED']:
            latest=self.o|dict(lifecycle=life,observed_at_UTC='2026-10-31T23:59:30Z');r=p.quote_universe([self.o,latest],self.cutoff)
            self.assertEqual(len(r),1);self.assertEqual(r[0]['lifecycle'],life);self.assertEqual(self.evaluate(r[0])['P2_state'],'UNAVAILABLE')
    def test_status_staleness_started_changed_and_quote_clock_fail_closed(self):
        for delta in [dict(source_asof_UTC='2026-10-31T23:00:00Z'),dict(observed_at_UTC='2026-11-01T00:01:00Z'),dict(side_states={'OVER':'SUSPENDED','UNDER':'OPEN'}),dict(availability_review='CURRENT_OUT')]:
            self.assertTrue(self.evaluate(self.o|delta)['reasons'])
        for status in [self.status|dict(completed=True),self.status|dict(espn_event_id='changed'),self.status|dict(observed_UTC='2026-10-31T22:00:00Z'),{}]:
            r=p.exact_directions(self.o,self.f,'PROSPECTIVE',self.cutoff,status);self.assertEqual(r['P1_state'],'UNAVAILABLE')
    def test_old_forecast_issue_not_reused_as_selection_time(self):
        r=self.evaluate();self.assertNotEqual(r['cutoff_UTC'],r['forecast_generated_UTC']);self.assertEqual(p.instant(r['cutoff_UTC']),self.cutoff)
    def test_cmp_att_coherence_and_chart_shadow_remain_blocked(self):
        for cat in ['pass_cmp','pass_att']:
            f=self.f|dict(category=cat);o=self.o|dict(category=cat)
            for coh in ['COMPLETION_ATTEMPT_CONTRADICTION','CROSS_STATISTIC_COHERENCE_UNCHECKED']:
                self.assertTrue(self.evaluate(o,f,coherence=coh)['reasons'])
            self.assertFalse(self.evaluate(o,f,coherence='CMP_ATT_ORDER_CHECKED_NOT_A_JOINT_LAW')['reasons'])
        self.assertTrue(self.evaluate(f=self.f|dict(readiness='EXPERIMENTAL_SHADOW_LABEL_COVERAGE'))['reasons'])
    def test_probability_complements_monotonic_and_whole_push(self):
        qs=[self.evaluate(self.o|dict(line=x)) for x in [-1.5,0,9.5,10,19.5,25]]
        self.assertTrue(all(abs(sum(r[k] for k in ['p_under','p_push','p_over'])-1)<1e-10 for r in qs))
        self.assertEqual([r['p_over'] for r in qs],sorted([r['p_over'] for r in qs],reverse=True));self.assertGreater(qs[3]['p_push'],0)
    def test_grades_side_counts_win_loss_push_dnp_unknown_signed_zero(self):
        rows=[];out={}
        for i,(line,side,y,appearance) in enumerate([(9.5,'OVER',10,'PLAYED'),(19.5,'UNDER',20,'PLAYED'),(10,'OVER',10,'PLAYED'),(-.5,'UNDER',0,'PLAYED'),(.5,'UNDER',-1,'PLAYED'),(1.5,'OVER',None,'DNP'),(1.5,'OVER',None,'UNKNOWN')]):
            r=self.evaluate(self.o|dict(offer_id=str(i),player_id=str(i),line=line),self.f|dict(player_id=str(i)));r['P1_side']=side;rows.append(r);out[(r['game_id'],str(i),r['category'])]=dict(actual=y,appearance=appearance)
        result=p.statistical_grades(rows,out,'P1');self.assertEqual((result['OVER']['wins'],result['UNDER']['losses']),(1,2));self.assertEqual(result['COMBINED']['rate'],.5);self.assertEqual(result['other'],{'DNP':1,'PUSH':1,'UNKNOWN':1})
    def test_inclusive_milestone_and_missing_actual_bool_boundary(self):
        r=self.evaluate(self.o|dict(comparator='AT_LEAST',line=10));r['P2_side']='OVER'
        def g(y):return p.statistical_grades([r],{(r['game_id'],r['player_id'],r['category']):dict(actual=y,appearance='PLAYED')},'P2')
        self.assertEqual(g(10)['OVER']['wins'],1);self.assertEqual(g(True)['other'],{'MISSING_ACTUAL':1})
    def test_fractional_lattice_tie_uses_exact_contract_and_retains_raw(self):
        r=self.evaluate();r.update(category='fpts',line=.3,P2_side='OVER',p_under=.2,p_push=.6,p_over=.2)
        key=(r['game_id'],r['player_id'],'fpts');a=p.grade_records([r],{key:dict(appearance='PLAYED',actual=.30000000000000004)},'P2')[0]
        self.assertEqual(a['grade'],'PUSH');self.assertEqual(a['actual_lattice_integer'],15);self.assertEqual(a['actual'],.3);self.assertEqual(a['actual_raw'],.30000000000000004);self.assertAlmostEqual(a['probability_half_brier'],.12)
    def test_first_quote_candidate_choice_is_not_outcome_based(self):
        a=self.evaluate();b=self.evaluate(self.o|dict(offer_id='second',line=19.5,observed_at_UTC='2026-10-31T23:59:30Z'))
        rows=p.primary_candidates([a,b]);self.assertEqual([r['offer_id'] for r in rows if r['primary_in_packet']],['second'])
    def test_quote_order_uses_instants_across_offsets(self):
        a=self.evaluate();a.update(offer_id='old',observed_at_UTC='2026-10-31T23:59:30Z')
        b=a|dict(offer_id='new',observed_at_UTC='2026-10-31T18:59:45-05:00')
        self.assertEqual([r['offer_id'] for r in p.primary_candidates([a,b]) if r['primary_in_packet']],['new'])
    def test_known_source_permission_cannot_be_overridden_by_packet_boolean(self):
        registry=p.read(p.REGISTRY)
        for source in registry['sources']:self.assertTrue(p.source_gate(source,'x',registry,p.REGISTRY.parent,self.cutoff.isoformat()))
    def test_false_permission_strings_and_denied_scope_cannot_authorize(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);e=root/'grant.txt';e.write_text('FICTIONAL TEST ONLY');grant=dict(provider='FIXTURE',scope={s:False for s in ['automated_analysis','public_quote_retention','identities_clocks_contracts']},effective_from_UTC='2026-01-01T00:00:00Z',evidence_file=e.name,evidence_SHA256=p.sha(e),review_id='TEST_ONLY',approved_export_SHA256=['abc'])
            source=dict(analysis_qualified=True,public_retention_qualified=True,grant=grant);registry=dict(sources={'TEST':source})
            self.assertIn('GRANT_SCOPE_INCOMPLETE',p.source_gate('TEST','abc',registry,root,self.cutoff.isoformat()))
            source['analysis_qualified']='false';self.assertTrue(p.source_gate('TEST','abc',registry,root,self.cutoff.isoformat()))
    def test_grant_requires_recoverable_exact_scoped_bytes_and_effective_date(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);e=root/'grant.txt';e.write_text('FICTIONAL TEST ONLY');grant=dict(provider='FIXTURE',scope=['automated_analysis','public_quote_retention','identities_clocks_contracts'],effective_from_UTC='2026-01-01T00:00:00Z',evidence_file=e.name,evidence_SHA256=p.sha(e),review_id='TEST_ONLY',approved_export_SHA256=['abc'])
            registry=dict(sources={'TEST':dict(analysis_qualified=True,public_retention_qualified=True,grant=grant)})
            self.assertEqual(p.source_gate('TEST','abc',registry,root,self.cutoff.isoformat()),[])
            self.assertIn('EXACT_EXPORT_OUTSIDE_APPROVED_SCOPE',p.source_gate('TEST','other',registry,root,self.cutoff.isoformat()))
            grant['effective_from_UTC']='2027-01-01T00:00:00Z';self.assertIn('GRANT_OUTSIDE_EFFECTIVE_DATES',p.source_gate('TEST','abc',registry,root,self.cutoff.isoformat()))
            e.write_text('changed');self.assertIn('GRANT_EVIDENCE_BYTES_UNVERIFIED',p.source_gate('TEST','abc',registry,root,self.cutoff.isoformat()))
    def test_server_receipt_does_not_rescue_expired_quote(self):
        with tempfile.TemporaryDirectory() as d:
            run=Path(d);p.write(run/'RUN.json',{});p.write(run/'evaluations.json',[]);m=dict(run_id='fixture',created_UTC='2026-11-01T00:00:00Z');proof=dict(schema='C-PAPER-SERVER-RECEIPT-v5',qualified_pregame_paper=True,fresh_GitHub_bytes=True,run_id='fixture',run_SHA256=p.sha(run/'RUN.json'),evaluations_SHA256=p.sha(run/'evaluations.json'),server_persisted_UTC='2026-11-01T00:30:00Z',server_created_UTC='2026-11-01T00:01:00Z')
            with self.assertRaises(AssertionError):p.check_receipt(run,proof,m,[self.evaluate()])
    def test_saved_point_only_value_and_type_cannot_be_changed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'saved.json';r=dict(game_id='g',player_id='p',category='pass_yd',method_id='m',point=10,point_type='MEDIAN',scoring_contract_id='contract',information_cutoff_UTC='2026-01-01T00:00:00Z',kickoff_UTC='2026-01-02T00:00:00Z');p.write(path,[r]);f=r|dict(retained_forecast_evidence=path.name,retained_forecast_SHA256=p.sha(path));self.assertEqual(p.retained_forecast(f,root),r)
            for delta in [dict(point=999),dict(point_type='MEAN')]:
                with self.assertRaises(AssertionError):p.retained_forecast(f|delta,root)

if __name__=='__main__':unittest.main()
