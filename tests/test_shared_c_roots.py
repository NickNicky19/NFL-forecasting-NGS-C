import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from forward_budget_v4 import tree_bytes,complete_C_roots
class SharedRoots(unittest.TestCase):
 def test_nested_inputs_count_once_and_loose_file_counts(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);child=root/'child';child.mkdir();f=child/'evidence';f.write_bytes(b'known')
   roots=complete_C_roots([root,child,f]);self.assertIn(root,roots);self.assertNotIn(child,roots);self.assertNotIn(f,roots);self.assertEqual(tree_bytes(root),5);self.assertEqual(tree_bytes(f),5)
 def test_current_C_roots_are_not_only_the_callers_list(self):
  workspace=Path('/workspace')
  if workspace.exists():
   roots=complete_C_roots([])
   for p in workspace.iterdir():
    if p.name=='ngs-c' or p.name.startswith('c-'):self.assertTrue(any(p.resolve()==r or p.resolve().is_relative_to(r) for r in roots))
if __name__=='__main__':unittest.main()
