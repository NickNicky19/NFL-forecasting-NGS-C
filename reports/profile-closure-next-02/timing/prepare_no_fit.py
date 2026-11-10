"""Finite no-fit diagnosis/parity pass over retained sources."""
import sys,signal,time,resource,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
import receiving_timing_c04 as c
start=time.process_time();wall=time.monotonic()
signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('C04_DIAGNOSIS_180CPU_CAP')))
signal.setitimer(signal.ITIMER_PROF,180)
receipt={'id':'C04-NO-FIT-PREPARE-v1','new_fits':0,'network':0,'code_SHA256':c.sha(ROOT/'src/receiving_timing_c04.py')}
try:
 data=c.prepare();report=c.diagnose(data);receipt.update(status='PASS',raw_query_rows=len(data[0]),old_fit_contracts_checked=len(data[-1]),summary=report['summaries'][0]);print('C04_DIAGNOSIS_PARITY_PASS',receipt['summary'])
except Exception as e:
 receipt.update(status='FAIL',error=str(e));raise
finally:
 signal.setitimer(signal.ITIMER_PROF,0);receipt.update(CPU_seconds=time.process_time()-start,wall_seconds=time.monotonic()-wall,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
 c.write(c.OUT/'PREPARE_RESOURCE.json',receipt)
