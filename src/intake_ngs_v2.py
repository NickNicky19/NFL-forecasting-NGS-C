"""Inert source reconciliation only. No fitting, scraping, network or raw publication."""
from html.parser import HTMLParser
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
import json,re,hashlib,argparse
import pandas as pd
class Tables(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.tables=[];self.table=None;self.row=None;self.cell=None;self.ignored=0
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag in ['script','style']:self.ignored+=1
  if tag=='table':self.table={'class':attrs.get('class',''),'rows':[]};self.tables.append(self.table)
  if tag=='tr' and self.table is not None:self.row=[]
  if tag=='td' and self.row is not None:self.cell=[]
 def handle_data(self,data):
  if self.cell is not None and not self.ignored:self.cell.append(data)
 def handle_endtag(self,tag):
  if tag in ['script','style']:self.ignored=max(0,self.ignored-1)
  if tag=='td' and self.cell is not None:self.row.append(' '.join(' '.join(self.cell).split()));self.cell=None
  if tag=='tr' and self.row is not None:
   if self.row:self.table['rows'].append(self.row)
   self.row=None
  if tag=='table':self.table=None
FIELDS=['player_name','team_display','position_display','cush','sep','tay','tay_pct','rec','tar','ctch_pct','yds','td','yac_per_rec','expected_yac_per_rec','avg_yac_above_expectation']
MAP={'cush':'avg_cushion','sep':'avg_separation','tay':'avg_intended_air_yards','tay_pct':'percent_share_of_intended_air_yards','rec':'receptions','tar':'targets','ctch_pct':'catch_percentage','yds':'yards','td':'rec_touchdowns','yac_per_rec':'avg_yac','expected_yac_per_rec':'avg_expected_yac','avg_yac_above_expectation':'avg_yac_above_expectation'}
def reconcile(root,ngs,output):
 j=json.load(open(root/'derived/NGS_2026_W1_W7_Intake.json'));m=json.load(open(root/'PACKAGE_MANIFEST.json'));files={Path(f['path']).name:root/f['path'] for f in m['files']};tables=[];checked=0;mismatch=0;replicas=0
 for item in j['receiving_source_manifest']:
  p=files[item['filename']];parser=Tables();text=p.read_text(encoding='utf-8');parser.feed(text);body=[t['rows'] for t in parser.tables if 'el-table__body' in t['class'] and t['rows']]
  assert len(body)==2 and body[0]==body[1];replicas+=len(body[1]);expected=j['receiving_weekly_display_rows'] if item['period_type']=='weekly' else j['receiving_season_summary_display_rows'];expected=[r for r in expected if r['source_sha256']==item['sha256']];assert len(expected)==len(body[0])
  for row,e in zip(body[0],expected):
   assert len(row)==len(FIELDS)
   # The name cell contains long+short aliases; no native-ID join is inferred.
   assert e['player_name'] in row[0]
   for k,v in zip(FIELDS[1:],row[1:]):checked+=1;mismatch+=int(v!=e[k])
  tables.append(dict(period=item['selected_period'],rows=len(body[0]),body_copies=2,identical=True,script_elements=len(re.findall(r'<script\b',text,re.I)),source_missing_markers=item['raw_missing_marker_cells'],local_path_markers=len(re.findall(r'file://|/Users/|C:\\Users\\',text))))
 n=pd.read_csv(ngs);n=n[(n.season==2026)&(n.season_type=='REG')&n.week.between(1,7)].copy();alias={'AZ':'ARI','LA':'LAR','LVR':'LV','JAC':'JAX','WSH':'WAS'};n['display_team']=n.team_abbr.replace(alias)
 keys=['week','player_display_name','display_team','player_position'];dups=int(n.duplicated(keys,keep=False).sum());exact=missing=ambiguous=cells=compatible=conflicting=unavailable=0;fieldcounts={k:dict(compatible=0,conflicting=0,missing=0) for k in MAP}
 for r in j['receiving_weekly_display_rows']:
  q=n[(n.week==r['week'])&(n.player_display_name==r['player_name'])&(n.display_team==alias.get(r['team_display'],r['team_display']))&(n.player_position==r['position_display'])]
  if not len(q):missing+=1;continue
  if len(q)>1:ambiguous+=1;continue
  exact+=1;z=q.iloc[0]
  for field,col in MAP.items():
   cells+=1;text=r[field].replace('%','').replace(',','')
   if text=='--' or pd.isna(z[col]):unavailable+=1;fieldcounts[field]['missing']+=1;continue
   d=Decimal(text);precision=Decimal(1).scaleb(d.as_tuple().exponent);value=Decimal(str(z[col])).quantize(precision,rounding=ROUND_HALF_UP)
   if value==d:compatible+=1;fieldcounts[field]['compatible']+=1
   else:conflicting+=1;fieldcounts[field]['conflicting']+=1
 result=dict(id='C-USER-NGS-INTAKE-v1',bundle_sha256='3fb2d52d1dc336a4c65ade0f12e2d4774e92f03e200a97bf2b41b2adb6d2f01d',repeated_attachment_same_hash=True,bundle_verifier='PASS30payloadfiles+manifest+checksums',original_files=25,distinct_views=24,passing_primary_png=8,rushing_primary_png=8,receiving_primary_HTML=8,duplicate_passing_week6_excluded=1,receiving_weekly_rows=501,receiving_summary_rows=117,weekly_counts=j['receiving_counts_by_week'],replica_rows_excluded=replicas,inert_HTML_display_cells_checked=checked,inert_HTML_display_mismatches=mismatch,HTML=tables,existing_weekly_ngs_rows=len(n),exact_text_tuple_matches_not_native_identity_qualification=exact,unmatched=missing,ambiguous=ambiguous,existing_duplicate_text_tuples=dups,numeric_cells_compared=cells,display_precision_compatible=compatible,numeric_display_conflicts=conflicting,missing_or_unqualified_cells=unavailable,field_summary=fieldcounts,team_code_rule='Display AZ normalized to standard historical ARI; diagnostic only, no guessed name join or native identity admission',rounding_note='Any residual0.05 difference at one-decimal half-boundary is recorded as ambiguous display rounding, not silently corrected source data',new_evidence='Original weekly pixels/HTML; explicit2026minimum5targets WR/TE coverage and readable display precision. No new numerical receiving rows under diagnostic tuple reconciliation ifallmatched.',already_present='Existing combinedNGS2026receiving weekly rowcount501sameweekcounts; displayprecision comparisons above',still_unqualified=['NativeGSIS/event identity fromHTML notauthenticated; texttuple comparison is diagnostic only','Passing/rushing screenshots need numeric extraction+independentvalidation','Retrospective October31views not pregame publication snapshots','Summary included-game cutoff unknown; summaries excludedfromfeatures','Metric-specific opportunity/model-version provenance inclCP2.0/expectedYAC remainsgated','RawHTML/NGS publicredistributionrights and browsermetadata privacy notcleared'],frozen_experiments_changed=0,new_fits=0,raw_payload_published=False,durable_status='Only public-safe metadata/report in C; rawNGS retainedtemporaryintake pendingrights. Hashes do notclaim recoverableGitHubrawbytes.')
 output.write_text(json.dumps(result,indent=2));print(json.dumps({k:result[k] for k in ['receiving_weekly_rows','exact_text_tuple_matches_not_native_identity_qualification','display_precision_compatible','numeric_display_conflicts','missing_or_unqualified_cells','inert_HTML_display_mismatches']}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--ngs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();reconcile(a.root,a.ngs,a.output)
