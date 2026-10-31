"""Contract-level statistical directions. No prices, lines or laws are acquired here."""
import math

def point_side(point,line):
 if point is None or line is None or not math.isfinite(point) or not math.isfinite(line):return 'UNAVAILABLE'
 return 'OVER' if point>line else 'UNDER' if point<line else 'ABSTAIN'

def probability_side(under,push,over):
 if any(v is None or not math.isfinite(v) for v in [under,push,over]):return 'UNAVAILABLE'
 if min(under,push,over)<0 or abs(under+push+over-1)>1e-10:raise ValueError('invalid probability complement')
 return 'OVER' if over>under else 'UNDER' if under>over else 'ABSTAIN'

def grade(side,actual,line,state='PLAYED'):
 if state!='PLAYED':return state
 if actual is None:return 'MISSING_ACTUAL'
 if side=='UNAVAILABLE':return 'UNAVAILABLE'
 if side=='ABSTAIN':return 'ABSTAIN'
 if actual==line:return 'PUSH'
 return 'WIN' if (actual>line)==(side=='OVER') else 'LOSS'

def brier(under,push,over,actual,line):
 probability_side(under,push,over)
 truth=[float(actual<line),float(actual==line),float(actual>line)]
 return .5*sum((p-y)**2 for p,y in zip([under,push,over],truth))

def counts(rows):
 result={}
 for side in ['OVER','UNDER']:
  pool=[r for r in rows if r['side']==side];w=sum(r['grade']=='WIN' for r in pool);l=sum(r['grade']=='LOSS' for r in pool)
  result[side]=dict(selected=len(pool),wins=w,losses=l,decided=w+l,rate=w/(w+l) if w+l else None)
 w=result['OVER']['wins']+result['UNDER']['wins'];l=result['OVER']['losses']+result['UNDER']['losses']
 result['COMBINED']=dict(selected=result['OVER']['selected']+result['UNDER']['selected'],wins=w,losses=l,decided=w+l,rate=w/(w+l) if w+l else None)
 return result
