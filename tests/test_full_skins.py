from pathlib import Path
import json,sys,tempfile,unittest
from unittest.mock import patch
from contextlib import nullcontext
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import full_skins

class FullSkinTests(unittest.TestCase):
    def test_all_off_without_existing_bridge_does_not_inject_or_prepare_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(full_skins.client,'find_process_module',return_value=None),patch.object(full_skins.skins,'Session') as session,patch.object(full_skins,'session_folder',return_value=Path(temp)),patch.object(full_skins.live_skin_guard,'hold',return_value=nullcontext()),patch.object(full_skins.live_skin_guard,'require'),patch.object(full_skins,'prepare_copies') as prepare:
            result=full_skins.run(123,restore=True)
            self.assertFalse(result['status']['active']);session.assert_not_called();prepare.assert_not_called()

    def fixture(self,folder,kind,rows):
        p=folder/(kind+'.jsonl');p.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
        return dict(name='layout.bundle',kind=kind,inventory=str(p),original_bundle_name='old.bundle',clone_bundle_name='skin.bundle')
    def asset(self,id,name,cls='UnityEngine.UIElements.VisualTreeAsset'):
        return dict(id=id,name=name,**{'class':cls})
    def test_prefers_actual_original_and_skips_ambiguous_embedded_styles(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);old=[self.asset(10,'panel'),self.asset(11,'inline'),self.asset(12,'inline')]
            new=[self.asset(20,'panel'),self.asset(21,'inline'),self.asset(22,'inline')]
            records=[self.fixture(p,'original',old),self.fixture(p,'skin',new)]
            report=full_skins.make_routes([self.asset(1,'panel')],[self.asset(99,'skin.bundle','UnityEngine.AssetBundle')],records,p/'routes')
            self.assertEqual((p/'routes/pairs.txt').read_text(),'1 20\n10 20\n')
            self.assertEqual(len(report['ambiguous']),1)
    def test_previous_baseline_is_remapped_when_changing_skin(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);previous=self.fixture(p,'previous',[self.asset(5,'panel')]);previous['kind']='original'
            records=[self.fixture(p,'original',[self.asset(10,'panel')]),self.fixture(p,'skin',[self.asset(20,'panel')])]
            full_skins.make_routes([], [self.asset(99,'skin.bundle','UnityEngine.AssetBundle')],records,p/'routes',[previous])
            self.assertEqual((p/'routes/pairs.txt').read_text(),'10 20\n5 20\n')
    def test_missing_rollback_asset_prevents_route_file_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            records=[self.fixture(p,'original',[self.asset(10,'panel')]),self.fixture(p,'skin',[self.asset(20,'different')])]
            with self.assertRaisesRegex(ValueError,'기존 자원'):full_skins.make_routes([],[],records,p/'routes')
            self.assertFalse((p/'routes/pairs.txt').exists())

    def test_all_older_baselines_are_remapped_across_multiple_configurations(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);previous=[]
            for kind,id in [('earlier',5),('recent',6)]:
                item=self.fixture(p,kind,[self.asset(id,'panel')]);item['kind']='original';previous.append(item)
            records=[self.fixture(p,'original',[self.asset(10,'panel')]),self.fixture(p,'skin',[self.asset(20,'panel')])]
            full_skins.make_routes([], [self.asset(99,'skin.bundle','UnityEngine.AssetBundle')],records,p/'routes',previous)
            self.assertEqual((p/'routes/pairs.txt').read_text(),'10 20\n5 20\n6 20\n')

if __name__=='__main__':unittest.main()
