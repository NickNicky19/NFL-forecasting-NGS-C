import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from context_identity_view_c01 import BASE,read,corrected_rows
class IdentityMetadata(unittest.TestCase):
 def test_source_bound_identity_changes_no_scientific_outputs(self):
  old=read(BASE);new=corrected_rows(old);self.assertEqual(len(old),len(new));self.assertTrue(any(r.get('team') is None for r in old));self.assertTrue(all(r['team'] and r['opponent_team'] for r in new))
  fields=['offer_id','game_id','player_id','method','selected_side','line','actual','appearance','status','mean','median','probabilities','fallback']
  self.assertEqual([[r.get(k) for k in fields] for r in old],[[r.get(k) for k in fields] for r in new])
 def test_conflicting_nonnull_identity_is_not_overwritten(self):
  old=read(BASE);old[0]['team']='INVALID'
  with self.assertRaisesRegex(AssertionError,'CONFLICTING'):corrected_rows(old)
if __name__=='__main__':unittest.main()
