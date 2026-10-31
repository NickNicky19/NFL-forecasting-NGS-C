"""Independent exact contracts; no original website implementation is copied."""
from decimal import Decimal,InvalidOperation
from fractions import Fraction
import math

CATEGORIES={
 'pass_yd':('Passing Yards','passing_yards','signed',1,['QB']),
 'pass_td':('Passing TDs','passing_tds','count',1,['QB']),
 'pass_cmp':('Completions','completions','count',1,['QB']),
 'pass_att':('Pass Attempts','attempts','count',1,['QB']),
 'pass_int':('Interceptions','passing_interceptions','count',1,['QB']),
 'rush_yd':('Rushing Yards','rushing_yards','signed',1,['QB','RB']),
 'rush_att':('Rush Attempts','carries','count',1,['QB','RB']),
 'rec':('Receptions','receptions','count',1,['RB','WR','TE']),
 'rec_yd':('Receiving Yards','receiving_yards','signed',1,['RB','WR','TE']),
 'rush_rec_yd':('Rush + Rec Yards',None,'signed',1,['RB','WR','TE']),
 'anytime_td':('Anytime TD',None,'event',1,['QB','RB','WR','TE']),
 'fpts':('Fantasy Points (PPR)',None,'signed',50,['QB','RB','WR','TE'])}
CHART='nick-chart-ppr-v1'
# Weights in integer 1/50 point coordinates. No binary-float rounding in scoring.
WEIGHTS={'passing_yards':2,'passing_tds':200,'passing_interceptions':-50,'rushing_yards':5,'rushing_tds':300,'receptions':50,'receiving_yards':5,'receiving_tds':300,'fumbles_lost_total':-50,'passing_2pt_conversions':100,'rushing_2pt_conversions':100,'receiving_2pt_conversions':100,'offensive_fumble_recovery_td':300,'kick_return_td':300,'punt_return_td':300,'field_goal_return_td':300}
SIGNED={'passing_yards','rushing_yards','receiving_yards'}
RARE={'offensive_fumble_recovery_td','kick_return_td','punt_return_td','field_goal_return_td'}
def integer(v,signed=False):
 try:
  if v is None or isinstance(v,bool):return None
  d=Decimal(str(v))
  if not d.is_finite() or d!=d.to_integral_value() or (d<0 and not signed):return None
  return int(d)
 except (InvalidOperation,ValueError):return None
def chart(row,played):
 if not played:return None,'UNKNOWN_APPEARANCE'
 z={k:integer(row.get(k),k in SIGNED) for k in WEIGHTS if k not in RARE}
 if any(v is None for v in z.values()):return None,'MISSING_DIRECT_COMPONENT'
 # Qualified zero supersets only, never attribution of a positive broad total.
 if integer(row.get('fumble_recovery_tds'))!=0 or integer(row.get('special_teams_tds'))!=0:return None,'RARE_TD_ATTRIBUTION_UNRESOLVED'
 return sum(WEIGHTS[k]*v for k,v in z.items())/50,'SUPPORTED_EXPLICIT_ZERO_SUBSET'
def target(row,key,played=True):
 if not played:return None
 if key=='fpts':return chart(row,played)[0]
 if key=='anytime_td':
  a,b=integer(row.get('rushing_tds')),integer(row.get('receiving_tds'))
  return None if a is None or b is None else int(a+b>0)
 if key=='rush_rec_yd':
  a,b=integer(row.get('rushing_yards'),True),integer(row.get('receiving_yards'),True)
  return None if a is None or b is None else a+b
 col=CATEGORIES[key][1];return integer(row.get(col),CATEGORIES[key][2]=='signed')
def thresholds_for_line(line,scale):
 d=Decimal(str(line))*scale
 # Under is strictly less than line. Over is strictly greater. Push only on lattice.
 k_floor=int(d.to_integral_value(rounding='ROUND_FLOOR'));k_ceil=int(d.to_integral_value(rounding='ROUND_CEILING'))
 return k_ceil-1,k_floor,d==k_floor
def probs(cdf,line,scale=1):
 lo,hi,on_grid=thresholds_for_line(line,scale)
 u=float(cdf(lo));o=1-float(cdf(hi));p=1-u-o
 if min(u,o,p)<-1e-10 or abs(u+o+p-1)>1e-10:raise ValueError('invalid complementary law')
 return dict(under=max(0,u),push=max(0,p),over=max(0,o))
def grade(actual,line,side,state='PLAYED'):
 if state!='PLAYED':return state
 if actual is None or not math.isfinite(actual):return 'MISSING_ACTUAL'
 if side not in ['OVER','UNDER']:return side
 a,l=Decimal(str(actual)),Decimal(str(line))
 if a==l:return 'PUSH'
 return 'WIN' if (a>l)==(side=='OVER') else 'LOSS'
