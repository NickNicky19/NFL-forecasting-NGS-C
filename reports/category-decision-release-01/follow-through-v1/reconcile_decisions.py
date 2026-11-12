"""Project received owner aggregates into C's existing decision record.

No forecasting, NFL grading, policy search or production activation occurs here.
The coordinator's explicit dispositions are review judgments, not a new scorer.
"""
import datetime as dt
import hashlib
import json
import lzma
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'reports/category-decision-release-01'
HERE = BASE / 'follow-through-v1'

def load(p):
    b = p.read_bytes()
    return json.loads(lzma.decompress(b) if p.suffix == '.xz' else b)

def save(p, x):
    p.write_text(json.dumps(x, indent=2, ensure_ascii=False, allow_nan=False) + '\n')

def binding(p):
    return {'path': p.relative_to(ROOT).as_posix(), 'SHA256': hashlib.sha256(p.read_bytes()).hexdigest()}

def reconcile():
    canonical = BASE / 'CATEGORY_PRODUCT_DECISIONS.json'
    # This migration records the first owner-data projection. The coordinator
    # subsequently appends operational receipts and explicit adjudications.
    # Never reset a closed release to that earlier projection on a repeat run.
    if load(canonical).get('status', '').startswith('CURRENT_RELEASE_VERSION_CLOSED'):
        print('CURRENT_RELEASE_ALREADY_CLOSED; use retained bindings and site validation, not a reset.')
        return
    prior = HERE / 'PRIOR_DECISIONS.json.xz'
    if not prior.exists():
        prior.write_bytes(lzma.compress(canonical.read_bytes()))
    doc = load(prior)
    contribution = load(HERE / 'peer-intake/A_CONTRIBUTION.json.xz')
    weekly = load(HERE / 'peer-intake/A_WEEKLY_COVERAGE.json.xz')
    supplied = {r['category']: r for r in contribution['rows']}
    decisions = dict(pass_yd='SHADOW', pass_td='BLOCKED', pass_cmp='SHADOW',
                     pass_att='KEEP_INCUMBENT', pass_int='SHADOW', rush_yd='KEEP_INCUMBENT',
                     rush_att='SHADOW', rec='SHADOW', rec_yd='SHADOW', rush_rec_yd='SHADOW',
                     anytime_td='ABSTAIN', **{'nick-chart-ppr-v1': 'ABSTAIN'})
    for row in doc['categories']:
        cat = row['category']
        owner = supplied[cat]
        row['decision'] = decisions[cat]
        for panel in row['highest_observed_panels']:
            if panel.get('panel_id') == 'A_ARCHIVED_W1_W7_AS_REPORTED_PENDING_SOURCE':
                panel['source_week_qualification'] = (
                    'A14a source-week binding received: named annual actual lines W1-W5; '
                    'W6-W7 site/reference diagnostics in this package. Preserve this mixed '
                    'archived diagnostic; do not use seven weeks as actual-offer qualification '
                    'or invalidate separate B native/W8 originally frozen source panels.')
                panel['current_disposition'] = 'CONDITIONAL_MIXED_DIAGNOSTIC;SUPERSEDED_FOR_PRIMARY_ACTUAL_OFFER_SCOPE'
                panel['source_week_receipt'] = 'follow-through-v1/peer-intake/A_WEEKLY_COVERAGE.json.xz'
        if owner.get('own_sides'):
            panel = {'panel_id': 'A14A_SOURCE_BOUND_ANNUAL_NJ_W1_W5',
                     'origin': owner['origin_session'], 'category': cat,
                     'procedure_id': owner['exact_procedure'],
                     'tied_candidate_set': owner['tied_point_candidates_in_this_panel'],
                     'own_sides': owner['own_sides'], 'coverage': owner['coverage'],
                     'actual_season_weeks': owner['actual_scored_season_weeks'],
                     'numerical_same_offered_player_rows': owner.get('numerical_same_offered_player_rows'),
                     'matched_strong_control_pairs': owner.get('matched_strong_control_pairs', owner.get('matched_pairs')),
                     'source_policy': weekly['annual_source_policy'], 'evidence_tier': owner['evidence_tier'],
                     'source': 'follow-through-v1/peer-intake/A_CONTRIBUTION.json.xz',
                     'limits': 'Owner-local aggregates; private masks/clocks/model parity not independently supplied. A broad reception panel is not the C WR/TE common mask.'}
            row['highest_observed_panels'].insert(0, panel)
            if cat != 'rec':
                old_id = row['exact_procedure']
                row['exact_procedure'] = owner['exact_procedure']
                row['origin'] = owner['origin_session']
                if old_id != row['exact_procedure']:
                    row['prior_report_procedure_id'] = old_id
                    row['identity_note'] = ('Same config digest/output aliases retained where applicable. '
                                            'Passing-attempt primary row now names the already-tested B common-exposure median; '
                                            'the old A point remains a separate contender, not an alias.')
                row['output'] = owner['exact_procedure'].split('::')[-1]
                row['history_policy'] = owner['exact_history_policy']
                for side in ['OVER', 'UNDER', 'COMBINED']:
                    row[side] = owner['own_sides'][side]
                cov = owner['coverage']
                selected = sum(owner['own_sides'][s].get('selected', owner['own_sides'][s]['decided']) for s in ['OVER', 'UNDER'])
                row['coverage'] = dict(eligible=cov['eligible'],
                    available=cov.get('available', cov['eligible'] - cov['unavailable']),
                    selected=cov.get('selected', selected), unknown=cov.get('unknown', 0),
                    unavailable=cov['unavailable'], fallback=cov.get('fallback_outputs'),
                    games=cov['games'], player_games=cov.get('player_games'),
                    fallback_provenance=cov.get('fallback_count', 'EXPLICIT_EXPORTED_COUNT' if 'fallback_outputs' in cov else 'UNSPECIFIED'))
                row['actual_weeks_by_season'] = {'2026': [1, 2, 3, 4, 5]}
                row['evidence_tier'] = owner['evidence_tier']
                row['numerical_same_offered_player_rows'] = owner.get('numerical_same_offered_player_rows')
                o, u, c = (row[k] for k in ['OVER', 'UNDER', 'COMBINED'])
                row['controls'] = {'ALWAYS_OVER': {'wins': o['wins'] + u['losses'], 'decided': c['decided']},
                    'ALWAYS_UNDER': {'wins': o['losses'] + u['wins'], 'decided': c['decided']},
                    'matched_owner_pairs': panel['matched_strong_control_pairs'],
                    'incumbent_comparison': owner.get('incumbent_paired_difference'),
                    'scope': 'Constants on this exact own decided pool; no live constant-side policy approved.'}
                row['uncertainty'] = {'owner_supplied_pairs': panel['matched_strong_control_pairs'],
                    'private_resampling': 'Intervals received and arithmetic checked; raw masks/resampling not independently reconstructed.',
                    'limits': 'Five exposed week clusters, multiple prior searches, unknown quote/source clocks. Inconclusive is not equivalence.'}
                row['five_week_status'] = {'status': owner['five_week_status'],
                    'actual_season_weeks': owner['actual_scored_season_weeks'],
                    'admission': 'Duration at the admitted retrospective tier does not establish source authentication, superiority or operational readiness.'}
                pref = row.get('preferred_eligible_candidate')
                if pref is not None:
                    pref.update(procedure=row['exact_procedure'], output=row['output'],
                        status='FIVE_WEEK_DURATION_REVIEW_CANDIDATE;SOURCE_SUPPORT_AND_NATIVE_ADMISSION_REMAIN_SCOPED',
                        tied_candidate_set=owner['tied_point_candidates_in_this_panel'])
                if cat in ['pass_att', 'rush_yd']:
                    row['preferred_eligible_candidate'] = None
                if cat == 'pass_att':
                    row['role_scope'] = 'QB; common-exposure own-history median with shared prior/fallback contract'
                row['current_query']['producer_owner'] = owner['origin_session']
            row['source_qualification'] = {
                'scope': 'SUPPORTED_OWNER_LOCAL_SOURCE_WEEK_CLASSIFICATION',
                'release_eligibility': 'CONDITIONAL_AT_DECLARED_RETROSPECTIVE_EVIDENCE_TIER',
                'authenticated_quote_and_vintage': 'UNRESOLVED; UNKNOWN_NOT_RETAINED, NOT BACKDATED',
                'book_priority': weekly['annual_source_policy']['book_priority'],
                'role_provenance': 'Annual weekly export often says UNKNOWN; prior role contracts are preserved separately, not promoted to independently verified raw-role parity.'}
        else:
            row['source_qualification'] = {'scope': 'SUPPORTED_ABSENCE_OF_COMPATIBLE_OFFER_IN_THIS_PANEL',
                'release_eligibility': 'NO_QUALIFIED_REPLACEMENT_ACTUAL_OFFER_DIRECTION',
                'other_sources': 'Not a global absence proof; numerical/event products remain separately recorded.'}
        row['operationally_ready_candidate'] = {
            'research_replacement': None,
            'state': 'NO_CURRENT_ADMITTED_REPLACEMENT_FEED_IN_RECEIVED_PACKAGE',
            'continuity': row['actual_live_method'],
            'meaning': 'Installed incumbent is operational retention, not proven globally best.'}
        row['release_version_state'] = 'CLOSED_WITH_NAMED_OWNER_EXCEPTIONS;RESEARCH_INVENTORY_FROZEN'
        row['decision_scope'] = 'Coordinator recommendation only; original website owner alone admits and releases. No automatic activation.'
        for product in row['other_products']:
            if product['product'] == 'Top_Picks':
                product['decision'] = 'SHADOW'
                product['scope'] = ('Website-owned exact fixed P1 mean WR/TE mapping executed over W5-W8: '
                    'control48-45/93 +3unknown, candidate50-43/93 +3unknown;96selected each. '
                    'Four conditional retrospective full-system weeks, W8 fallback-only. '
                    'Fifth compatible board/clock contract not qualified. B actual verification received separately; '
                    'C has public protocol/aggregates, not private192-row membership parity.')
                product['reason'] = 'Retain current primary selector; exact candidate remains shadow until duration and existing admission requirements qualify. No new five-learned-week gate.'
    doc['id'] = 'NFL-CATEGORY-DECISION-AND-RELEASE-01-C/v1-CLOSED-WITH-EXCEPTIONS'
    doc['prepared_UTC'] = dt.datetime.now(dt.timezone.utc).isoformat()
    doc['status'] = 'CURRENT_RELEASE_VERSION_CLOSED_WITH_SCOPED_DECISIONS;NO_ORIGINAL_SITE_PRIMARY_SWITCH'
    doc['follow_through'] = {'assignment': 'FOLLOW-THROUGH-RELEASE-AND-DEFENSIVE-SOURCE-01/v1',
        'frozen_inventory': 'Prior retained inventory plus exact already-tested supplied A/B contributions; no new defensive experiment or candidate.',
        'new_fits': 0, 'new_inference': 0, 'new_NFL_games_or_weeks': 0,
        'current_capture': 'Existing75/69/25 packets preserved; expired current use, pending recorded future games. No synthetic offered-line decisions.',
        'defensive_lead': 'SOURCE_BLOCKED; separate qualification only, no active inputs or release gate.'}
    for name in ['peer-intake/A_CONTRIBUTION.json.xz', 'peer-intake/A_WEEKLY_COVERAGE.json.xz']:
        doc['source_bindings'].append(binding(HERE / name))
    save(canonical, doc)
    print('Existing canonical decisions reconciled from owner source-bound aggregates; no new NFL grading.')

if __name__ == '__main__':
    reconcile()
