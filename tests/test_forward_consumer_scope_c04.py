"""C04 and legacy feed scope isolation; no fit, regrade or source request."""
import contextlib,hashlib,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import site_forward_v4 as build
import site_validate_forward_v4 as check
ROOT=Path(__file__).resolve().parents[1]

class ForwardConsumerScope(unittest.TestCase):
 def test_only_two_explicit_schemas_are_known(self):
  self.assertTrue(build.legacy_feed_run({'schema':'C-PREGAME-RUN-v4'}))
  self.assertFalse(build.legacy_feed_run({'schema':'C04-CURRENT-FORECAST-ONLY-RUN-v1'}))
  for meta in [{},{'schema':'NEW_UNREGISTERED_RUN'}]:
   with self.assertRaisesRegex(AssertionError,'UNKNOWN_PROSPECTIVE_CONSUMER_SCHEMA'):build.legacy_feed_run(meta)
 def fixture(self,root):
  docs=root/'docs';(docs/'data').mkdir(parents=True);prospective=root/'prospective';(prospective/'receipts').mkdir(parents=True)
  (prospective/'receipts/c04.json').write_text(json.dumps({'run_id':'SHADOW'}))
  manifest={'schema':'C-UPCOMING-SITE-v4','categories':[{}]*12,'runs':[],'files':[]}
  p=docs/'data/forward-manifest.json';p.write_text(json.dumps(manifest));(docs/'build.json').write_text(json.dumps({'forward_manifest_SHA256':hashlib.sha256(p.read_bytes()).hexdigest()}))
  return docs,prospective
 def test_shadow_receipt_validation_is_never_skipped(self):
  with tempfile.TemporaryDirectory() as td:
   docs,prospective=self.fixture(Path(td))
   with patch.object(check,'validate_run',return_value=({'schema':'C04-CURRENT-FORECAST-ONLY-RUN-v1'},[])),patch.object(check,'validate_receipt',side_effect=AssertionError('INVALID_SHADOW_RECEIPT')) as receipt:
    with self.assertRaisesRegex(AssertionError,'INVALID_SHADOW_RECEIPT'):check.validate(docs,prospective)
    receipt.assert_called_once()
 def test_unknown_schema_is_validated_then_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   docs,prospective=self.fixture(Path(td))
   with patch.object(check,'validate_run',return_value=({'schema':'UNREGISTERED'},[])),patch.object(check,'validate_receipt',return_value=True) as receipt:
    with self.assertRaisesRegex(AssertionError,'UNKNOWN_PROSPECTIVE_CONSUMER_SCHEMA'):check.validate(docs,prospective)
    receipt.assert_called_once()
 def test_all_actual_receipts_validate_in_their_correct_consumer_scope(self):
  prospective=ROOT/'prospective';proofs=[json.loads(p.read_text()) for p in (prospective/'receipts').glob('*.json')]
  self.assertEqual(len(proofs),7)
  legacy=[];shadow=[]
  for proof in proofs:
   meta,rows=build.validate_run(prospective/'runs'/proof['run_id']);build.validate_receipt(prospective/'runs'/proof['run_id'],proof,meta,rows)
   (legacy if build.legacy_feed_run(meta) else shadow).append((proof['run_id'],len(rows)))
  self.assertEqual(len(legacy),6);self.assertEqual(shadow,[('C-C04-20261110-W10-FIRST-01',75)])
  self.assertEqual(len(check.validate(ROOT/'docs',prospective)['runs']),6)
 def test_actual_legacy_builder_ignores_c04_source_layout_and_preserves_payload(self):
  # C04 intentionally lacks legacy sources/SOURCE_MANIFEST.json. The checked
  # schema gate must run before that layout is accessed; all seven receipts are
  # still validated, and legacy forecast payloads are reproduced exactly.
  self.assertFalse((ROOT/'prospective/runs/C-C04-20261110-W10-FIRST-01/sources/SOURCE_MANIFEST.json').exists())
  with tempfile.TemporaryDirectory() as td:
   docs=Path(td);shutil.copyfile(ROOT/'docs/build.json',docs/'build.json')
   with contextlib.chdir(ROOT):manifest=build.build(Path('prospective'),docs)
   self.assertEqual(len(manifest['runs']),6)
   self.assertNotIn('C-C04-20261110-W10-FIRST-01',{r['run_id'] for r in manifest['runs']})
   for item in manifest['files']:
    self.assertEqual((docs/'data'/item['file']).read_bytes(),(ROOT/'docs/data'/item['file']).read_bytes(),item['category'])

if __name__=='__main__':unittest.main()
