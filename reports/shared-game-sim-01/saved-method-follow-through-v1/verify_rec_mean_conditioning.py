"""Reproduce the C/site participation counterexample from pinned source, without network or fitting."""

import argparse
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from contracts_v2 import CATEGORIES
from data_v2 import PHYSICAL, load


WEBSITE_FIXTURES = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const body = fs.readFileSync(process.argv[1], 'utf8');
const sha = crypto.createHash('sha256').update(body).digest('hex');
if (sha !== 'e096048c614ffa50b4c0b39776f2e361d503882ab0a27a8265436175fd207ba8') throw Error('Website source version changed');
const start = body.indexOf('function propFinal('), end = body.indexOf('function twoPointScorers(');
if (start < 0 || end <= start) throw Error('Missing pinned functions');
const bindings = ['ESPN_TO_SLEEPER', 'teamCode'].map(name => body.split('\n').find(line => line.startsWith('const ' + name + ' =')));
if (bindings.some(x => !x)) throw Error('Missing team bindings');
const player = {id:'fixture-player', game_id:'fixture-game', espn_id:'123', team:'DAL'};
const game = {id:'fixture-game',kickoff:'2020-01-01T01:00:00Z',home:'DAL',away:'PHI',state:'post',detail:'Final'};
const board = {season:2020,week:1,players:[player]};
const state = {data:board,games:{[game.id]:game}};
const ctx = vm.createContext({S:state});
vm.runInContext(bindings.join('\n') + '\n' + body.slice(start,end),ctx);
const tests = [];
for (const [name, didNotPlay, rec, targets] of [
  ['explicit_play_zero_involvement',false,'0','0'],
  ['target_with_zero_catches',false,'0','1'],
  ['explicit_dnp',true,'0','0'],
  ['played_missing_rec',false,null,'0']
]) {
  const summary = {header:{id:game.id,season:{year:2020,type:2},week:{number:1},
     competitions:[{id:game.id,date:game.kickoff,status:{type:{state:'post',shortDetail:'Final',completed:true}}}]},
     boxscore:{players:[{team:{abbreviation:'DAL'},statistics:[{name:'receiving',labels:['REC','TGTS'],athletes:[{athlete:{id:'123'},didNotPlay,stats:[rec,targets]}]}]}]}};
  ctx.recordPropEvidence(game.id,summary,board);
  const result = ctx.propStatus(player,'rec',0.5,null);
  tests.push({name,consumer_played:state.propEvents[game.id].players[player.id].played,rec_or_null:result.v,dnp:result.res==='dnp'});
}
if (tests[0].rec_or_null!==0 || tests[1].rec_or_null!==0 || !tests[2].dnp || tests[3].rec_or_null!==null) throw Error('Website predicate changed');
process.stdout.write(JSON.stringify({website_app_sha256:sha,case_origin:'typed logical contract fixtures',cases:tests}));
"""


def verify(website_app):
    """Return the two predicates on identical facts. The site receives explicit appearance."""
    for name, expected in {
        "data_v2.py": "e217c62617ea394a514fbde274e0074274f04a24890522db2af70f3b35ec2b9a",
        "contracts_v2.py": "9321d35ba5c7d7af59684784cbf92322849e968097ab7c01a2990493d061a77a",
    }.items():
        if hashlib.sha256((ROOT / "src" / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Producer version changed: {name}")

    output = subprocess.run(
        ["node", "-e", WEBSITE_FIXTURES, str(website_app)],
        check=True, capture_output=True, text=True
    )
    result = json.loads(output.stdout)
    base = dict.fromkeys(set(PHYSICAL) | {c[1] for c in CATEGORIES.values() if c[1]}
                         | {"fumbles_lost_total", "fumble_recovery_tds"}, 0)
    facts = []
    for i, case in enumerate(result["cases"]):
        facts.append(dict(base, game_id="fixture-game", season=2020, week=1, team="DAL",
                          opponent_team="PHI", position="WR", player_id=f"00-{i:07d}",
                          targets=int(case["name"] == "target_with_zero_catches"),
                          receptions=None if case["name"] == "played_missing_rec" else 0))
    games = [dict(game_id="fixture-game", gameday="2020-01-01", gametime="12:00",
                  home_team="DAL", away_team="PHI", home_score=3, away_score=0)]

    class FixtureInputs:
        def __truediv__(self, name):
            table = {"facts.csv.gz": facts, "schedule.csv": games}[name]
            return io.StringIO(pd.DataFrame(table).to_csv(index=False))

    rows, _, _ = load(FixtureInputs())
    for case, row in zip(result["cases"], rows.itertuples(), strict=True):
        case["C_model_statistical_appearance"] = bool(row.played)
        case["C_training_rec_or_null"] = row.values["rec"]
    actual = [(c["rec_or_null"], c["C_training_rec_or_null"]) for c in result["cases"]]
    if actual != [(0, None), (0, 0), (None, None), (None, None)]:
        raise ValueError("Participation fixture result changed")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("website_app", type=Path, help="Locally held, pinned website output/app.js")
    print(json.dumps(verify(parser.parse_args().website_app), indent=2, allow_nan=False))
