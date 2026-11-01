"""Persistent finite budget for one manual forward-model wave."""
import json,os,resource,signal,time
from pathlib import Path

def tree_bytes(root):
    return sum(os.stat(Path(d)/n,follow_symlinks=False).st_size for d,_,names in os.walk(root) for n in names)

class ForwardBudget:
    def __init__(self,path,out,roots,limits):
        self.path,self.out,self.roots,self.limits=path,out,roots,limits
        self.state=json.loads(path.read_text()) if path.exists() else dict(CPU_seconds=0.,wall_seconds=0.,fit_attempts=[],peak_RSS_bytes=0,peak_cache_bytes=0,stages=[])
        if self.state.get('active'):raise RuntimeError('UNCLEAN_FORWARD_WAVE_REQUIRES_EXPLICIT_REVIEW')
        self.cpu=time.process_time();self.wall=time.monotonic();self.check()
    def persist(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        p=self.path.with_suffix('.tmp');p.write_text(json.dumps(self.state,separators=(',',':')));p.replace(self.path)
    def checkpoint(self):
        c,w=time.process_time(),time.monotonic()
        self.state['CPU_seconds']+=c-self.cpu;self.state['wall_seconds']+=w-self.wall;self.cpu,self.wall=c,w
    def check(self):
        self.checkpoint();s=self.state;b=self.limits
        s['peak_RSS_bytes']=max(s['peak_RSS_bytes'],resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        s['peak_cache_bytes']=max(s['peak_cache_bytes'],sum(tree_bytes(p) for p in self.roots))
        s.setdefault('output_sizes',{})[self.out.name]=tree_bytes(self.out)
        self.persist()
        for key in ['CPU_seconds','wall_seconds']:
            if s[key]>b[key]:raise RuntimeError('FORWARD_'+key.upper()+'_CAP')
        if s['peak_RSS_bytes']>b['fit_RSS_bytes']:raise RuntimeError('FORWARD_RSS_CAP')
        if s['peak_cache_bytes']>b['whole_C_cache_bytes']:raise RuntimeError('WHOLE_C_CACHE_CAP')
        if sum(s['output_sizes'].values())+tree_bytes(self.path.parent)>b['new_artifacts_bytes']:raise RuntimeError('NEW_FORWARD_ARTIFACT_CAP')
    def reserve(self,target,key):
        self.check()
        if any(r['key']==key for r in self.state['fit_attempts']):raise RuntimeError('PREVIOUS_FIT_ATTEMPT_WITHOUT_RECOVERABLE_MODEL')
        if len(self.state['fit_attempts'])>=self.limits['primary_fits_max']:raise RuntimeError('CUMULATIVE_FORWARD_FIT_CAP')
        self.state['fit_attempts'].append(dict(target=target,key=key));self.persist()
    def __enter__(self):
        self.state['active']=True;self.persist()
        self.old=signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('FORWARD_CPU_TIMER')))
        signal.setitimer(signal.ITIMER_PROF,max(.01,self.limits['CPU_seconds']-self.state['CPU_seconds']));return self
    def __exit__(self,typ,value,tb):
        signal.setitimer(signal.ITIMER_PROF,0);signal.signal(signal.SIGPROF,self.old);self.checkpoint()
        self.state['active']=False;self.state['stages'].append(dict(state='PASS' if typ is None else 'FAILED',reason=None if typ is None else str(value)))
        self.persist()
