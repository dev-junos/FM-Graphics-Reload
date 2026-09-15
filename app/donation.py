"""Optional, user-opened donation panel; never required for app functionality."""
import json
import tkinter as tk
from tkinter import ttk
from urllib.parse import urlsplit
import webbrowser
from PIL import Image, ImageTk
from resources import resource


def details():
    path=resource('assets/donation.json')
    if not path.is_file():return None
    data=json.loads(path.read_text(encoding='utf-8'))
    url=data.get('url','').strip()
    if not url:return None
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('후원 주소는 유효한 HTTPS 주소여야 합니다.')
    if not resource('assets/donation-qr.png').is_file():
        raise ValueError('후원 QR 이미지가 준비되지 않았습니다.')
    modules=data.get('modules_with_border')
    if type(modules) is not int or not 29<=modules<=185:
        raise ValueError('후원 QR 크기 정보가 올바르지 않습니다.')
    return dict(url=url,modules_with_border=modules)


def qr_image(data,target_size):
    with Image.open(resource('assets/donation-qr.png')) as source:
        image=source.convert('RGB')
    modules=data['modules_with_border']
    if image.width!=image.height or image.width%modules:
        raise ValueError('후원 QR 이미지 크기와 모듈 정보가 맞지 않습니다.')
    pixels=max(1,target_size//modules)*modules
    return image.resize((pixels,pixels),Image.Resampling.NEAREST)


def show(app):
    data=details()
    if data is None:return
    existing=getattr(app,'donation_window',None)
    if existing is not None and existing.winfo_exists():
        existing.lift();existing.focus_set();return
    window=tk.Toplevel(app.root);app.donation_window=window
    window.title(app.tr('donate'));window.transient(app.root);window.resizable(False,False)
    window.iconbitmap(str(resource('assets/app.ico')))
    s=app.scale
    frame=ttk.Frame(window,padding=s.px(18));frame.pack(fill='both',expand=True)
    ttk.Label(frame,text=app.tr('donate_title'),font=app.title_font).pack(anchor='w')
    ttk.Label(frame,text=app.tr('donate_optional'),wraplength=s.px(300),justify='left').pack(anchor='w',pady=s.px((8,12)))
    # Integer pixels per QR module preserve the quiet zone at every DPI.
    window.qr=ImageTk.PhotoImage(qr_image(data,s.px(240)),master=window)
    tk.Label(frame,image=window.qr,bg='white',bd=0,padx=s.px(8),pady=s.px(8)).pack()
    ttk.Label(frame,text=app.tr('donate_scan'),wraplength=s.px(300),justify='center').pack(pady=s.px((10,8)))
    ttk.Button(frame,text=app.tr('donate_open'),command=lambda:webbrowser.open(data['url'])).pack(fill='x')
    ttk.Label(frame,text=app.tr('donate_thanks'),foreground='#6a7689').pack(pady=s.px((10,0)))
    window.bind('<Escape>',lambda event:window.destroy())
