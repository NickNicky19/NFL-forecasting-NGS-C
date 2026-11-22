"""Single-worker resource/accounting controller for the approved SIM package.

No scientific work on import. CPU includes worker plus controller, failed work
stays charged, and completion reserves cannot be consumed by generation.
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, resource, signal, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'reports/shared-game-sim-01/execution-v1'
LEDGER=D/'LEDGER.json'
LIMITS=dict(CPU_seconds=1800.,wall_seconds=7200.,RSS_bytes=1288490188,
 retained_bytes=536870912,peak_bytes=805306368,whole_C_bytes=2684354560,
 completion_CPU_reserve=380.,source_recovery_reads=8,output_readbacks=8)

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp')
 t.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n');os.replace(t,p)
def footprint(root=ROOT):
 return sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink())
def initialize():
 if LEDGER.exists():
  x=json.loads(LEDGER.read_text());assert x['limits']==LIMITS;return x
 x=dict(id='C-SHARED-GAME-SIM01-APPROVED-EXECUTION-v1',approval='User follow-through approves request at ebf9a0bbe8411f8dbb80745ec87f1fbcf13a4f82 ONCE',limits=LIMITS,
  charged_CPU_seconds=45.,charged_controlled_wall_seconds=190.,first_scientific_launch_UTC=None,
  source_recovery_reads=0,output_readbacks=0,baseline_whole_C_bytes=footprint(),
  events=[dict(stage='Prior preparation carry ONCE',CPU=45.,wall=190.)],
  metering='Controller+single worker process CPU; selected prior meters/conservative authoring charges. Assistant/network orchestration not a complete CPU certificate. End-to-end since first scientific launch separately enforced; original prior packages unchanged.')
 save(LEDGER,x);return x
def charge(stage,cpu,wall=0.,details=None):
 x=initialize();x['charged_CPU_seconds']+=cpu;x['charged_controlled_wall_seconds']+=wall
 x['events'].append(dict(stage=stage,CPU=cpu,wall=wall,details=details,UTC=utc()));save(LEDGER,x);return x
def run(stage,cap,command,*,scientific=False,completion=False):
 x=initialize();reserve=0 if completion else LIMITS['completion_CPU_reserve']
 allowance=min(cap,LIMITS['CPU_seconds']-x['charged_CPU_seconds']-reserve)
 if allowance<=2:raise RuntimeError('CPU_RESERVE_SAFE_STOP')
 if scientific and x['first_scientific_launch_UTC'] is None:
  x['first_scientific_launch_UTC']=utc();save(LEDGER,x)
 wall_left=LIMITS['wall_seconds']-x['charged_controlled_wall_seconds']
 if wall_left<=2:raise RuntimeError('CONTROLLED_WALL_SAFE_STOP')
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',PYTHONHASHSEED='0')
 c0=time.process_time();w0=time.monotonic();r0=resource.getrusage(resource.RUSAGE_CHILDREN)
 p=subprocess.Popen(command,cwd=ROOT,env=env);reason=None;peak=0;max_threads=0
 try:
  while p.poll() is None:
   try:
    s=Path(f'/proc/{p.pid}/stat').read_text().split();cpu=(int(s[13])+int(s[14]))/os.sysconf('SC_CLK_TCK')
    rss=int(s[23])*os.sysconf('SC_PAGE_SIZE');peak=max(peak,rss)
    threads=len(list(Path(f'/proc/{p.pid}/task').iterdir()));max_threads=max(max_threads,threads)
   except (FileNotFoundError,ProcessLookupError):continue
   elapsed=time.monotonic()-w0
   since=None if x['first_scientific_launch_UTC'] is None else (datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(x['first_scientific_launch_UTC'])).total_seconds()
   if cpu+time.process_time()-c0>=allowance-1:reason='CPU_SAFE_STOP'
   elif elapsed>=wall_left-1 or since is not None and since>=LIMITS['wall_seconds']-1:reason='WALL_SAFE_STOP'
   elif rss>LIMITS['RSS_bytes']:reason='RSS_SAFE_STOP'
   elif threads>1:reason='THREAD_SAFE_STOP'
   if reason:p.terminate();break
   time.sleep(.1)
  try:rc=p.wait(timeout=3)
  except subprocess.TimeoutExpired:p.kill();rc=p.wait()
 finally:
  r1=resource.getrusage(resource.RUSAGE_CHILDREN)
  cpu=time.process_time()-c0+r1.ru_utime-r0.ru_utime+r1.ru_stime-r0.ru_stime
  wall=time.monotonic()-w0
  charge(stage,cpu,wall,dict(returncode=p.returncode,safe_stop=reason,peak_RSS_bytes=peak,threads=max_threads,command_SHA256=hashlib.sha256(json.dumps(command).encode()).hexdigest()))
 if reason or rc:raise SystemExit(reason or rc)
 return dict(CPU=cpu,wall=wall,RSS=peak)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--stage',required=True);a.add_argument('--CPU-cap',type=float,required=True);a.add_argument('--scientific',action='store_true');a.add_argument('--completion',action='store_true');a.add_argument('command',nargs=argparse.REMAINDER);v=a.parse_args();cmd=v.command[1:] if v.command[:1]==['--'] else v.command
 print(json.dumps(run(v.stage,v.CPU_cap,cmd,scientific=v.scientific,completion=v.completion)))
