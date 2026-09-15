from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import skin_pool as pool
import full_skins


class PoolTests(TestCase):
    def test_dependency_cycles_and_shared_identifiers_are_indivisible(self):
        infos = dict(a=dict(owns=['A'],references=['B']),
                     b=dict(owns=['B'],references=['A']),
                     c=dict(owns=['C'],references=[]),
                     d=dict(owns=['C'],references=[]))
        self.assertEqual(list(pool.groups(infos)), [['a','b'],['c','d']])

    def test_only_changed_dependency_component_is_reloaded(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); rows=root/'assets.jsonl';rows.write_text('')
            metadata=dict(a=dict(owns=['A'],references=['B']),
                          b=dict(owns=['B'],references=[]),c=dict(owns=['C'],references=[]))
            def info(path,checksum,unity):return metadata[path.name]
            initial=dict(files=[dict(name=n,skin=n+'skin',original=n+'base') for n in metadata],profile='p')
            with patch.object(pool,'bundle_info',side_effect=info):
                _,keys=pool.plan(root,root,list(metadata),initial,[],None)
                records=[dict(kind=k,name=n,pool_key=v,index=i,inventory=str(rows),expected_inventory=str(rows))
                         for i,((k,n),v) in enumerate(keys.items())]
                state=dict(records=records,complete=True,assets_verified=True)
                changed=json.loads(json.dumps(initial));changed['files'][0]['skin']='a-updated'
                shared,newkeys=pool.plan(root,root,list(metadata),changed,[state],None)
                self.assertEqual(set(shared), {('skin','c'),('original','a'),('original','b'),('original','c')})
                self.assertNotEqual(keys['skin','a'],newkeys['skin','a'])
                # A partially available dependency group cannot be shared.
                state['records']=[r for r in records if (r['kind'],r['name'])!=('original','b')]
                shared,_=pool.plan(root,root,list(metadata),changed,[state],None)
                self.assertNotIn(('original','a'),shared)
                state['complete']=False
                self.assertEqual(pool.plan(root,root,list(metadata),initial,[state],None)[0],{})

    def test_adding_a_previously_external_dependency_invalidates_group(self):
        infos=dict(a=dict(owns=['A'],references=['B']),b=dict(owns=['B'],references=[]))
        self.assertEqual(list(pool.groups({'a':infos['a']})),[['a']])
        self.assertEqual(list(pool.groups(infos)),[['a','b']])

    def test_capacity_counts_only_new_live_records_and_stops_before_preparing(self):
        shared={('original','a'):dict(kind='original',name='a',index=0)}
        keys={('skin','a'):'skin',('original','a'):'base'}
        with patch.object(full_skins,'preparation_identity',return_value={}), \
             patch.object(pool,'plan',return_value=(shared,keys)), \
             patch.object(full_skins,'cached_copies',return_value=[dict(kind='skin',name='a')]) as prepare, \
             patch('unity_support.unitypy'):
            with self.assertRaisesRegex(RuntimeError,'추가 1개 / 남은 0개'):
                full_skins.shared_copies(Path('.'),Path('.'),['a'],[],0,lambda s:None)
            prepare.assert_not_called()
            records=full_skins.shared_copies(Path('.'),Path('.'),['a'],[],1,lambda s:None)
            self.assertEqual(sum(r['shared'] for r in records),1)

    def test_shared_records_are_not_loaded_or_enumerated_again(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp);expected=folder/'expected.json';expected.write_text('[]')
            inventory=folder/'shared.jsonl';inventory.write_text('')
            original=dict(kind='original',name='a',index=4,shared=True,inventory=str(inventory),expected_inventory=str(expected))
            fresh=dict(kind='skin',name='a',path='fresh',expected_inventory=str(expected))
            state=dict(records=[fresh,original]);calls=[]
            class Connection:
                def command(self,op,path,index=0):
                    calls.append((op,index))
                    if op==23:path.write_text('')
                    return dict(matching_styles=5)
            with patch.object(full_skins.live_skin_guard,'require'):
                full_skins.load_verified_assets(Connection(),1,['a'],folder,folder,folder,state,folder/'session.json',lambda s:None)
            self.assertEqual(calls,[(22,0),(23,5)])
            self.assertTrue(state['assets_verified'])
            self.assertEqual(original['index'],4)

    def test_rejected_fresh_assets_retry_without_loading_shared_assets(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            shared=dict(name='layout.bundle',kind='original',shared=True,index=4)
            fresh=dict(name='layout.bundle',kind='skin',path='bad',pool_key='group')
            state=dict(key='key',records=[shared,fresh]);calls=[]
            class Connection:
                def command(self,op,path,index=0):calls.append(op);return dict(matching_styles=5)
            failure=full_skins.AssetInventoryError([dict(bundle='layout.bundle',kind='skin',missing=[dict(name='Validator')])])
            with patch.object(full_skins.live_skin_guard,'require'), \
                 patch.object(full_skins,'validate_records',side_effect=[failure,None]), \
                 patch.object(full_skins,'cached_copies',return_value=[dict(name='layout.bundle',kind='skin',path='fresh'),dict(name='layout.bundle',kind='original',path='unused')]), \
                 patch.object(full_skins,'fingerprint',return_value=('key',[])), \
                 patch.object(full_skins,'status',return_value=dict(bundles=5)):
                full_skins.load_verified_assets(Connection(),1,['layout.bundle'],folder,folder,folder,state,folder/'session.json',lambda s:None)
            self.assertEqual(calls,[22,23,22,23])
            self.assertEqual(state['records'][0],shared)
            self.assertEqual(state['records'][1]['pool_key'],'group')
            self.assertEqual(state['rejected'],[fresh])

    def test_shared_history_inventory_has_one_owner(self):
        item=dict(kind='original',name='a',index=1,clone_bundle_name='base')
        self.assertEqual(pool.unique_records([item,dict(item),dict(item,index=2)]),[item,dict(item,index=2)])
