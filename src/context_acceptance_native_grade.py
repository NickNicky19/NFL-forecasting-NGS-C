"""Bounded memory-only source transport for existing prospective grading.

No model fitting, line creation, source-clock reuse or original prediction writes.
"""
import hashlib,json,time,resource
from pathlib import Path
from urllib.request import Request,urlopen
from forward_sources_v4 import stamp
from context_sources_c01 import guard
import grade_native_capture_c01 as native
ROOT=Path(__file__).resolve().parents[1]
class MemoryRetriever:
 def __init__(self,cache,limit=3):self.manifest=[];self.limit=limit
 def fetch(self,key,url):
  assert len(self.manifest)<self.limit
  started=stamp()
  with urlopen(Request(url,headers={'User-Agent':'C-manual-acceptance-final-grade','Cache-Control':'no-cache'}),timeout=35) as r:
   body=r.read(8*1024*1024+1);assert len(body)<=8*1024*1024
   headers={k.lower():v for k,v in r.headers.items()};status=r.status
  item=dict(id=key,url=url,started_UTC=started,observed_UTC=stamp(),HTTP_status=status,HTTP_Date=headers.get('date'),HTTP_Age=headers.get('age'),HTTP_Last_Modified=headers.get('last-modified'),bytes=len(body),raw_SHA256=hashlib.sha256(body).hexdigest(),raw_retention='Memory-only upstream bytes; retained consumed factual projection')
  self.manifest.append(item);assert sum(x['bytes'] for x in self.manifest)<=24*1024*1024
  return body,item
if __name__=='__main__':
 guard();native.Retriever=MemoryRetriever
 native.run('401873038','C-NATIVE-GRADE-20261110-CINATL-01')
 guard()
