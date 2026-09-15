import ctypes
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import client

class ClientTests(unittest.TestCase):
    def test_wire_matches_native_abi(self):
        self.assertEqual(client.Wire.state.offset,16)
        self.assertEqual(client.Wire.path.offset,64)
        self.assertEqual(client.Wire.status_tick.offset,2112)
        self.assertEqual(client.Wire.activity.offset,2128)
        self.assertEqual(client.Wire.guard_token.offset,2136)
        self.assertEqual(client.Wire.request_token.offset,2152)
        self.assertEqual(ctypes.sizeof(client.Wire),2160)

    def test_invalid_config_prevents_submission(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            with self.assertRaises(ValueError):client.validate_folder(p)
            (p/'config.xml').write_text('<broken',encoding='utf-8')
            with self.assertRaises(ValueError):client.validate_folder(p)

    def test_nested_graphics_config_is_found(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'한국어 팩').mkdir()
            (p/'한국어 팩/config.xml').write_text('<record><list id="maps"><record from="logo" to="graphics/pictures/club/1/logo"/></list></record>',encoding='utf-8')
            self.assertEqual(client.validate_folder(p)[1:],(1,1))

    def test_other_client_blocks_install_and_submission(self):
        with patch.object(client.K,'CreateMutexW',return_value=101), patch.object(client.K,'WaitForSingleObject',return_value=258), patch.object(client.K,'CloseHandle'), patch.object(client,'install') as install:
            with self.assertRaisesRegex(RuntimeError,'다른 새로고침'):client.request(1)
            install.assert_not_called()

    def test_incomplete_or_timed_out_request_cannot_be_replaced(self):
        for state,code in [(1,0),(2,0),(4,21)]:
            wire=client.Wire();wire.magic=0x464d475241504831;wire.version=1;wire.state=state;wire.code=code
            with patch.object(client.K,'CreateMutexW',return_value=101), patch.object(client.K,'WaitForSingleObject',return_value=0), patch.object(client.K,'CloseHandle'), patch.object(client.K,'ReleaseMutex'), patch.object(client.K,'OpenFileMappingW',return_value=102), patch.object(client.K,'MapViewOfFile',return_value=ctypes.addressof(wire)), patch.object(client.K,'UnmapViewOfFile'), patch.object(client,'install'):
                with self.assertRaises(RuntimeError):client.request(1,'C:/test')
                self.assertEqual(wire.state,state)
                self.assertEqual(wire.operation,0)

if __name__=='__main__':unittest.main()
