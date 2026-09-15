from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import skins
import live_skin_guard

class SkinTests(unittest.TestCase):
    def test_pack_analysis_reports_missing_and_extra_without_claiming_support(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)/'base';skin=Path(temp)/'skin';base.mkdir();skin.mkdir()
            for p in (base,skin):(p/skins.STYLE_BUNDLE).write_bytes(b'same')
            (base/'layout.bundle').write_bytes(b'old');(skin/'layout.bundle').write_bytes(b'new')
            (base/'missing.bundle').write_bytes(b'x');(skin/'extra.bundle').write_bytes(b'x')
            (skin/'_bak_saved.bundle').write_bytes(b'x')
            result=skins.analyze(skin,base)
            self.assertEqual(result['changed_bundles'],['layout.bundle'])
            self.assertEqual(result['missing_bundles'],['missing.bundle'])
            self.assertEqual(result['added_bundles'],['extra.bundle'])
            self.assertFalse(result['full_skin_supported'])
    def test_style_patch_rejects_changed_asset_references(self):
        base={k:[] for k in skins.STYLE_FIELDS};base['assets']=[{'instanceID':1}]
        new=dict(base,assets=[{'instanceID':2}])
        with patch.object(skins,'normalize_folder',side_effect=lambda x:Path(x)),patch.object(skins,'_style',side_effect=[(new,new),(base,base)]):
            with self.assertRaisesRegex(ValueError,'자원 연결'):skins.build_style_patch('skin','base')
    def test_failed_isolated_evidence_never_reaches_live_apply(self):
        class FakeSession:
            commands=[]
            def __init__(self,pid):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def command(self,op,path):
                self.commands.append(op)
                if op==15:Path(str(path)+'.clone.json').write_text('{}',encoding='utf-8')
                return {}
        with tempfile.TemporaryDirectory() as temp,patch.object(live_skin_guard,'require'),patch.object(skins,'data_root',return_value=Path(temp)),patch.object(skins,'installed_folder',return_value=Path(temp)),patch.object(skins,'build_style_patch',return_value={'colors':[1]}),patch.object(skins,'Session',FakeSession):
            with self.assertRaisesRegex(RuntimeError,'실제 적용을 중단'):skins.run_style(1,'skin')
            self.assertEqual(FakeSession.commands,[14,15])
    def test_session_releases_mutex_when_install_fails(self):
        with patch.object(skins.client.K,'CreateMutexW',return_value=101),patch.object(skins.client.K,'WaitForSingleObject',return_value=0),patch.object(skins.client.K,'ReleaseMutex') as release,patch.object(skins.client.K,'CloseHandle') as close,patch.object(skins.client,'install',side_effect=RuntimeError('failed')):
            with self.assertRaisesRegex(RuntimeError,'failed'):
                with skins.Session(1):pass
            release.assert_called_once_with(101);close.assert_called_once_with(101)

if __name__=='__main__':unittest.main()
