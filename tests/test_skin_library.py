from pathlib import Path
import json,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import skin_library as lib
import skins
import skin_import
import full_skins

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        storage=patch.object(skin_import,'skin_root',return_value=self.root/'managed');storage.start();self.addCleanup(storage.stop)
        state=patch.object(lib,'data_root',return_value=self.root/'state');state.start();self.addCleanup(state.stop)
        self.base=self.root/'base';self.base.mkdir()
        (self.base/'ui-widgets_assets_all.bundle').write_bytes(b'original widgets')
        (self.base/'ui-styles_assets_default.bundle').write_bytes(b'original styles')
        self.data=dict(version=2,game_folder='',graphics_folder='',skins=[])
        location=patch.object(lib.installation,'locate',return_value=self.base);location.start();self.addCleanup(location.stop)
        # Simulate a guarded game and an observed installation without inspecting
        # the real running process or writing the user's installation journal.
        for target,name,value in [(lib.client,'request_token',1),
                                  (lib.installed_skins,'data_root',self.root/'state')]:
            mock=patch.object(target,name,return_value=value);mock.start();self.addCleanup(mock.stop)
        inventory=patch.object(lib.live_skin_guard,'inventory',side_effect=lambda pid:dict(
            pid=pid,stamp=1,installed=self.base,current={p.name:{'path':str(p)} for p in self.base.glob('*.bundle')},
            permitted={p.name for p in self.base.glob('*.bundle')}))
        inventory.start();self.addCleanup(inventory.stop)

    def pack(self,name,files):
        folder=self.root/name;folder.mkdir(parents=True)
        for filename,value in files.items():(folder/filename).write_bytes(value)
        result=lib.add(self.data,folder)[0];result['enabled']=True;return result

    def test_sparse_widgets_pack_needs_no_styles_file(self):
        item=self.pack('widgets',{'ui-widgets_assets_all.bundle':b'new'})
        plan=lib.resolve(self.data);composed=lib.compose(plan,self.root/'cache')
        self.assertEqual(plan['changed_bundles'],['ui-widgets_assets_all.bundle'])
        self.assertFalse((composed/'ui-styles_assets_default.bundle').exists())
        self.assertEqual(skins.analyze(item['path'],self.base)['changed_bundles'],plan['changed_bundles'])

    def test_priority_and_toggle_resolve_the_entire_overlapping_file(self):
        first=self.pack('first',{'ui-widgets_assets_all.bundle':b'A'})
        second=self.pack('second',{'ui-widgets_assets_all.bundle':b'B','ui-styles_assets_default.bundle':b'style B'})
        plan=lib.resolve(self.data)
        self.assertEqual(plan['winners']['ui-widgets_assets_all.bundle']['id'],first['id'])
        self.assertEqual(plan['entries'][second['id']]['overridden'],1)
        self.data['skins'].reverse();plan=lib.resolve(self.data)
        self.assertEqual(plan['winners']['ui-widgets_assets_all.bundle']['id'],second['id'])
        second['enabled']=False
        self.assertEqual(lib.resolve(self.data)['changed_bundles'],['ui-widgets_assets_all.bundle'])

    def test_high_priority_original_bytes_cancel_lower_patch(self):
        self.pack('original override',{'ui-widgets_assets_all.bundle':b'original widgets'})
        self.pack('lower',{'ui-widgets_assets_all.bundle':b'changed'})
        self.assertTrue(lib.resolve(self.data)['original'])

    def test_all_off_restores_idempotently_and_ignores_missing_disabled_pack(self):
        self.data['skins']=[dict(id='off',name='removed',path=str(self.root/'missing'),enabled=False)]
        with patch.object(lib.full_skins,'run',return_value={'restored':True,'already_original':True}) as run,patch.object(skins,'installed_folder',return_value=self.base),patch.object(full_skins,'session_folder',return_value=self.root):
            result=lib.apply(123,self.data)
        self.assertTrue(result['composition']['uses_installed'])
        self.assertTrue(result['live_applied'])
        self.assertTrue(result['live']['already_original'])
        self.assertTrue(run.call_args.kwargs['restore']);self.assertIsNone(run.call_args.args[1])

    def test_variant_discovery_adds_independent_disabled_entries_and_deduplicates(self):
        self.pack('variants/Dark/Large',{'ui-widgets_assets_all.bundle':b'A'})
        self.pack('variants/Default/Normal',{'ui-widgets_assets_all.bundle':b'B'})
        self.data['skins']=[];items=lib.add(self.data,self.root/'variants')
        self.assertEqual(len(items),2);self.assertTrue(all(not i['enabled'] for i in items))
        self.assertEqual(lib.add(self.data,self.root/'variants'),[])

    def test_settings_roundtrip_preserves_order_toggles_and_base(self):
        self.pack('first',{'ui-widgets_assets_all.bundle':b'A'})
        item=self.pack('second',{'ui-widgets_assets_all.bundle':b'B'});item['enabled']=False
        self.data['skins'].reverse();path=self.root/'settings.json';lib.save(self.data,path)
        self.assertEqual(lib.load(path),self.data)

    def test_unknown_bundle_and_changed_source_fail_before_game_calls(self):
        item=self.pack('extra',{'unknown.bundle':b'A'})
        with patch.object(lib.full_skins,'run') as run:
            with self.assertRaisesRegex(ValueError,'설치 폴더에 없는'):lib.apply(123,self.data)
            run.assert_not_called()
        self.data['skins']=[];item=self.pack('valid',{'ui-widgets_assets_all.bundle':b'A'})
        plan=lib.resolve(self.data);(Path(item['path'])/'ui-widgets_assets_all.bundle').write_bytes(b'changed after resolve')
        with self.assertRaisesRegex(RuntimeError,'파일이 바뀌'):lib.compose(plan,self.root/'cache')
        self.assertFalse((self.root/'cache'/plan['key']).exists())

    def test_cached_composition_is_reused_and_tampering_is_rejected(self):
        self.pack('skin',{'ui-widgets_assets_all.bundle':b'A'});plan=lib.resolve(self.data)
        folder=lib.compose(plan,self.root/'cache');self.assertEqual(lib.compose(plan,self.root/'cache'),folder)
        (folder/'ui-widgets_assets_all.bundle').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'구성 파일이 변경'):lib.compose(plan,self.root/'cache')

    def test_noop_restore_does_not_send_mutation(self):
        from unittest.mock import Mock
        connection=Mock();state={'active':False}
        result=full_skins.restore_active(connection,self.root,state,lambda s:None)
        self.assertTrue(result['already_original']);connection.command.assert_not_called()

    def test_all_off_uses_installed_even_if_old_settings_point_to_other_original(self):
        self.data['base_folder']=str(self.root/'unused_backup')
        (self.base/'ui-widgets_assets_all.bundle').write_bytes(b'installed mod')
        plan=lib.resolve(self.data)
        self.assertTrue(plan['uses_installed']);self.assertEqual(plan['changed_bundles'],[])
        self.assertIsNone(lib.compose(plan,self.root/'cache'))

    def test_migration_removes_old_original_folder_and_keeps_skin_selection(self):
        self.pack('first',{'ui-widgets_assets_all.bundle':b'A'})
        old=dict(self.data,version=1,base_folder='old backup')
        path=self.root/'old.json';path.write_text(json.dumps(old),encoding='utf-8')
        migrated=lib.load(path)
        self.assertEqual(migrated['version'],2);self.assertNotIn('base_folder',migrated)
        self.assertEqual(migrated['skins'],self.data['skins'])

    def test_eight_file_pack_only_composes_eight_differing_files(self):
        files={f'part{i}.bundle':b'changed' for i in range(8)}
        for name in files:(self.base/name).write_bytes(b'installed')
        self.pack('eight',files)
        plan=lib.resolve(self.data);folder=lib.compose(plan,self.root/'cache')
        self.assertEqual(len(plan['changed_bundles']),8)
        self.assertEqual(len(list(folder.glob('*.bundle'))),8)

    def test_partial_skin_preserves_catalog_without_live_replacing_it(self):
        script_name='common_monoscripts.bundle'
        (self.base/script_name).write_bytes(b'installed script catalog')
        self.pack('skin',{'ui-widgets_assets_all.bundle':b'new widgets'})
        with patch.object(lib.full_skins,'run',return_value={}) as run, \
             patch.object(full_skins,'session_folder',return_value=self.root):
            result=lib.apply(123,self.data)
        self.assertTrue(result['live_applied'],result)
        baseline=run.call_args.kwargs['installed_override']
        self.assertEqual((baseline/script_name).read_bytes(),b'installed script catalog')
        self.assertEqual({p.name for p in run.call_args.args[1].glob('*.bundle')},
                         {'ui-widgets_assets_all.bundle'})
        self.assertEqual((self.base/'ui-widgets_assets_all.bundle').read_bytes(),b'original widgets')
        identity=full_skins.preparation_identity(run.call_args.args[1],baseline,['ui-widgets_assets_all.bundle'])
        self.assertEqual([s['name'] for s in identity['scripts']],[script_name])

    def test_existing_partial_startup_backup_gets_missing_catalog(self):
        startup=self.root/'startup';startup.mkdir()
        name='ui-widgets_assets_all.bundle'
        (startup/name).write_bytes((self.base/name).read_bytes())
        (self.root/'startup.json').write_text(json.dumps(dict(installed=str(self.base),
            files={name:skins._hash(startup/name)})),encoding='utf-8')
        script_name='common_monoscripts.bundle'
        (self.base/script_name).write_bytes(b'installed script catalog')
        self.pack('skin',{name:b'new widgets'})
        with patch.object(lib.full_skins,'run',return_value={}), \
             patch.object(full_skins,'session_folder',return_value=self.root):
            result=lib.apply(123,self.data)
        self.assertTrue(result['live_applied'],result)
        self.assertTrue((startup/script_name).exists())
        self.assertEqual((startup/name).read_bytes(),b'original widgets')

    def test_unconfirmed_script_catalog_stops_before_live_apply(self):
        self.pack('skin',{'ui-widgets_assets_all.bundle':b'new widgets'})
        (self.base/'common_monoscripts.bundle').write_bytes(b'changed catalog')
        view=dict(pid=123,stamp=1,installed=self.base,
                  current={p.name:{'path':str(p)} for p in self.base.glob('*.bundle')},
                  permitted={'ui-widgets_assets_all.bundle','ui-styles_assets_default.bundle'})
        with patch.object(lib.live_skin_guard,'inventory',return_value=view), \
             patch.object(lib.full_skins,'run') as run, \
             patch.object(full_skins,'session_folder',return_value=self.root):
            result=lib.apply(123,self.data)
        self.assertFalse(result['live_applied'])
        self.assertIn('common_monoscripts.bundle',result['live_error'])
        run.assert_not_called()
        self.assertFalse((self.root/'startup.json').exists())

if __name__=='__main__':unittest.main()
