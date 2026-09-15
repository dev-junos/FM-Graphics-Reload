"""Fail a release build when its GUI runtime is unusable or incomplete."""
import argparse
from pathlib import Path

def check_archive(path):
    from PyInstaller.archive.readers import CArchiveReader
    reader=CArchiveReader(str(path))
    names={n.replace('\\','/') for n in reader.toc}
    required={'_tkinter.pyd','tcl86t.dll','tk86t.dll','_tcl_data/init.tcl','_tk_data/tk.tcl',
              'assets/app.ico','assets/icon-256.png','assets/icon-512.png','assets/icon-1024.png'}
    missing=required-names
    modules=reader.open_embedded_archive('PYZ.pyz').toc
    missing.update(name for name in ('tkinter','tkinter.ttk','tkinter.filedialog','tkinter.messagebox','tkinter.scrolledtext',
                                    'window_icon','skin_pool','prepared_skin_cache') if name not in modules)
    if missing:raise RuntimeError('Missing GUI components: '+', '.join(sorted(missing)))
    print('Packaged GUI components verified.')

def check_runtime():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    root=tk.Tk();root.withdraw()
    try:
        style=ttk.Style(root);style.theme_use('clam')
        ttk.Treeview(root,columns=('name',));scrolledtext.ScrolledText(root)
        root.update_idletasks()
        print('GUI runtime verified:',root.tk.call('info','patchlevel'))
    finally:root.destroy()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path)
    args=parser.parse_args()
    check_archive(args.archive) if args.archive else check_runtime()
