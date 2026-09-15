from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import bundle_inventory as inventory
import full_skins


class InventoryTests(TestCase):
    def record(self, folder, kind, actual):
        expected=folder/(kind+'.expected.json')
        expected.write_text(json.dumps([{'class':'FM.UI.Validator','name':'Validator','count':1}]),encoding='utf-8')
        loaded=folder/(kind+'.loaded.jsonl')
        loaded.write_text(''.join(json.dumps(row)+'\n' for row in actual),encoding='utf-8')
        return dict(name='layout.bundle',kind=kind,expected_inventory=str(expected),inventory=str(loaded))

    def test_both_sides_missing_same_script_are_rejected(self):
        with TemporaryDirectory() as temp:
            folder=Path(temp)
            records=[self.record(folder,kind,[]) for kind in ('skin','original')]
            with self.assertRaises(inventory.AssetInventoryError) as caught:
                inventory.validate_records(records)
            self.assertEqual(len(caught.exception.failures),2)

    def test_same_name_with_wrong_script_class_is_rejected(self):
        with TemporaryDirectory() as temp:
            record=self.record(Path(temp),'skin',[{'class':'UnityEngine.ScriptableObject','name':'Validator'}])
            with self.assertRaises(inventory.AssetInventoryError):inventory.validate_records([record])

    def test_expected_multiplicity_and_nonpublic_extras(self):
        with TemporaryDirectory() as temp:
            record=self.record(Path(temp),'skin',[{'class':'FM.UI.Validator','name':'Validator'},
                                                  {'class':'Other','name':'Embedded'}])
            inventory.validate_records([record])

    def retry(self, failures):
        with TemporaryDirectory() as temp:
            folder=Path(temp)
            old=[dict(name='layout.bundle',kind='skin',path='first')]
            fresh=[dict(name='layout.bundle',kind='skin',path='fresh')]
            state=dict(key='key',records=old)
            counter=iter(range(10))
            calls=[]
            class Connection:
                def command(self,op,path,index=0):
                    calls.append((op,str(path),index))
                    return {'matching_styles':next(counter)}
            failure=inventory.AssetInventoryError([dict(bundle='layout.bundle',kind='skin',missing=[dict(name='Validator')])])
            with patch.object(full_skins.live_skin_guard,'require'), \
                 patch.object(full_skins,'validate_records',side_effect=[failure]*(failures)+([None] if failures==1 else [])), \
                 patch.object(full_skins,'cached_copies',return_value=fresh) as prepare, \
                 patch.object(full_skins,'fingerprint',return_value=('key',[])), \
                 patch.object(full_skins,'status',return_value={'bundles':1}):
                if failures==2:
                    with self.assertRaises(inventory.AssetInventoryError):
                        full_skins.load_verified_assets(Connection(),1,['layout.bundle'],folder,folder,folder,state,folder/'state.json',lambda s:None)
                else:
                    full_skins.load_verified_assets(Connection(),1,['layout.bundle'],folder,folder,folder,state,folder/'state.json',lambda s:None)
                prepare.assert_called_once()
            self.assertEqual([path for op,path,index in calls if op==22],['first','fresh'])
            self.assertEqual(state['retry_count'],1)
            self.assertEqual(state['rejected'][0]['path'],'first')
            if failures==1:
                self.assertTrue(state['assets_verified']);self.assertEqual(state['records'][0]['path'],'fresh')
            else:
                self.assertEqual(state['records'],[]);self.assertNotIn('assets_verified',state)

    def test_failed_pack_is_replaced_with_fresh_verified_pack(self):self.retry(1)
    def test_second_failure_stops_without_publishing(self):self.retry(2)
