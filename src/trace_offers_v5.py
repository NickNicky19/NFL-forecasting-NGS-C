"""Read-only structural audit of the pinned producer archive; never grade quotes.

Outputs contain counts, schemas and content hashes, not player/quote values.
The input archive remains temporary until its separate rights gate qualifies.
"""
import argparse,csv,gzip,hashlib,io,json,re,zipfile
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timezone

PIN='0f615dd95fb6684ffe84ccd978a49e620ed6ba6c'
REPO='NickNicky19/nicks-expert-nfl-picks'
CATS=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','fpts']
def sha(b):return hashlib.sha256(b).hexdigest()
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def audit(archive,roster,saved=None,schedule=None):
    z=zipfile.ZipFile(archive);prefix=z.namelist()[0];lookup=defaultdict(list)
    with gzip.open(roster,'rt') as f:
        for r in csv.DictReader(f):
            if r['season']=='2026' and r.get('game_type')=='REG' and r.get('sleeper_id') and r.get('gsis_id'):
                lookup[(int(r['week']),r['team'],r['sleeper_id'])].append(r)
    weeks=[];categories=Counter();explicit=Counter();roles=defaultdict(Counter);archives=[];games=set();missing=ambiguous=disagree=0;offer_keys=[]
    def native(path):
        b=z.read(prefix+path)
        return json.loads(b),dict(path=path,Git_blob_SHA=blob(b),SHA256=sha(b),bytes=len(b))
    for w in range(1,8):
        j,info=native(f'output/data/weeks/2026_w{w:02d}.json');c=Counter();e=Counter();rowkeys=set();has=0
        for r in j['players']:
            rowkeys.update(r);team={'LAR':'LA'}.get(r['team'],r['team']);match=lookup.get((w,team,str(r['id'])),[]);ids={m['gsis_id'] for m in match};n=len(r.get('lines',{}));has+=n if r.get('espn_id') else 0
            missing+=n if not ids else 0;ambiguous+=n if len(ids)>1 else 0
            if r.get('espn_id') and not any(str(m['espn_id'])==str(r['espn_id']) for m in match):disagree+=n
            for cat in r.get('lines',{}):
                c[cat]+=1;categories[cat]+=1;roles[cat][r['pos']]+=1
                offer_keys.append((str(r['game_id']),next(iter(ids)) if len(ids)==1 else None,cat,bool(r.get('espn_id'))))
                if r.get('espn_id'):explicit[cat]+=1;e[cat]+=1
        gamekeys={str(g['id']) for g in j['games']};games.update(gamekeys)
        weeks.append(info|dict(season=2026,week=w,games=len(gamekeys),players=len(j['players']),line_views=sum(c.values()),categories=dict(c),explicit_ESPN_views=has,explicit_ESPN_categories=dict(e),retained_player_fields=sorted(rowkeys),kickoff_min=min(g['kickoff'] for g in j['games']),kickoff_max=max(g['kickoff'] for g in j['games']),quote_observation_UTC=None,source_update_UTC=None,clock_tier='POSTGAME_RETRIEVAL_WITHOUT_QUOTE_CLOCK'))
    for path in sorted(n[len(prefix):] for n in z.namelist() if re.fullmatch(re.escape(prefix)+r'output/data/archive/2026_w\d+\.json',n)):
        j,info=native(path);c=Counter();by=defaultdict(Counter);pkeys=set();props=set();future=Counter();before=Counter()
        game={str(g['id']):g for g in j['games']};saved_clock=j.get('saved_at')
        for r in j['players']:
            pkeys.update(r)
            for p in r['props']:
                cat=p['key']
                props.update(p);source=p.get('line_from') or ('fixed' if p.get('source')=='fixed' else 'unknown');c[source]+=1;by[source][cat]+=1
                kick=game.get(str(r['game_id']),{}).get('kickoff')
                if saved_clock and kick:(future if kick>saved_clock else before)[source]+=1
        archives.append(info|dict(season=j['season'],week=j['week'],saved_at=saved_clock,players=len(j['players']),line_views=sum(c.values()),line_from=dict(c),by_source_category={k:dict(v) for k,v in by.items()},kickoff_after_saved_line_views=dict(future),kickoff_at_or_before_saved_line_views=dict(before),retained_player_fields=sorted(pkeys),retained_prop_fields=sorted(props),quote_observation_UTC=None,source_update_UTC=None))
    groups=defaultdict(list)
    for n in z.namelist():
        path=n[len(prefix):]
        if re.fullmatch(r'data/(forward|current-classic)/2026/w\d+/[^/]+\.json.gz',path):groups[str(Path(path).parent)].append((path,n))
    capture_groups=[]
    for group,files in sorted(groups.items()):
        clocks=[];counts=Counter();cats=defaultdict(Counter);keys=set();valid=invalid=0;size=0;hashes=[]
        for path,n in files:
            raw=z.read(n);size+=len(raw);j=json.loads(gzip.decompress(raw));p=j['payload'];clocks.append(p['captured_at']);canonical=json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
            if sha(canonical)==j.get('payload_sha256'):valid+=1
            else:invalid+=1
            hashes.append(dict(path=path,Git_blob_SHA=blob(raw),SHA256=sha(raw),bytes=len(raw)))
            for r in p['rows']:
                keys.update(r);source=r.get('line_from') or 'unknown';counts[source]+=1;cats[source][r['category']]+=1
        capture_groups.append(dict(path=group,files=len(files),bytes=size,local_capture_min=min(clocks),local_capture_max=max(clocks),repeated_line_views=dict(counts),by_source_category={k:dict(v) for k,v in cats.items()},retained_row_fields=sorted(keys),payload_hash_valid=valid,payload_hash_invalid=invalid,publication_clock='NOT_AUTHENTICATED_BY_LOCAL_CAPTURE_CLOCK',quote_update_clock=None,files_manifest=hashes))
    codes=[]
    for path in ['pull/books.py','pull/build.py','pull/grade.py','pull/sources.py','tools/compare_lines.py']:
        b=z.read(prefix+path);codes.append(dict(path=path,Git_blob_SHA=blob(b),SHA256=sha(b),bytes=len(b)))
    matches=[];saved_sources=[]
    if saved and schedule:
        with schedule.open() as f:event={r['game_id']:str(r['espn']) for r in csv.DictReader(f) if r['season']=='2026' and r['game_type']=='REG' and 1<=int(r['week'])<=7}
        assert set(event.values())==games,'REGISTERED_107_GAME_SCHEDULE_MISMATCH'
        for cat in CATS:
            keys=set()
            for p in sorted(saved.glob(f'*-{cat}-H-MULTI-P2_LEAF-E0_OP-W*/rows.json.gz')):
                b=p.read_bytes();saved_sources.append(dict(slot=p.parent.name,SHA256=sha(b),bytes=len(b)))
                for r in json.loads(gzip.decompress(b)):keys.add((event[r['game_id']],r['player_id'],r['target']))
            q=[o for o in offer_keys if o[2]==cat];matches.append(dict(category=cat,C_method='P2_LEAF/H-MULTI/E0_OP retained point identity panel',offer_identity_views=len(q),C_saved_cases=len(keys),identity_intersection=sum(o[:3] in keys for o in q),explicit_ESPN_intersection=sum(o[:3] in keys and o[3] for o in q),unmatched_views=sum(o[:3] not in keys for o in q),performance='NOT_GRADED; native identity membership only, not same-label/timing/contract qualification'))
    return dict(id='C-ACTUAL-OFFER-STRUCTURAL-TRACE-v5',repository=REPO,reference=PIN,archive_SHA256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,ordinary_identity_crosswalk_SHA256=sha(roster.read_bytes()),counts_are='Recorded/repeated views, not independent outcomes or qualified offers; no quote values/names/outcomes published here',historical=dict(weeks=weeks,games=len(games),line_views=sum(categories.values()),explicit_ESPN_line_views=sum(explicit.values()),no_ESPN_line_views=sum(categories.values())-sum(explicit.values()),native_crosswalk_missing_views=missing,native_crosswalk_ambiguous_views=ambiguous,native_ESPN_disagreement_views=disagree,categories=[dict(category=cat,line_views=categories[cat],explicit_ESPN_line_views=explicit[cat],roles=dict(roles[cat]),qualified=0,state='NO_GENUINE_RETAINED_MARKET' if not categories[cat] else 'HELD_SOURCE_PERMISSION_AND_CONTRACT_COMPLETENESS') for cat in CATS]),C_identity_matches=matches,C_saved_source_hashes=saved_sources,archives=archives,capture_groups=capture_groups,code=codes,prior_seasons_main_tree=[n[len(prefix):] for n in z.namelist() if '2025' in n and re.search(r'(offer|prop|archive|/weeks/|/forward/|current-classic)',n,re.I)],executed_performance_comparisons=0,new_fits=0,provider_offer_endpoint_calls=0)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--roster',type=Path,required=True);p.add_argument('--saved',type=Path);p.add_argument('--schedule',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();j=audit(a.archive,a.roster,a.saved,a.schedule);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(j,indent=2)+'\n');print(json.dumps({k:j['historical'][k] for k in ['games','line_views','explicit_ESPN_line_views','native_crosswalk_missing_views','native_crosswalk_ambiguous_views','native_ESPN_disagreement_views']}))
