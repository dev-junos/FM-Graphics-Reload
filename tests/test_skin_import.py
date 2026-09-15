from pathlib import Path
import json,sys,tempfile,unittest,zipfile,stat
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import skin_import as imp

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.storage=self.root/'imports';self.data={'skins':[]}

    def archive(self,name,files):
        path=self.root/name
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as out:
            for name,value in files:out.writestr(name,value)
        return path

    def test_zip_root_uses_archive_name_and_only_imports_bundles(self):
        path=self.archive('한글 스킨 공백.zip',[('ui.bundle',b'a'),('readme.txt',b'not a bundle')])
        items=imp.add(self.data,path,self.storage)
        self.assertEqual(items[0]['name'],'한글 스킨 공백');self.assertFalse(items[0]['enabled'])
        self.assertEqual((Path(items[0]['path'])/'ui.bundle').read_bytes(),b'a')
        self.assertFalse((Path(items[0]['path'])/'readme.txt').exists())
        self.assertEqual(imp.add(self.data,path,self.storage),[])

    def test_nested_parent_and_child_bundle_folders_are_all_independent(self):
        path=self.archive('variants.zip',[('Skin/base.bundle',b'a'),('Skin/Dark/ui.bundle',b'b'),('Skin/Light/ui.bundle',b'c')])
        items=imp.add(self.data,path,self.storage)
        self.assertEqual([i['name'] for i in items],['variants / Skin','variants / Skin / Dark','variants / Skin / Light'])
        self.assertTrue(all(not i['enabled'] for i in items))
        self.assertEqual([(Path(i['path'])/'ui.bundle').read_bytes() for i in items[1:]],[b'b',b'c'])

    def test_windows_path_traversal_reserved_names_and_duplicate_targets_are_rejected(self):
        for bad in ['../escape.bundle',r'..\escape.bundle','/abs.bundle','C:/abs.bundle','folder/CON.bundle','folder/a.bundle:ads','trailing./a.bundle']:
            with self.subTest(path=bad):
                archive=self.archive('bad.zip',[(bad,b'x')])
                with self.assertRaises(ValueError):imp.add(self.data,archive,self.storage)
        archive=self.archive('duplicates.zip',[('UI.bundle',b'a'),('ui.bundle',b'b')])
        with self.assertRaisesRegex(ValueError,'겹치는'):imp.add(self.data,archive,self.storage)
        self.assertEqual(self.data['skins'],[])
        self.assertFalse((self.root/'escape.bundle').exists())

    def test_symlink_archive_member_is_rejected(self):
        member=zipfile.ZipInfo('link.bundle');member.create_system=3;member.external_attr=(stat.S_IFLNK|0o777)<<16
        archive=self.archive('symlink.zip',[(member,b'../../outside')])
        with self.assertRaises(ValueError):imp.add(self.data,archive,self.storage)

    def test_incomplete_or_oversized_archives_do_not_register_a_skin(self):
        archive=self.archive('big.zip',[('ui.bundle',b'12345')])
        with patch.object(imp,'MAX_BYTES',4),self.assertRaisesRegex(ValueError,'크기'):imp.add(self.data,archive,self.storage)
        self.assertEqual(self.data['skins'],[])

    def test_corrupt_zip_and_multiple_drops_report_errors_without_losing_valid_imports(self):
        good=self.archive('good.zip',[('a.bundle',b'a')]);bad=self.root/'broken.zip';bad.write_bytes(b'broken')
        result=imp.add_many(self.data,[bad,good],self.storage)
        self.assertEqual(len(result['errors']),1);self.assertEqual(len(result['added']),1)
        self.assertEqual(len(self.data['skins']),1)

    def test_cached_zip_is_verified_and_changed_zip_creates_a_separate_import(self):
        path=self.archive('skin.zip',[('a.bundle',b'a')]);first=imp.add(self.data,path,self.storage)[0]
        path=self.archive('skin.zip',[('a.bundle',b'b')]);second=imp.add(self.data,path,self.storage)[0]
        self.assertNotEqual(first['path'],second['path'])
        (Path(second['path'])/'a.bundle').write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError,'변경'):imp.add(self.data,path,self.storage)

    def test_removing_zip_variant_preserves_source_and_sibling_and_can_reimport(self):
        path=self.archive('variants.zip',[('Dark/ui.bundle',b'dark'),('Light/ui.bundle',b'light')])
        first,second=imp.add(self.data,path,self.storage)
        self.assertTrue(imp.delete_managed(first,[second],self.storage))
        self.assertFalse(Path(first['path']).exists())
        self.assertEqual((Path(second['path'])/'ui.bundle').read_bytes(),b'light')
        self.assertTrue(path.is_file())
        self.data['skins']=[second]
        restored=imp.add(self.data,path,self.storage)
        self.assertEqual(len(restored),1)
        self.assertEqual((Path(restored[0]['path'])/'ui.bundle').read_bytes(),b'dark')

    def test_deletion_rejects_external_directory_even_if_marked_managed(self):
        source=self.root/'original';source.mkdir();(source/'a.bundle').write_bytes(b'keep')
        with self.assertRaises(ValueError):
            imp.delete_managed(dict(path=str(source),managed=True),[],self.storage)
        self.assertEqual((source/'a.bundle').read_bytes(),b'keep')

    def test_legacy_zip_parent_removal_preserves_registered_child(self):
        archive=self.archive('old.zip',[('Skin/a.bundle',b'parent'),('Skin/Dark/a.bundle',b'child')])
        extracted=imp.extract_zip(archive,self.storage/'archives')
        parent=dict(path=str(extracted/'Skin'),managed=True)
        child=dict(path=str(extracted/'Skin'/'Dark'),managed=True)
        imp.delete_managed(parent,[child],self.storage)
        self.assertFalse((extracted/'Skin'/'a.bundle').exists())
        self.assertEqual((Path(child['path'])/'a.bundle').read_bytes(),b'child')
        imp.delete_managed(child,[],self.storage)
        self.assertFalse(extracted.exists());self.assertTrue(archive.exists())

if __name__=='__main__':unittest.main()
