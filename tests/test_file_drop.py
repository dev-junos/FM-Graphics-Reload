from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import sys,unittest,queue
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import file_drop

class DropTests(unittest.TestCase):
    def test_native_unicode_multi_path_drop_decoding_and_release(self):
        class DROPFILES(C.Structure):
            _fields_=[('pFiles',W.DWORD),('x',W.LONG),('y',W.LONG),('fNC',W.BOOL),('fWide',W.BOOL)]
        expected=[r'F:\한글 스킨\다크 버전',r'F:\Downloads\Skin {large} v7.zip']
        payload=('\0'.join(expected)+'\0\0').encode('utf-16-le')
        header=DROPFILES(C.sizeof(DROPFILES),0,0,False,True)
        k=C.WinDLL('kernel32',use_last_error=True)
        k.GlobalAlloc.argtypes=[W.UINT,C.c_size_t];k.GlobalAlloc.restype=W.HANDLE
        k.GlobalLock.argtypes=[W.HANDLE];k.GlobalLock.restype=C.c_void_p
        k.GlobalUnlock.argtypes=[W.HANDLE]
        handle=k.GlobalAlloc(0x42,C.sizeof(header)+len(payload));self.assertTrue(handle)
        ptr=k.GlobalLock(handle);C.memmove(ptr,C.byref(header),C.sizeof(header));C.memmove(ptr+C.sizeof(header),payload,len(payload));k.GlobalUnlock(handle)
        # DragFinish owns and frees the native HDROP allocation.
        self.assertEqual(file_drop.read_paths(handle),expected)

    def test_drop_callback_queues_one_import_and_finishes_on_invalid_input(self):
        receiver=object.__new__(file_drop.FileDrop);receiver.original={};receiver.closed=False
        receiver.pending=queue.SimpleQueue();receiver.timer=None
        receiver.root=Mock();receiver.callback=Mock();receiver.on_error=Mock()
        with patch.object(file_drop,'read_paths',return_value=['a.zip','b']) as read:
            self.assertEqual(receiver.dispatch(1,0x233,2,0),0);read.assert_called_once_with(2)
            receiver.root.after.assert_not_called();receiver.callback.assert_not_called()
            receiver.drain();receiver.callback.assert_called_once_with(['a.zip','b'])
        with patch.object(file_drop.S,'DragQueryFileW',return_value=1001),patch.object(file_drop.S,'DragFinish') as finish:
            with self.assertRaises(ValueError):file_drop.read_paths(99)
            finish.assert_called_once_with(99)

if __name__=='__main__':unittest.main()
