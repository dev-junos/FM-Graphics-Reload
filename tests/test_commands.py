from pathlib import Path
import sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import main

class CommandTests(unittest.TestCase):
    def test_import_command_never_connects_to_game_or_applies_skins(self):
        args=main.parser().parse_args(['--import-skins','folder with spaces','한글.zip'])
        data={'version':2,'skins':[]}
        with patch.object(main.skin_library,'load',return_value=data),patch.object(main.skin_library,'add_many',return_value={'added':[],'errors':[]}) as add,patch.object(main.skin_library,'save') as save,patch.object(main,'fm_pids') as pids,patch.object(main.skin_library,'apply') as apply:
            main.execute(args)
            add.assert_called_once_with(data,['folder with spaces','한글.zip']);save.assert_called_once_with(data)
            pids.assert_not_called();apply.assert_not_called()

if __name__=='__main__':unittest.main()
