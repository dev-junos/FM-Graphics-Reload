"""Select native icon pixels for the window's actual monitor DPI."""
import ctypes as C
from ctypes import wintypes as W
import tkinter as tk
from resources import resource


def enable_dpi():
    # Before creating Tk. A manifest may already have selected this context.
    user = C.WinDLL('user32', use_last_error=True)
    try:
        user.SetProcessDpiAwarenessContext.argtypes = [C.c_void_p]
        user.SetProcessDpiAwarenessContext.restype = W.BOOL
        user.SetProcessDpiAwarenessContext(C.c_void_p(-4))
    except AttributeError:
        user.SetProcessDPIAware()


class WindowIcon:
    def __init__(self, root):
        self.root = root; self.handles = []; self.dpi = None; self.pending = None
        self.user = C.WinDLL('user32', use_last_error=True)
        definitions = {
            'GetAncestor': ([W.HWND, W.UINT], W.HWND),
            'GetDpiForWindow': ([W.HWND], W.UINT),
            'GetSystemMetricsForDpi': ([C.c_int, W.UINT], C.c_int),
            'LoadImageW': ([W.HINSTANCE, W.LPCWSTR, W.UINT, C.c_int, C.c_int, W.UINT], W.HANDLE),
            'SendMessageW': ([W.HWND, W.UINT, C.c_size_t, C.c_ssize_t], C.c_ssize_t),
            'DestroyIcon': ([W.HANDLE], W.BOOL),
        }
        for name, (args, result) in definitions.items():
            function = getattr(self.user, name); function.argtypes = args; function.restype = result
        # Large PNGs also supply Tk-owned icons for dialogs and shell previews.
        self.photos = [tk.PhotoImage(master=root, file=str(resource(f'assets/icon-{n}.png')))
                       for n in (256, 512, 1024)]
        root.iconphoto(True, *self.photos)
        root.iconbitmap(str(resource('assets/app.ico')))
        root.update_idletasks()
        self.refresh()
        root.bind('<Configure>', self.configure, add='+')
        root.bind('<Map>', self.configure, add='+')
        root.bind('<Destroy>', self.destroy, add='+')

    def configure(self, event):
        if event.widget == self.root and self.pending is None:
            self.pending = self.root.after_idle(self.refresh)

    def refresh(self):
        self.pending = None
        window = self.user.GetAncestor(self.root.winfo_id(), 2)
        dpi = self.user.GetDpiForWindow(window) or 96
        identity = window, dpi
        if identity == self.dpi:
            return
        sizes = [self.user.GetSystemMetricsForDpi(metric, dpi) for metric in (49, 11)]
        icons = []
        try:
            for size in sizes:
                icon = self.user.LoadImageW(None, str(resource('assets/app.ico')), 1, size, size, 0x10)
                if not icon:
                    raise C.WinError(C.get_last_error())
                icons.append(icon)
        except Exception:
            for icon in icons: self.user.DestroyIcon(icon)
            raise
        for kind, icon in enumerate(icons):
            self.user.SendMessageW(window, 0x80, kind, icon)  # WM_SETICON, SMALL/BIG
        for old in self.handles: self.user.DestroyIcon(old)
        self.handles = icons; self.dpi = identity; self.sizes = sizes
        self.root.display_dpi=dpi
        self.root.event_generate('<<WindowDpiChanged>>',when='tail')

    def destroy(self, event):
        if event.widget != self.root:
            return
        if self.pending is not None:
            self.root.after_cancel(self.pending); self.pending = None
        for icon in self.handles: self.user.DestroyIcon(icon)
        self.handles = []
