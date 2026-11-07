"""Append-only identity metadata view; never alters forecasts or grades."""
from pathlib import Path
import json,gzip,hashlib
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/player-context-matchup-01/CANONICAL_REPORT_ROWS.json.gz'
PATCH=ROOT/'artifacts/player-context-matchup-01/ROW_IDENTITY_CORRECTION-v1.json.gz'
def read(p):return json.loads(gzip.decompress(Path(p).read_bytes()))
def corrected_rows(rows=None):
    if rows is None:rows=read(BASE)
    patch=read(PATCH);assert hashlib.sha256(BASE.read_bytes()).hexdigest()==patch['base_CANONICAL_SHA256']
    mapping={r['offer_id']:r for r in patch['corrections']};out=[]
    for row in rows:
        r=dict(row);p=mapping[r['offer_id']]
        assert (r['game_id'],r['player_id'],r['position'])==(p['game_id'],p['player_id'],p['position'])
        assert r.get('team') is None or r['team']==p['team'],'CONFLICTING_RETAINED_IDENTITY'
        r.update(team=p['team'],opponent_team=p['opponent_team'],identity_metadata_version=patch['id']);out.append(r)
    return out
