from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import prepared_skin_cache as cache
import full_skins


class PreparedCacheTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        mocked = patch.object(cache, 'data_root', return_value=self.root)
        mocked.start();self.addCleanup(mocked.stop)
        self.built = 0

    def builder(self, dest):
        self.built += 1
        records = []
        for kind in ('skin', 'original'):
            folder = dest / kind;folder.mkdir(parents=True)
            bundle = folder / 'layout.bundle';bundle.write_bytes(f'{kind}-{self.built}'.encode())
            expected = folder / 'layout.bundle.expected.json';expected.write_text('[]')
            records.append(dict(name=bundle.name,kind=kind,objects=1,path=str(bundle),
                expected_inventory=str(expected),original_bundle_name=kind,
                clone_bundle_name=f'{kind}-{dest.name}',sha256=cache.digest(bundle)))
        return records

    def get(self, identity='same', slot='initial', forbidden=()):
        return cache.get_or_build(identity,['layout.bundle'],slot,forbidden,self.builder)

    def test_reopen_cache_reuses_files_but_not_process_ids(self):
        first=self.get();first[0].update(index=99,inventory='previous-game.jsonl')
        # Read from the disk index again; no process-local cache is involved.
        second=self.get()
        self.assertEqual(self.built,1)
        self.assertEqual(first[0]['path'],second[0]['path'])
        self.assertNotIn('index',second[0]);self.assertNotIn('inventory',second[0])

    def test_changed_inputs_build_a_new_generation_and_preserve_old_files(self):
        first=self.get();previous=Path(first[0]['path']).read_bytes()
        second=self.get(identity='changed')
        self.assertEqual(self.built,2);self.assertNotEqual(first[0]['path'],second[0]['path'])
        self.assertEqual(Path(first[0]['path']).read_bytes(),previous)

    def test_tampered_bundle_and_expected_metadata_are_rebuilt(self):
        for field in ('path','expected_inventory'):
            records=self.get();Path(records[0][field]).write_bytes(b'corrupt')
            before=self.built;replacement=self.get()
            self.assertEqual(self.built,before+1)
            self.assertNotEqual(records[0]['path'],replacement[0]['path'])

    def test_retry_has_distinct_identities_and_both_slots_survive_restart(self):
        first=self.get();retry=self.get(slot='retry',forbidden=[r['clone_bundle_name'] for r in first])
        self.assertNotEqual(first[0]['clone_bundle_name'],retry[0]['clone_bundle_name'])
        self.assertEqual(self.get()[0]['path'],first[0]['path'])
        self.assertEqual(self.get(slot='retry')[0]['path'],retry[0]['path'])
        self.assertEqual(self.built,2)

    def test_already_loaded_identities_are_not_loaded_twice(self):
        first=self.get();second=self.get(forbidden=[r['clone_bundle_name'] for r in first])
        self.assertEqual(self.built,2)
        self.assertNotEqual(first[0]['clone_bundle_name'],second[0]['clone_bundle_name'])

    def test_failed_build_does_not_publish_a_partial_entry(self):
        def fail(dest):
            dest.mkdir();(dest/'partial.bundle').write_bytes(b'incomplete')
            raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError):
            cache.get_or_build('failure',['layout.bundle'],'initial',(),fail)
        self.assertFalse(list(self.root.rglob('initial.json')))

    def test_index_cannot_select_a_folder_outside_the_cache(self):
        self.get();pointer=next(self.root.rglob('initial.json'))
        pointer.write_text(json.dumps(dict(generation='../../outside',sha256='fake')))
        self.get();self.assertEqual(self.built,2)

    def test_source_changes_during_build_do_not_publish(self):
        with patch.object(full_skins,'preparation_identity',side_effect=['before','after']), \
             patch.object(full_skins,'prepare_copies',side_effect=lambda s,i,c,d,p:self.builder(d)):
            with self.assertRaisesRegex(RuntimeError,'변경'):
                full_skins.cached_copies(self.root,self.root,['layout.bundle'],'initial',[],lambda s:None)
        self.assertFalse(list(self.root.rglob('initial.json')))


class InventoryQueryTests(unittest.TestCase):
    def test_first_apply_and_reapply_each_use_one_fresh_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'skin';installed=root/'base';session=root/'session'
            for p in (source,installed,session):p.mkdir()
            (source/'layout.bundle').write_bytes(b'mod');(installed/'layout.bundle').write_bytes(b'base')
            records=[]
            for kind in ('skin','original'):
                expected=root/(kind+'.expected.json');expected.write_text('[]')
                records.append(dict(name='layout.bundle',kind=kind,path=str(source/'layout.bundle'),
                    expected_inventory=str(expected),original_bundle_name='basecab',clone_bundle_name=kind+'cab'))
            class Connection:
                active=False;loaded=0;original_id=1;queries=0
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def command(self,op,path,index=0):
                    if op==32:path.write_text(json.dumps(dict(active=self.active,bundles=self.loaded)))
                    elif op==22:
                        self.loaded+=1;return dict(matching_styles=self.loaded-1)
                    elif op==23:
                        path.write_text(json.dumps(dict(id=20 if index==0 else 10,name='panel',
                            **{'class':'UnityEngine.UIElements.VisualTreeAsset'}))+'\n')
                    elif op==20:
                        self.queries+=1
                        path.write_text(json.dumps(dict(id=self.original_id,name='panel',
                            **{'class':'UnityEngine.UIElements.VisualTreeAsset'}))+'\n'+
                            json.dumps(dict(id=99,name='skincab',**{'class':'UnityEngine.AssetBundle'}))+'\n')
                    elif op==30:self.active=True
                    elif op==31:self.active=False
                    return dict(matching_styles=1)
            connection=Connection()
            with patch.object(full_skins.live_skin_guard,'require'), \
                 patch.object(full_skins,'session_folder',return_value=session), \
                 patch.object(full_skins.skins,'Session',return_value=connection), \
                 patch.object(full_skins,'shared_copies',return_value=records) as prepare:
                full_skins._run(1,source,installed_override=installed)
                self.assertEqual(connection.queries,1)
                connection.active=False;connection.original_id=2
                full_skins._run(1,source,installed_override=installed)
                self.assertEqual(connection.queries,2)
                prepare.assert_called_once()
                pairs=next(session.rglob('pairs.txt')).read_text()
                self.assertIn('2 20\n',pairs);self.assertNotIn('1 20\n',pairs)
