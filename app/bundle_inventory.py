"""Check public bundle assets against disk metadata before publishing replacements."""
from collections import Counter
from pathlib import Path
import json


class AssetInventoryError(ValueError):
    def __init__(self, failures):
        self.failures = failures
        names = list(dict.fromkeys(item['name'] for failure in failures for item in failure['missing']))
        super().__init__('스킨 자원의 스크립트 연결을 확인하지 못했습니다: ' + ', '.join(names[:4]))


def script_catalog(folder, fallback, unity):
    result = {}
    # Prefer the scripts belonging to this side of the comparison.
    for directory in dict.fromkeys([Path(fallback), Path(folder)]):
        for path in sorted(directory.glob('*_monoscripts.bundle')):
            for obj in unity.load(str(path)).objects:
                if obj.type.name == 'MonoScript':
                    tree = obj.read_typetree()
                    result[obj.assets_file.name, obj.path_id] = tree['m_Namespace'] + '.' + tree['m_ClassName']
    return result


def required_assets(env, catalog):
    bundle = next(obj for obj in env.objects if obj.type.name == 'AssetBundle').read_typetree()
    # LoadAllAssets returns public assets, not every component or embedded subasset.
    public = {entry['asset']['m_PathID'] for _, entry in bundle['m_Container']
              if entry['asset']['m_FileID'] == 0}
    expected = Counter()
    for obj in env.objects:
        if obj.path_id not in public or obj.type.name != 'MonoBehaviour':
            continue
        tree = obj.read_typetree()
        ref = tree['m_Script']
        owner = obj.assets_file.name if not ref['m_FileID'] else obj.assets_file.externals[ref['m_FileID'] - 1].path.split('/')[-1]
        klass = catalog.get((owner, ref['m_PathID']))
        if owner == 'unity default resources':
            # Built-in script identities in the hash-validated FM26 Unity build.
            klass = {11995: 'UnityEngine.UIElements.VisualTreeAsset',
                     11998: 'UnityEngine.UIElements.StyleSheet',
                     19101: 'UnityEngine.UIElements.PanelSettings',
                     19004: 'UnityEngine.TextCore.Text.TextStyleSheet',
                     19103: 'UnityEngine.UIElements.PanelTextSettings',
                     19001: 'UnityEngine.TextCore.Text.FontAsset',
                     19202: 'UnityEngine.UIElements.ThemeStyleSheet'}.get(ref['m_PathID'])
        if not klass:
            raise ValueError('스킨의 스크립트 정보를 확인하지 못했습니다: ' + tree.get('m_Name', ''))
        expected[klass, tree.get('m_Name', '')] += 1
    return [dict(**{'class': klass}, name=name, count=count)
            for (klass, name), count in sorted(expected.items())]


def validate_records(records):
    failures = []
    for record in records:
        path = record.get('expected_inventory')
        if not path:
            raise ValueError('이전 방식으로 준비된 스킨 자료입니다. FM을 다시 시작한 뒤 적용해 주세요.')
        expected = Counter({(row['class'], row['name']): row['count']
                            for row in json.loads(Path(path).read_text(encoding='utf-8'))})
        actual = Counter((row['class'], row['name']) for row in
                         (json.loads(line) for line in Path(record['inventory']).read_text(encoding='utf-8').splitlines() if line))
        missing = expected - actual
        if missing:
            failures.append(dict(bundle=record['name'], kind=record['kind'], missing=[
                dict(**{'class': klass}, name=name, count=count)
                for (klass, name), count in sorted(missing.items())]))
    if failures:
        raise AssetInventoryError(failures)
