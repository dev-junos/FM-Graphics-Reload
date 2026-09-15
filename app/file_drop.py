"""Native Windows Explorer folder/ZIP drops, with pointer-sized window callbacks."""
import ctypes as C
from ctypes import wintypes as W
import queue

U=C.WinDLL('user32',use_last_error=True);S=C.WinDLL('shell32',use_last_error=True)
PROC=C.WINFUNCTYPE(C.c_ssize_t,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
U.SetWindowLongPtrW.argtypes=[W.HWND,C.c_int,C.c_ssize_t];U.SetWindowLongPtrW.restype=C.c_ssize_t
U.CallWindowProcW.argtypes=[C.c_void_p,W.HWND,W.UINT,W.WPARAM,W.LPARAM];U.CallWindowProcW.restype=C.c_ssize_t
U.GetAncestor.argtypes=[W.HWND,W.UINT];U.GetAncestor.restype=W.HWND
U.IsWindow.argtypes=[W.HWND];U.IsWindow.restype=W.BOOL
S.DragAcceptFiles.argtypes=[W.HWND,W.BOOL];S.DragAcceptFiles.restype=None
S.DragQueryFileW.argtypes=[W.HANDLE,W.UINT,W.LPWSTR,W.UINT];S.DragQueryFileW.restype=W.UINT
S.DragFinish.argtypes=[W.HANDLE];S.DragFinish.restype=None


def read_paths(handle):
    try:
        count=S.DragQueryFileW(handle,0xffffffff,None,0)
        if count>1000:raise ValueError('한 번에 추가할 폴더와 ZIP이 너무 많습니다.')
        paths=[]
        for index in range(count):
            length=S.DragQueryFileW(handle,index,None,0)
            if not length:raise ValueError('드래그한 파일 경로를 읽지 못했습니다.')
            value=C.create_unicode_buffer(length+1)
            if S.DragQueryFileW(handle,index,value,length+1)!=length:raise ValueError('드래그한 파일 경로가 바뀌었습니다.')
            paths.append(value.value)
        return paths
    finally:S.DragFinish(handle)


class FileDrop:
    def __init__(self,root,callback,on_error):
        self.root=root;self.callback=callback;self.on_error=on_error;self.original={};self.closed=False
        self.pending=queue.SimpleQueue();self.timer=None
        self.proc=PROC(self.dispatch)
        root.update_idletasks()
        # Explorer finds the accepting ancestor; do not replace every Tk widget's proc.
        handles={U.GetAncestor(root.winfo_id(),2) or root.winfo_id()}
        try:
            for handle in handles:
                if not handle:continue
                C.set_last_error(0)
                old=U.SetWindowLongPtrW(handle,-4,C.cast(self.proc,C.c_void_p).value)
                if not old:raise C.WinError(C.get_last_error())
                self.original[handle]=old;S.DragAcceptFiles(handle,True)
        except Exception:self.close();raise
        self.timer=root.after(100,self.drain)

    def dispatch(self,hwnd,message,wparam,lparam):
        old=self.original.get(hwnd)
        if message==0x233:
            try:
                paths=read_paths(wparam)
                if not self.closed:self.pending.put(('paths',paths))
            except Exception as exc:
                if not self.closed:self.pending.put(('error',str(exc)))
            return 0
        result=U.CallWindowProcW(old,hwnd,message,wparam,lparam) if old else 0
        if message==0x82:self.original.pop(hwnd,None)
        return result

    def drain(self):
        # Never call Tcl/Tk from the ctypes WNDPROC callback: Tcl may be re-entered
        # while the outer Tk event loop has released its Python thread state.
        self.timer=None
        if self.closed:return
        try:
            while True:
                kind,value=self.pending.get_nowait()
                try:
                    if kind=='paths':self.callback(value)
                    else:self.on_error(value)
                except Exception as exc:self.on_error('드래그 추가 오류: '+str(exc))
        except queue.Empty:pass
        finally:
            if not self.closed:self.timer=self.root.after(100,self.drain)

    def close(self):
        self.closed=True
        if self.timer is not None:
            self.root.after_cancel(self.timer);self.timer=None
        for handle,old in list(self.original.items()):
            if U.IsWindow(handle):
                S.DragAcceptFiles(handle,False);U.SetWindowLongPtrW(handle,-4,old)
        self.original.clear()
