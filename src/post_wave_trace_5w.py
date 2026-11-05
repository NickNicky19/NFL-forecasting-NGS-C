"""New read-only model-usage trace; original football fits remain frozen."""
import gzip
import hashlib
import json
import resource
import signal
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from actual_accuracy_v6 import digest
from data_v2 import load,History,vector
from laws_v2 import ThresholdModel,medians,design
from predictive_information_c01 import ROOT,ART,read,write,sha,now,storage_guard
from receiving_information_v10 import ReceivingInformation,team_projection,SHARE_SUPPORT,SHARE_VALUES,COMP_SUPPORT,COMP_VALUES
from reliability_v8 import hgb_cdf,hgb_export

OUT=ROOT/'reports/post-wave-5w-v1'
BASE_NAMES=['rec_mean3','rec_support3','rec_mean8','rec_support8']+[x for i in range(1,5) for x in [f'rec_lag{i}',f'age_lag{i}',f'missing_lag{i}']]+['role_QB','role_RB','role_WR','role_TE']+[x for c in ['attempts','carries','targets'] for x in [c+'_mean3',c+'_rows3',c+'_last']]+['team_attempts_mean3','team_carries_mean3','team_sacks_mean3']


def feature_names(stage,arm):
    if stage.startswith('share'):
        return BASE_NAMES+['home','week','team_rest_days']+SHARE_SUPPORT+(SHARE_VALUES if arm=='S1' else [])
    return BASE_NAMES+(COMP_SUPPORT if arm in ['C1','C2'] else [])+(COMP_VALUES if arm=='C2' else [])


def canonical_tree_hash(model,names):
    columns=names+['missing_'+x for x in names]+['exact_count_threshold']
    trees=[]
    for tree in model['trees']:
        t=dict(tree);t['feature_idx']=['LEAF' if leaf else columns[int(i)] for i,leaf in zip(t['feature_idx'],t['is_leaf'])];trees.append(t)
    return digest(dict(baseline=model['baseline'],trees=trees,thresholds=[float(x) for x in model['thresholds']]))


def stats(values):
    a=np.asarray(values,float);known=a[np.isfinite(a)]
    return dict(rows=len(a),missing=int(np.sum(~np.isfinite(a))),unique=int(len(np.unique(known))),minimum=float(known.min()) if len(known) else None,maximum=float(known.max()) if len(known) else None,std=float(known.std()) if len(known) else None)


def build():
    assert not (OUT/'MODEL_INPUT_TRACE.json').exists(),'COMPLETED_TRACE_FROZEN'
    start=time.monotonic();cpu=time.process_time()
    charged=read(OUT/'TRACE_ATTEMPTS.json')['attempt1']['conservative_single_thread_CPU_charge_seconds'] if (OUT/'TRACE_ATTEMPTS.json').exists() else 0
    signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('TRACE_CPU_CAP120')));signal.setitimer(signal.ITIMER_PROF,120-charged)
    storage_guard();models=[];perturb=[]
    for stage in ['share-original','share-actual','completion-original']:
        rows=read(ART/stage/'PREDICTIONS.json.gz')
        for path in sorted((ART/stage).glob('*MODEL.json.gz')):
            packet=read(path);model=packet['model'];origin='-'.join(path.name.split('-')[:2]);arm=path.name.split('-')[2]
            names=feature_names(stage,arm);assert len(names)==len(model['imputation'])
            columns=names+['missing_'+x for x in names]+['exact_count_threshold']
            counts=Counter(columns[int(idx)] for tree in model['trees'] for idx,leaf in zip(tree['feature_idx'],tree['is_leaf']) if not leaf)
            origin_rows=[r for r in rows if r['origin']==origin]
            new_names=SHARE_VALUES if arm=='S1' else COMP_VALUES if arm=='C2' else []
            added={name:stats([r['arms'][arm]['features'][names.index(name)] for r in origin_rows]) for name in new_names}
            models.append(dict(stage=stage,origin=origin,arm=arm,model_path=str(path.relative_to(ROOT)),model_SHA256=sha(path),raw_columns=names,training_membership_SHA256=packet['training_membership_SHA256'],training_fingerprint=packet['training_fingerprint'],raw_imputation=model['imputation'],fitted_split_counts=dict(counts),new_value_query_variation=added,canonical_tree_SHA256=canonical_tree_hash(model,names),cache_identity='Separateorigin/armcache;dimensions/memberhash/fingerprintarebound;C0reuseexplicitonly2026'))
            query=next(r for r in origin_rows if all(r['arms'][arm]['features'][names.index(n)] is not None for n in new_names))
            fv=np.asarray(query['arms'][arm]['features'],float);before=np.asarray(hgb_cdf(model,fv,[0,1,3,7]));changed=fv.copy()
            for name in new_names:changed[names.index(name)]=.99 if 'share' in name or 'rate' in name else 999.
            after=np.asarray(hgb_cdf(model,changed,[0,1,3,7]));assert np.array_equal(before,after)
            perturb.append(dict(stage=stage,origin=origin,arm=arm,new_value_fields=new_names,maximum_probability_change=float(np.max(np.abs(before-after))),reason='Unusedbysavedtrees;notdroppedinputorcache'))
    # Reuse prior all-query source and safe-inference audit; newly verify actual
    # training field order/variation/imputation/fingerprint at ONE representative origin.
    inputs=Path(__import__('os').environ['C_VERIFIED_FACTS_DIR']);assert sha(inputs/'facts.csv.gz')=='9abc681265b6bec413de2d9002aa72ac19b1a48ea2e57d4f38698b1cc8717a11'
    d,g,teams=load(inputs);raw=pd.read_csv(inputs/'facts.csv.gz',low_memory=False);ct=team_projection(raw,g);del raw
    info=ReceivingInformation(d,ct);hist=History(d[d.season>=2022],'player_id');th=History(teams[teams.season>=2022],'team')
    cutoff=float(g.loc[(g.season==2026)&(g.week==2),'kickoff'].min())
    pool=d.loc[d.position.isin(['RB','WR','TE']),['game_id','player_id','team','opponent_team','position','season','week','home_team','kickoff','available','values']].to_dict('records')
    train=[r for r in pool if r['season']>=2022 and r['available']<cutoff and r['values']['rec'] is not None]
    ys=np.asarray([r['values']['rec'] for r in train],float);membership=digest([dict(game_id=r['game_id'],player_id=r['player_id']) for r in train])
    op=np.asarray([vector(r,'rec',hist,th,'E0_OP') for r in train],float)
    env=np.asarray([vector(r,'rec',hist,th,'E0_ENV') for r in train],float)
    ss=[info.share(r) for r in train];cc=[info.completion(r) for r in train]
    support=np.asarray([r[0] for r in ss],float);values=np.asarray([r[1] for r in ss],float)
    cs=np.asarray([r[0] for r in cc],float);cv=np.asarray([r[1] for r in cc],float)
    matrices={'S0':np.column_stack([env,support]),'S1':np.column_stack([env,support,values]),'C0':op,'C1':np.column_stack([op,cs]),'C2':np.column_stack([op,cs,cv])}
    training=[]
    for arm,x in matrices.items():
        stage='share-actual' if arm.startswith('S') else 'completion-original';packet=read(ART/stage/f'2026-W02-{arm}-MODEL.json.gz')
        fingerprint=hashlib.sha256(np.nan_to_num(x,nan=999999.).tobytes()+ys.tobytes()).hexdigest()
        assert fingerprint==packet['training_fingerprint'] and membership==packet['training_membership_SHA256']
        assert np.allclose(medians(x),packet['model']['imputation'],rtol=0,atol=0)
        zz=design(x,np.asarray(packet['model']['imputation']));assert np.array_equal(zz[:,:x.shape[1]],np.where(np.isfinite(x),x,medians(x)))
        names=feature_names(stage,arm)
        training.append(dict(stage=stage,arm=arm,rows=len(train),training_membership_SHA256=membership,training_fingerprint=fingerprint,medians_match=True,feature_order='rawvalues_then_rawmissingflags_then_exactthreshold',raw_field_stats={name:stats(x[:,i]) for i,name in enumerate(names)},fit_target_outcomes_prior_to_weekly_origin=True))
    # One deterministic SOFTWARE fit; never a football trial or test week.
    if (OUT/'SYNTHETIC_PATH_POSITIVE_CONTROL.json').exists():
        positive=read(OUT/'SYNTHETIC_PATH_POSITIVE_CONTROL.json');assert positive['new_synthetic_fit_count']==1
    else:
        toy=np.zeros((512,43));toy[:,-1]=np.where(np.arange(512)%2,1.,-1.);y=np.where(toy[:,-1]>0,8.,0.)
        with threadpool_limits(limits=1):fitted=ThresholdModel('MONOTONE_HGB',False,[0,1,2,3,4,5,7]).fit(toy[:384],y[:384])
        numeric=hgb_export(fitted);low=hgb_cdf(numeric,toy[384],[3])[0];high=hgb_cdf(numeric,toy[385],[3])[0]
        assert low-high>.5
        usage=Counter(int(i) for t in numeric['trees'] for i,leaf in zip(t['feature_idx'],t['is_leaf']) if not leaf);assert usage[42]>0
        write(OUT/'SYNTHETIC_PATH_POSITIVE_CONTROL.json',dict(id='C-POST5W-SOFTWARE-POSITIVE-v1',new_synthetic_fit_count=1,new_football_fits=0,qualifying_football_weeks=0,rows=512,train_rows=384,raw_columns=43,informative_new_column=42,data_rule='Alternatinglastfeature-1/+1;Y0/8;allotherfeatures0;notNFLsimulation',CDF3_low_feature=low,CDF3_high_feature=high,split_counts=dict(usage),model=numeric,interpretation='Addedcolumncanreachtrainingandinference;notfootballskillorforcedNFLusage'))
    grouped={}
    for row in models:grouped.setdefault((row['stage'],row['origin']),[]).append(row)
    same=[]
    for (stage,origin),rr in grouped.items():
        assert len({r['canonical_tree_SHA256'] for r in rr})==1
        same.append(dict(stage=stage,origin=origin,arms=[r['arm'] for r in rr],canonical_tree_SHA256=rr[0]['canonical_tree_SHA256'],all_trees_identical_after_threshold_index_mapping=True))
    result=dict(id='C-POST5W-UNCHANGED-PREDICTION-TRACE-v1',completed_UTC=now(),models=models,training_reconstruction=training,tree_equivalence=same,inference_perturbation=perturb,reused_prior_audit=dict(path='reports/predictive-C01/INDEPENDENT_PREDICTIVE_REVIEW.json',SHA256=sha(ROOT/'reports/predictive-C01/INDEPENDENT_PREDICTIVE_REVIEW.json'),scope='Alreadyverifiedall2524sourcevectors/44170primitiveprobabilities/targetfuturemutation;notrepeatedhere'),verified_cause='Newperformancecolumnsarepresent,varying,correctlyorderedandimputed;nofootballtreesplitusesnewvalues. Canonicalfittedtreesareidenticalacrossvaluearms. Sharedplayer_targets5supportISusedbysharecontrols. Noevidenceofdrop/cache/featureorderdefect.',unresolved='Whyunusedfeatureslostsplitselectionandtheireffectunderotherlearners/representationsarenotestablished;gaintracewasnotretained. Nocausalredundancyclaim.',decision='CLOSE_THIS_BOUNDED_VALUE_RECIPE_NO_INCREMENT;ordinarycompletioncontextnotNGS',new_football_fits=0,new_synthetic_software_fits=1,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,max_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    result['conservative_prior_CPU_charge_seconds']=charged;result['CPU_total_upper_bound_seconds']=charged+result['CPU_seconds']
    assert result['CPU_total_upper_bound_seconds']<=120 and result['wall_seconds']+charged<=240 and result['max_RSS_bytes']<=805306368
    write(OUT/'MODEL_INPUT_TRACE.json',result);storage_guard();signal.setitimer(signal.ITIMER_PROF,0)
    print('TRACE_VERIFIED',len(models),'MODELS',len(training),'EXACT_TRAINING_MATRICES;0FOOTBALL_FITS;1SYNTHETIC_FIT')


if __name__=='__main__':build()
