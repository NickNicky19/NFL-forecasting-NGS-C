"""Verify typed points directly against trusted archived safe JSON rows.

No model deserialization, fitting, new inference, line grading or source calls.
"""
from pathlib import Path
import gzip,hashlib,json,math,zipfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 meta=json.loads((HERE/'COMPLETION_HANDOFF.json').read_bytes())
 binding=meta['durable_archive_binding'];archive=ROOT/binding['path']
 assert archive.stat().st_size==binding['bytes'] and sha(archive.read_bytes())==binding['sha256']
 wire=(HERE/'C_RETAINED_COMPLETION_POINTS_W1_W7.json.gz').read_bytes()
 assert sha(wire)==meta['wire_SHA256']
 payload=json.loads(gzip.decompress(wire));exported=payload['rows']
 assert len(exported)==242 and len({(r['game_id'],r['player_id'],r['category']) for r in exported})==242
 expected=[]
 with zipfile.ZipFile(archive) as z:
  for source in meta['source_bindings']:
   raw=z.read(source['slot']+'/rows.json.gz');done=z.read(source['slot']+'/DONE.json')
   assert sha(raw)==source['row_wire_SHA256'] and sha(done)==source['DONE_SHA256']
   for r in json.loads(gzip.decompress(raw)):
    expected.append(r)
 assert len(expected)==len(exported)
 for e,s in zip(exported,expected):
  assert not {'actual','appearance','line','selected_side','p_over','p_under','odds'} & e.keys()
  for key in ['slot','game_id','player_id','position','team','opponent','season','week','as_of_UTC','mean','median','fallback']:
   assert e[key]==s[key],(key,e['game_id'],e['player_id'])
  assert math.isfinite(e['mean']) and math.isfinite(e['median'])
  assert e['feature_vector_SHA256']==sha(json.dumps(s['features'],separators=(',',':'),allow_nan=False).encode())
  assert e['category']=='pass_cmp' and e['position']=='QB'
 assert sum(bool(r['fallback']) for r in exported)==0
 print(json.dumps({'status':'PASS_ARCHIVE_TO_TYPED_POINT_IDENTITY','queries':242,'mean_median_values_compared':484,'source_weeks':list(range(1,8)),'unsafe_model_loads':0,'new_fits':0,'new_inference':0,'new_actual_offer_grades':0}))
if __name__=='__main__':main()
