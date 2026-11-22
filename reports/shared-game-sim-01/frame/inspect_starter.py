"""Inspect starter metadata and outcome-free queries; never execute its code or parse labels."""
import argparse,collections,hashlib,json,math,stat,time,zipfile
from pathlib import Path,PurePosixPath

def digest(b):return hashlib.sha256(b).hexdigest()
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def main():
    c0=time.process_time();w0=time.monotonic();ap=argparse.ArgumentParser();ap.add_argument('--zip',required=True);a=ap.parse_args();src=Path(a.zip)
    out=Path(__file__).resolve().parent;revision='f15790bc1396e532eb0f6991f8e05dbf6a66fb2d'
    wire=src.read_bytes();assert len(wire)<=20*1024**2
    entries=[]
    with zipfile.ZipFile(src) as z:
        info=z.infolist();assert len(info)==len({i.filename for i in info})
        assert sum(i.file_size for i in info)<=20*1024**2
        for i in info:
            p=PurePosixPath(i.filename);mode=i.external_attr>>16
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename
            assert not stat.S_ISLNK(mode) and not (i.flag_bits&1)
        sums=json.loads(z.read('SHA256SUMS.json'));bindings=json.loads(z.read('SOURCE_BINDINGS.json'))
        for i in info:
            body=z.read(i.filename) # Integrity hash only, no recursive/model/grade ingestion.
            sha=digest(body);expected=sums.get(i.filename)
            if expected:assert expected['bytes']==len(body) and expected['sha256']==sha
            entries.append(dict(path=i.filename,bytes=len(body),compressed_bytes=i.compress_size,SHA256=sha,delivered_sum_match=bool(expected),classification='FORECAST_QUERY' if i.filename=='queries/evaluation_cases_ungraded.jsonl' else 'GRADING_QUARANTINE' if i.filename.startswith(('grading_only/','comparison/stats/','comparison/archives/')) or i.filename in ['comparison/category_rows.json','comparison/category_results.json','comparison/verified_int_index.json','comparison/output/data/track_record.json','comparison/category_uncertainty.json'] else 'METADATA_OR_STATIC_CODE_NOT_EXECUTED'))
        assert len(sums)==28 and len(entries)==29
        archive_parity=[]
        for b in bindings:
            assert b['source_revision']==revision
            if 'original_source_sha256' in b:
                body=z.read(b['local_path']);assert body.endswith(b'\n') and digest(body[:-1])==b['original_source_sha256']
                archive_parity.append(dict(local_path=b['local_path'],original_source_SHA256=b['original_source_sha256'],terminal_LF_removal_parity='PASS_EXACTLY_ONE_BYTE',external_source_readback='NOT_PERFORMED'))
        qpath='queries/evaluation_cases_ungraded.jsonl';q=z.read(qpath);rows=[json.loads(line) for line in q.splitlines()]
        assert q==z.read(qpath) and len(rows)==3474 and len({r['case_id'] for r in rows})==3474
        keys=set(rows[0]);assert all(set(r)==keys for r in rows)
        forbidden={'actual','outcome','result','grade','played','participation','targets_actual','final_score','yards_actual'}
        assert not keys&forbidden and all(r['source_revision']==revision for r in rows)
        assert len({r['game_id'] for r in rows})==74
        assert all(r['provider_first_point']==(r['saved_raw_point'] if r['point_source']=='model' and finite(r['saved_raw_point']) else r['saved_adjusted_point']) for r in rows)
        counter=lambda k:dict(collections.Counter(r[k] for r in rows))
        query=dict(path=qpath,bytes=len(q),SHA256=digest(q),row_count=len(rows),unique_case_ids=len({r['case_id'] for r in rows}),unique_games=len({r['game_id'] for r in rows}),unique_player_games=len({(r['game_id'],r['player_id']) for r in rows}),unique_player_game_category=len({(r['game_id'],r['player_id'],r['category']) for r in rows}),weeks=counter('week'),games_by_week={w:len({r['game_id'] for r in rows if r['week']==w}) for w in sorted({r['week'] for r in rows})},categories=counter('category'),venues=counter('venue'),point_sources=counter('point_source'),positions=counter('position'),fields=sorted(keys),field_types={k:dict(collections.Counter(type(r[k]).__name__ for r in rows)) for k in sorted(keys)},null_counts={k:sum(r[k] is None for r in rows) for k in sorted(keys)},clock_states=dict(forecast=counter('forecast_issuance_authentication'),quote=counter('quote_clock_authentication')),provider_fallback_by_category=dict(collections.Counter(r['category'] for r in rows if r['point_source']!='model' or not finite(r['saved_raw_point']))),W1_point_rule_parity='PASS_ALL3474',W0_W1_point_equalities=dict(W0=sum(r['saved_adjusted_point']==r['line'] for r in rows),W1=sum(r['provider_first_point']==r['line'] for r in rows)),local_reopening='PASS_SAME_QUERY_BODY_READ_TWICE',durable_forecast_body_retention='NOT_CLAIMED;uploadedattachmentlocallyreopenable;parentmustqualifydurableroutebeforegeneration')
    result=dict(schema='SHARED_GAME_SIM01_AUDITED_V3_STARTER_FRAME_INSPECTION',scope='DATA_PACKAGE_METADATA_AND_OUTCOME_FREE_QUERY_ONLY;NO_GRADING_OR_MODEL_EXECUTION',attachment=dict(filename=src.name,bytes=len(wire),SHA256=digest(wire),entries=len(entries),expanded_bytes=sum(i['bytes'] for i in entries)),source_revision_asserted=revision,source_binding_revision_check='PASS_ALL_INCLUDED_BINDINGS_AND_QUERY_ROWS;NOT_EXTERNAL_OWNER_FRAME_ADMISSION',zip_safety=dict(traversal_symlinks_encryption='NONE',duplicate_members='NONE',expanded_bound_bytes=20971520,code_executed=False,files_extracted=False),files=entries,delivered_manifest=dict(entries=28,verified=28,self_hash='SHA256SUMS.jsonnotselfincluded;actualbodyhashretainedinfiles'),archive_original_byte_parity=archive_parity,query=query,grading_separation=dict(target_bodies_hashed_only=True,target_JSON_or_JSONL_parsed=False,target_stats_loaded=False,category_results_inspected=False,sixty_cell_replay='USER_AND_PACKAGE_REPORTED_COMPLETED;NOT_REPEATED',unknown_outcomes=dict(count=464,status='USER_AND_PACKAGE_REPORTED;NOT_INDEPENDENTLY_REPARSED_HERE'),no_new_grade=True),benchmarks=dict(W0='Literal saved_adjusted_point (saved adj), no changed multiplier recipe',W1='Literal saved_raw_point (saved proj) only when point_source==model and finite; otherwise saved_adjusted_point fallback; provider_first_point parity verified',strict_point_side='over iff point>line; under iff point<line; equality/nonfinite abstain',saved_lean='Existing margin-based stored side, separate from strict crossing;1219nullsavedleansarenotforecastunavailability',no_point_derived_probability=True),field_allowlist_guidance=dict(identity=['case_id','season','week','game_id','player_id','category','position','venue'],primary_provider_inputs='Conditional model-finite saved_raw_point; explicitly declared pregame fallback for6missingproviderpoints; provider_first_point is a W1 product, not pureproviderforallrows',benchmark_only=['saved_adjusted_point','saved_lean'],tail_query_not_outcome_distribution_feature=['line'],metadata_only=['source_revision','forecast_issuance_authentication','quote_clock_authentication','scope']),missing_inside_starter=['canonicalNFLgame/GSISplayeridentityadapter','team/opponent/eventkickoff/origincutoff','completeevent-effectiveteammateuniverse','pace/teamvolume/role/eventtrainingbodies','participant/void contract beyond suppliedquery fields','offeredside/period/settlementversion and ordinary/alternate classification'],engine_readiness='FRAME_QUERY_PRESENT;ENGINE_SOURCE_READINESS_NOT_DETERMINED_BY_THIS_FRAME_TASK',evidence_tier='EXPOSED_W4_W9_RETAINED_ACTUAL_LINE_DEVELOPMENT;ALL3474ISSUE_AND_QUOTECLOCKSUNVERIFIED',missing_categories=['anytime_td','nick-chart-ppr-v1'],publication_scope='Metadataandaggregatesonly;rawattachment/query/labelsnotcommittedorredistributionrightsassumed',new_fits=0,new_inference=0,new_simulation_trajectories=0,new_grading=0,new_network=0)
    (out/'PACKAGE_CONTRACT.json').write_text(json.dumps(result,indent=2)+'\n')
    resource=dict(task='C starter frame metadata inspection',measured_final_process_CPU=time.process_time()-c0,measured_final_process_wall=time.monotonic()-w0,conservative_reporting_CPU_charge=6,known_prior_commands='Fiveboundedstdlibmetadata/schema/static-codeinspectioncommands;notseparatelyprocess-metered;includedconservatively',scope='Ordinaryreportingonly;noneofanyscientificpilotbudget/reserveused',new_scientific_work=False,sourcebody_GETs=0)
    (out/'RESOURCE.json').write_text(json.dumps(resource,indent=2)+'\n')
    md=f'''# Starter frame contract — metadata inspection only

ZIP `{src.name}`: **{len(wire):,} bytes**, SHA256 `{digest(wire)}`. All29 entries are safe relative nonsymlink paths; expanded size9,088,315bytes. All28 delivered SHA256SUMS entries pass. The six archive copies match their recorded original-source hashes after removal of exactly one terminal LF. No archive/statistic/result JSON was parsed, no bundled code executed, no old grade replay repeated.

The outcome-free query body is actually present and locally reopenable: **3,474 rows /74 games /1,156 player-games**, ten numerical categories, W4–9. W4 has95 rows from2 games; later week rows are W5=682,W6=692,W7=649,W8=666,W9=690. DK=3,368,Sleeper=106; model-source=3,468,average-source=6 (three each receptions and receiving yards). All points used byW0/W1 and all lines are finite. Six raw provider values are null and use the declared adjusted fallback. W1 formula parity passes all3,474rows. All rows mark original issue and quote clocks **UNVERIFIED**.

W0 is literal saved `adj`. W1 is literal saved `proj` when source=model and finite, otherwise incumbent adjusted fallback. Strict point direction uses `>`Over/`<`Under; equality abstains. Saved margin-based leans are a separate product;1,219null leans are not missing forecasts. Points do not supply probability distributions.

The query contains website numeric game/player IDs, category, line, venue, position and benchmark/provider fields. It does **not** contain team/opponent, kickoff/cutoff, full teammate universe, pace/role/event-training inputs or a complete settlement/ordinary-line contract. Root's retained-input task may qualify those separately; missing fields in this package are not proof all engine paths are blocked. The derived query has no repository-path binding inSOURCE_BINDINGS; the website must admit the supplied derived frame/case contract. Its stable case IDs are specific to this pinned comparison. All source bindings and query rows assert website revision `{revision}`; this check is not external source readback or original pregame authentication.

`grading_only/outcomes.jsonl`, archives, postgame stats, category_rows/results, verifiedINT and track-record bodies remain grading/audit-only. They were byte-hashed without label parsing. **464unknown outcomes and60replayedcells are accepted user/package reports, not newly verified counts here.** No target outcomes or participant list reached a forecast worker. No raw package body is published by this task. Durable query retention, canonical identities, actual component sources and full-engine readiness remain root/website qualification work. AnytimeTD and exact nick-chart-PPR have no matching supplied offer rows.

[Machine contract and all entry hashes](PACKAGE_CONTRACT.json) · [Reporting accounting](RESOURCE.json). This is metadata/source readiness, not model performance or a five-week product qualification.
'''
    (out/'README.md').write_text(md)
    print(json.dumps(dict(state='FRAME_QUERY_PRESENT_METADATA_COMPLETE',query_rows=3474,games=74,entry_hashes=29,CPU=resource['measured_final_process_CPU'])))
if __name__=='__main__':main()
