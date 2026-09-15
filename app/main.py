import argparse
import faulthandler
import json
from pathlib import Path
import sys
import tkinter as tk
from client import fm_pids
from operations import run
from interface import App
import skins
import full_skins
import skin_library
from window_icon import WindowIcon, enable_dpi
from app_storage import data_root


def enable_crash_log():
    # Keep the handle alive for native Python/Tcl failures in windowed builds.
    global crash_log
    try:
        folder=data_root()/'logs';folder.mkdir(parents=True,exist_ok=True)
        crash_log=(folder/'app-crash.log').open('a',encoding='utf-8')
        faulthandler.enable(file=crash_log,all_threads=True)
    except OSError:pass


def parser():
    result=argparse.ArgumentParser();group=result.add_mutually_exclusive_group()
    group.add_argument('--self-test',action='store_true')
    group.add_argument('--check',action='store_true');group.add_argument('--reload',metavar='FOLDER')
    group.add_argument('--skin-analyze',metavar='FOLDER');group.add_argument('--skin-style',metavar='FOLDER')
    group.add_argument('--skin-apply',metavar='FOLDER');group.add_argument('--skin-restore',action='store_true')
    group.add_argument('--library-analyze',metavar='JSON');group.add_argument('--library-apply',metavar='JSON')
    group.add_argument('--import-skins',nargs='+',metavar='PATH');result.add_argument('--output')
    return result


def execute(args):
    if args.self_test:return gui_self_test()
    if args.library_apply and not fm_pids():return execute_guarded(args)
    if (args.reload or args.skin_style or args.skin_apply or args.skin_restore or args.library_apply):
        from game_state import Guard
        pid,=fm_pids()
        with Guard(pid):return execute_guarded(args)
    return execute_guarded(args)


def gui_self_test():
    """Construct the packaged UI without touching the user's library or game."""
    import os
    from tempfile import TemporaryDirectory
    from resources import resource
    original=os.environ.get('LOCALAPPDATA')
    with TemporaryDirectory(prefix='fmgr-gui-check-') as directory:
        os.environ['LOCALAPPDATA']=directory
        root=None
        try:
            enable_dpi()
            root=tk.Tk();root.withdraw();icons=WindowIcon(root)
            app=App(root);root.update_idletasks()
            default_language=app.language
            if default_language!='en':raise RuntimeError('Fresh settings must default to English.')
            titles=[];donation_checks=[]
            import donation
            for language in ('ko','en'):
                app.language=language;app.apply_language();root.update_idletasks();titles.append(root.title())
                if donation.details():
                    donation.show(app);window=app.donation_window;window.withdraw();root.update_idletasks()
                    donation_checks.append(dict(language=language,title=window.title(),qr_pixels=window.qr.width()))
                    window.destroy()
            return dict(gui_ready=True,default_language=default_language,tcl=root.tk.call('info','patchlevel'),titles=titles,
                        icon_dpi=icons.dpi[1],icon_pixels=icons.sizes,
                        icon_png_sizes=[p.width() for p in icons.photos],donation=donation_checks)
        finally:
            if root is not None:root.destroy()
            if original is None:os.environ.pop('LOCALAPPDATA',None)
            else:os.environ['LOCALAPPDATA']=original


def execute_guarded(args):
    if args.import_skins:
        data=skin_library.load();result=skin_library.add_many(data,args.import_skins);skin_library.save(data)
        return dict(result,total_skins=len(data['skins']),settings=str(skin_library.settings_path()))
    if args.library_analyze or args.library_apply:
        data=skin_library.load(args.library_analyze or args.library_apply)
        if args.library_analyze:return skin_library.resolve(data)
        pids=fm_pids()
        if len(pids)>1:raise RuntimeError('FM26을 한 개만 실행해 주세요.')
        return skin_library.apply(pids[0] if pids else None,data)
    if args.skin_apply or args.skin_restore:
        pid,=fm_pids();return full_skins.run(pid,args.skin_apply,args.skin_restore)
    if args.skin_analyze or args.skin_style:
        pid,=fm_pids()
        return skins.analyze(args.skin_analyze,skins.installed_folder(pid)) if args.skin_analyze else skins.run_style(pid,args.skin_style)
    return run(args.reload or '',args.check)


if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    enable_crash_log()
    args=parser().parse_args()
    if any(v for k,v in vars(args).items() if k!='output'):
        try:result=execute(args)
        except Exception as exc:result={'error':str(exc)}
        text=json.dumps(result,ensure_ascii=False,indent=2)
        if args.output:Path(args.output).write_text(text,encoding='utf-8')
        if sys.stdout:print(text)
        sys.exit(1 if 'error' in result or result.get('errors') or result.get('restart_required') else 0)
    import ctypes
    from resources import resource
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('JunHo.FMGraphicsReload')
    enable_dpi()
    root=tk.Tk()
    icons=WindowIcon(root)
    app=App(root);root.mainloop()
