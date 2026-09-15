"""Closing must preserve deferred installation work without repeated prompts."""
from copy import deepcopy
from pathlib import Path
import queue
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from interface import App


class CloseNoticeTests(unittest.TestCase):
    def app(self, pending=True):
        app = App.__new__(App)
        app.data = dict(disk_pending=pending, game_folder='game', skins=[
            dict(id='a', path='skin-a', enabled=True),
            dict(id='b', path='skin-b', enabled=False)])
        app.close_baseline = app.close_state()
        app.busy = False
        app.root = Mock()
        app.tree = Mock()
        app.drop = Mock()
        app.persist = Mock()
        app.say = Mock()
        app.tr = lambda key: key
        return app

    def test_immediate_close_preserves_saved_pending_job_without_prompt(self):
        app = self.app()
        saved = deepcopy(app.data)
        with patch('interface.messagebox.askyesno') as ask:
            app.close()
        ask.assert_not_called()
        app.root.destroy.assert_called_once()
        app.persist.assert_called_once()
        self.assertEqual(app.data, saved)

    def test_new_pending_selection_can_cancel_close(self):
        app = self.app()
        app.data['skins'][1]['enabled'] = True
        with patch('interface.messagebox.askyesno', return_value=False) as ask:
            app.close()
        ask.assert_called_once()
        app.root.destroy.assert_not_called()
        self.assertTrue(app.data['disk_pending'])

    def test_new_pending_selection_is_kept_when_close_confirmed(self):
        app = self.app(False)
        app.data['disk_pending'] = True
        with patch('interface.messagebox.askyesno', return_value=True) as ask:
            app.close()
        ask.assert_called_once()
        app.persist.assert_called_once()
        app.root.destroy.assert_called_once()
        self.assertTrue(app.data['disk_pending'])

    def test_reverting_selection_does_not_repeat_old_notice(self):
        app = self.app()
        app.data['skins'][1]['enabled'] = True
        app.data['skins'][1]['enabled'] = False
        with patch('interface.messagebox.askyesno') as ask:
            app.close()
        ask.assert_not_called()

    def test_disabled_import_and_language_are_not_installation_changes(self):
        app = self.app()
        app.data['language'] = 'en'
        app.data['skins'].append(dict(id='c', path='skin-c', enabled=False))
        with patch('interface.messagebox.askyesno') as ask:
            app.close()
        ask.assert_not_called()

    def test_completed_disk_save_does_not_prompt(self):
        app = self.app()
        app.data['skins'][1]['enabled'] = True
        app.data['disk_pending'] = False
        with patch('interface.messagebox.askyesno') as ask:
            app.close()
        ask.assert_not_called()

    def test_priority_change_with_existing_pending_job_prompts(self):
        app = self.app()
        app.data['skins'][1]['enabled'] = True
        app.close_baseline = app.close_state()
        app.data['skins'].reverse()
        with patch('interface.messagebox.askyesno', return_value=True) as ask:
            app.close()
        ask.assert_called_once()

    def test_running_work_still_blocks_close(self):
        app = self.app()
        app.busy = True
        with patch('interface.messagebox.askyesno') as ask:
            app.close()
        ask.assert_not_called()
        app.root.destroy.assert_not_called()
        app.say.assert_called_once_with('wait_close')

    def test_disk_save_resets_baseline_for_subsequent_pending_work(self):
        app = self.app()
        app.data['disk_pending'] = False
        app.events = queue.Queue()
        app.monitor = Mock()
        app.poll()
        app.data['disk_pending'] = True
        with patch('interface.messagebox.askyesno', return_value=True) as ask:
            app.close()
        ask.assert_called_once()


if __name__ == '__main__':
    unittest.main()
