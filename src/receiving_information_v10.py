"""Earlier-only reported opportunity shares and ordinary completion context.

These are descriptive football inputs, not routes, injuries, causal player
talent, or authenticated historical publication snapshots.
"""
import bisect
from collections import defaultdict

import numpy as np
import pandas as pd

from data_v2 import DAY, History

SHARE_SUPPORT=['qualified_team_games5','reported_player_target_rows5','team_targets5','player_targets5','age_latest_days','share_values_missing']
SHARE_VALUES=['latest_same_team_target_share','recent2_share_minus_previous3_share']
COMP_SUPPORT=['qualified_team_passing_games8','attempt_support8','age_latest_days','completion_quality_missing']
COMP_VALUES=['earlier_league_shrunk_team_completion_rate8']


def nonnegative_integer(value):
    return value is not None and np.isfinite(value) and value>=0 and value==round(value)


def team_projection(raw,schedule):
    """All reported positions enter true reported-team count denominators."""
    kick=dict(zip(schedule.game_id,schedule.kickoff))
    assert not raw.duplicated(['game_id','player_id']).any()
    out=[]
    for (game,team),frame in raw.groupby(['game_id','team'],sort=False):
        targets=frame.targets.to_numpy(float)
        attempts=frame.attempts.to_numpy(float)
        comps=frame.completions.to_numpy(float)
        tv=all(nonnegative_integer(v) for v in targets)
        cv=all(nonnegative_integer(a) and nonnegative_integer(c) and c<=a for a,c in zip(attempts,comps))
        first=frame.iloc[0]
        out.append(dict(game_id=game,team=team,season=int(first.season),week=int(first.week),kickoff=float(kick[game]),available=float(kick[game])+7*DAY,targets=float(targets.sum()) if tv else None,attempts=float(attempts.sum()) if cv else None,completions=float(comps.sum()) if cv else None,targets_complete=tv,passing_complete=cv,reported_rows=len(frame)))
    return pd.DataFrame(out)


class ReceivingInformation:
    def __init__(self,players,teams):
        self.teams=History(teams,'team')
        minimal=players[['game_id','player_id','team','available','targets']]
        self.player_games={(r['game_id'],r['player_id']):r for r in minimal.to_dict('records')}
        league=sorted((r for r in teams.to_dict('records') if r['passing_complete']),key=lambda r:(r['available'],r['game_id'],r['team']))
        self.league_times=[r['available'] for r in league]
        self.league_attempts=np.r_[0.,np.cumsum([r['attempts'] for r in league])]
        self.league_comps=np.r_[0.,np.cumsum([r['completions'] for r in league])]

    def share(self,row):
        cutoff=row['kickoff']
        # Filtering qualification is based solely on earlier source fields.
        before=self.teams.before(row['team'],cutoff,10000)
        qualified=[r for r in before if r['targets_complete'] and r['targets']>0][-5:]
        p=[]
        for t in qualified:
            r=self.player_games.get((t['game_id'],row['player_id']))
            if r and r['team']==row['team'] and r['available']<cutoff and nonnegative_integer(r.get('targets')):
                p.append(float(r['targets']))
            else:
                p.append(None) # Absence is not a zero or verified DNP.
        supported=len(qualified)==5 and all(v is not None for v in p)
        support=[float(len(qualified)),float(sum(v is not None for v in p)),float(sum(t['targets'] for t in qualified)) if qualified else np.nan,float(sum(v for v in p if v is not None)) if any(v is not None for v in p) else np.nan,(cutoff-qualified[-1]['kickoff'])/DAY if qualified else np.nan,float(not supported)]
        if not supported:
            return support,[np.nan,np.nan]
        den=[t['targets'] for t in qualified]
        assert all(0<=v<=d for v,d in zip(p,den)), 'PLAYER_TARGETS_EXCEED_REPORTED_TEAM_TARGETS'
        return support,[p[-1]/den[-1],sum(p[-2:])/sum(den[-2:])-sum(p[:3])/sum(den[:3])]

    def completion(self,row):
        cutoff=row['kickoff']
        before=self.teams.before(row['team'],cutoff,10000)
        ts=[r for r in before if r['passing_complete'] and r['attempts']>0][-8:]
        i=bisect.bisect_left(self.league_times,cutoff)
        den=float(sum(t['attempts'] for t in ts))
        supported=bool(den>0 and self.league_attempts[i]>0)
        support=[float(len(ts)),den,(cutoff-ts[-1]['kickoff'])/DAY if ts else np.nan,float(not supported)]
        if not supported:
            return support,[np.nan]
        prior=self.league_comps[i]/self.league_attempts[i]
        quality=(50*prior+sum(t['completions'] for t in ts))/(50+den)
        assert 0<=quality<=1
        return support,[float(quality)]


def feature_schema():
    return dict(version='C-RECEIVING-INFORMATION-SCHEMA-v10-v11',identity=['game_id','player_id_GSIS','team_at_game','position_at_game','cutoff_UTC'],source='Hash-pinned ordinary NFL facts; source row zero is explicit reported count, missing row is not zero',availability='Historical gamekickoff+7days strictly<each example cutoff; current/revised reconstruction, notauthenticatedasof',share_support=dict(zip(SHARE_SUPPORT,['games','reported rows','targets','targets','days','boolean'])),share_values=dict(zip(SHARE_VALUES,['unitless target share','unitless share difference'])),completion_support=dict(zip(COMP_SUPPORT,['games','attempts','days','boolean'])),completion_values={COMP_VALUES[0]:'completions/attempts, 50-attempt prior support'},forbidden=['targetgameactualtargets/attempts/outcomes','future smoothing','NGS targetgame values','routes inferred from snaps','invented injury weights','currentroster joins to old games'],population='Input schema usable from pregame identities; research query membership here includes retrospective stat-row panels and timing-unverified source offers; notauthenticatedliveeligibility')
