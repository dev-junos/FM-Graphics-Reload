"""One-screen graphics and partial skin manager."""
import json
import queue
import threading
import time
from pathlib import Path
import game_state
import i18n
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from client import fm_pids, default_folder
from operations import run, save_log
import skins
import skin_library as library
import installation
from file_drop import FileDrop
from skin_table import SkinTable
from text_codec import ui_font
import installed_skins
import skin_maintenance
from version import VERSION
from ui_scale import LayoutScale
from donation_style import DonationStyle


class App:
    def __init__(self,root):
        self.root=root;self.events=queue.Queue();self.busy=False;self.controls=[];self.disk_controls=[];self.load_error='';self.drag=None;self.anchor=None
        self.monitoring=False;self.game=dict(state='disconnected',pid=None);self.state_seen=0;self.next_monitor=0
        self.auto_sync_blocked=False
        self.live_policy=dict(blocked={},checked={});self.policy_error=''
        try:self.data=library.load()
        except (OSError,ValueError) as exc:self.data=library.empty();self.load_error=str(exc)
        self.committed_data=json.loads(json.dumps(self.data))
        self.close_baseline=self.close_state()
        self.language=self.data.get('language','en')
        if self.language not in ('ko','en'):self.language='en'
        self.text_widgets=[];self.last_status=('initial',{})
        self.scale=LayoutScale(root)
        root.configure(bg='#f5f7fb');root.protocol('WM_DELETE_WINDOW',self.close)
        style=ttk.Style();style.theme_use('clam')
        self.font=ui_font(root)
        self.donation_style=DonationStyle(root,self.font)
        self.body_font=tkfont.Font(root=root,family=self.font,size=-self.scale.px(12))
        self.title_font=tkfont.Font(root=root,family=self.font,size=-self.scale.px(16),weight='bold')
        self.section_font=tkfont.Font(root=root,family=self.font,size=-self.scale.px(14),weight='bold')
        root.option_add('*Font',self.body_font)
        style.configure('.',font=self.body_font,background='#f5f7fb',foreground='#263247')
        style.configure('Title.TLabel',font=self.title_font,foreground='#15243b')
        style.configure('TButton',padding=(7,4),background='white',bordercolor='#dce3ed',lightcolor='white',darkcolor='white',borderwidth=1)
        style.map('TButton',background=[('active','#edf2fb')],bordercolor=[('focus','#8ba9e8')])
        style.configure('TEntry',padding=(6,3),fieldbackground='white',bordercolor='#dce3ed',lightcolor='white',darkcolor='white')
        style.configure('Primary.TButton',padding=(9,5),background='#356ae6',foreground='white',bordercolor='#356ae6')
        style.map('Primary.TButton',background=[('disabled','#b5c0d4'),('active','#2459d4')])
        style.configure('Treeview',rowheight=29,background='white',fieldbackground='white',borderwidth=0)
        style.map('Treeview',background=[('selected','#e9efff')],foreground=[('selected','#243b64')])
        style.configure('Treeview.Heading',padding=(3,5),background='#eaf0f7',foreground='#59677b',relief='flat')
        style.configure('Horizontal.TProgressbar',thickness=2,background='#356ae6',troughcolor='#e4eaf3',borderwidth=0)
        frame=ttk.Frame(root,padding=12);frame.pack(fill='both',expand=True)
        header=self.row(frame)
        self.ui(ttk.Label(header,style='Title.TLabel'),'title').pack(side='left')
        self.ui(self.button(header,'',lambda:self.start('check')),'connect').pack(side='right')
        self.lang_choice=ttk.Combobox(header,values=('한국어','English'),state='readonly',width=8)
        self.lang_choice.current(0 if self.language=='ko' else 1);self.lang_choice.pack(side='right',padx=8)
        self.lang_choice.bind('<<ComboboxSelected>>',self.change_language)
        paths=ttk.Frame(frame);paths.pack(fill='x',pady=(10,10))
        paths.columnconfigure(1,weight=1)
        self.path_labels=[];self.path_entries=[]
        label=self.ui(ttk.Label(paths),'graphics');label.grid(row=0,column=0,sticky='w',padx=(0,8));self.path_labels.append(label)
        self.folder=tk.StringVar(value=self.data.get('graphics_folder') or default_folder())
        entry=ttk.Entry(paths,textvariable=self.folder,width=1);entry.grid(row=0,column=1,sticky='ew');self.controls.append(entry);self.path_entries.append(entry)
        button=self.ui(self.button(paths,'',self.choose_graphics),'browse');button.configure(width=7);button.grid(row=0,column=2,padx=(6,0))
        label=self.ui(ttk.Label(paths),'installation');label.grid(row=1,column=0,sticky='w',padx=(0,8),pady=(5,0));self.path_labels.append(label)
        self.base=tk.StringVar(value=self.tr('unknown_game'))
        entry=ttk.Entry(paths,textvariable=self.base,state='readonly',width=1);entry.grid(row=1,column=1,sticky='ew',pady=(5,0));self.path_entries.append(entry)
        button=self.ui(self.button(paths,'',self.choose_base),'browse');button.configure(width=7);button.grid(row=1,column=2,padx=(6,0),pady=(5,0))
        footer=ttk.Frame(frame);footer.pack(side='bottom',fill='x',pady=(8,0))
        skin=ttk.Frame(frame);skin.pack(fill='both',expand=True)
        toolbar=self.row(skin);toolbar.pack_configure(pady=(0,6))
        self.ui(ttk.Label(toolbar,font=self.section_font),'skins').pack(side='left',padx=(0,12))
        self.add_button=self.button(toolbar,'+',self.add_menu);self.add_button.configure(width=3);self.add_button.pack(side='left',padx=(0,4))
        for text,command in [('↑',lambda:self.move(-1)),('↓',lambda:self.move(1))]:
            button=self.button(toolbar,text,command);button.configure(width=3);button.pack(side='left',padx=(0,4))
            self.disk_controls.append(button)
        self.maintenance_button=self.button(toolbar,'▾',self.maintenance_menu)
        self.maintenance_button.configure(width=2);self.maintenance_button.pack(side='right',padx=(2,0))
        delete_button=self.ui(self.button(toolbar,'',self.remove),'delete');delete_button.pack(side='right')
        off_button=self.ui(self.button(toolbar,'',self.all_off),'off');off_button.pack(side='right',padx=(0,6))
        self.disk_controls.extend((delete_button,off_button))
        table=ttk.Frame(skin);table.pack(fill='both',expand=True)
        self.tree=SkinTable(table,self.switch_click,columns=('priority','name','wins','overlap','enabled'),show='headings',height=6,selectmode='extended')
        self.tree.display_font=self.font
        for column,width,anchor in [('priority',38,'center'),('name',300,'w'),('wins',64,'center'),('overlap',64,'center'),('enabled',54,'center')]:
            self.tree.column(column,width=width,minwidth=160 if column=='name' else width,anchor=anchor,stretch=column=='name')
        self.tree.tag_configure('off',foreground='#7b8595');self.tree.tag_configure('on',foreground='#263247')
        self.tree.pack(side='left',fill='both',expand=True)
        scrollbar=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);scrollbar.pack(side='right',fill='y')
        def scrolled(first,last):scrollbar.set(first,last);self.tree.redraw_later()
        self.tree.configure(yscrollcommand=scrolled)
        self.tree.bind('<ButtonPress-1>',self.drag_start);self.tree.bind('<B1-Motion>',self.drag_move)
        self.tree.bind('<ButtonRelease-1>',self.drag_end);self.tree.bind('<space>',self.toggle)
        self.tree.bind('<Control-a>',self.select_all);self.tree.bind('<Control-A>',self.select_all)
        self.tree.bind('<Alt-Up>',lambda e:self.move(-1));self.tree.bind('<Alt-Down>',lambda e:self.move(1))
        self.tree.bind('<Delete>',lambda e:self.remove());self.tree.bind('<Escape>',self.cancel_drag)
        self.tree.bind('<<TreeviewSelect>>',lambda e:self.show_summary(),add='+')
        self.summary=tk.StringVar()
        summary_label=ttk.Label(skin,textvariable=self.summary,foreground='#6a7689',wraplength=620,width=1)
        summary_label.pack(fill='x',pady=(5,0));summary_label.bind('<Configure>',lambda e:summary_label.configure(wraplength=max(100,e.width)))
        self.game_label=tk.StringVar(value=self.tr('disconnected'))
        state_label=ttk.Label(footer,textvariable=self.game_label,foreground='#5b6a81',wraplength=720)
        state_label.pack(fill='x',pady=(0,5));state_label.bind('<Configure>',lambda e:state_label.configure(wraplength=max(100,e.width)))
        actions=self.row(footer)
        self.refresh=self.ui(ttk.Button(actions,command=lambda:self.start('graphics')),'refresh')
        self.apply_button=self.ui(ttk.Button(actions,command=lambda:self.start('apply')),'apply')
        self.all_button=self.ui(ttk.Button(actions,style='Primary.TButton',command=lambda:self.start('all')),'all')
        for index,button in enumerate((self.refresh,self.apply_button,self.all_button)):
            actions.columnconfigure(index,weight=1,uniform='actions');button.grid(row=0,column=index,sticky='ew',padx=(0,6) if index<2 else 0)
        self.bar=ttk.Progressbar(footer,mode='indeterminate');self.bar.pack(fill='x',pady=(6,5))
        self.status=tk.StringVar(value=self.tr('initial'))
        status_row=ttk.Frame(footer);status_row.pack(fill='x')
        self.donation_button=None
        import donation
        try:
            if donation.details():
                self.donation_button=self.ui(self.button(status_row,'',lambda:donation.show(self)),'donate')
                self.donation_button.configure(width=0,style='Donation.TButton',cursor='hand2')
                self.donation_button.pack(side='right',anchor='s',padx=(8,0))
        except (OSError,ValueError):pass
        status_label=tk.Label(status_row,textvariable=self.status,font=self.body_font,wraplength=620,fg='#5b6a81',bg='#f5f7fb',anchor='nw',justify='left',width=1,height=3,bd=0)
        status_label.pack(side='left',fill='x',expand=True);status_label.bind('<Configure>',lambda e:status_label.configure(wraplength=max(100,e.width)))
        self.drop=None
        try:self.drop=FileDrop(root,self.import_sources,self.show_error)
        except OSError:self.say('drop_error')
        self.scale.capture(frame)
        self.refresh_library();self.apply_language();self.apply_scale(initial=True);self.update_buttons();root.after(100,self.poll)
        root.bind('<<WindowDpiChanged>>',self.dpi_changed,add='+')
        if self.load_error:self.show_error(self.load_error)

    def tr(self,key,**values):return i18n.text(key,self.language,**values)

    def ui(self,widget,key):
        self.text_widgets.append((widget,key));widget.configure(text=self.tr(key));return widget

    def say(self,key,**values):
        self.last_status=(key,values);self.status.set(self.tr(key,**values))

    def show_error(self,message):
        self.last_status=('error',dict(message=str(message)));self.status.set(i18n.error(message,self.language))
        try:save_log(dict(action='ui_error',error=str(message)))
        except OSError:pass

    def apply_language(self):
        self.root.title(self.tr('window_title',version=VERSION))
        for widget,key in self.text_widgets:widget.configure(text=self.tr(key))
        for key in ('priority','name','wins','overlap','enabled'):self.tree.heading(key,text=self.tr(key))
        self.scale.columns(self.tree,self.font)
        key,values=self.last_status
        if key=='error':self.status.set(i18n.error(values['message'],self.language))
        elif key=='progress':self.status.set(i18n.progress(values['message'],self.language))
        else:self.status.set(self.tr(key,**values))
        self.game_label.set(self.tr(self.game['state']));self.show_summary()

    def apply_scale(self,initial=False):
        s=self.scale;style=ttk.Style(self.root)
        self.body_font.configure(size=-s.px(12))
        self.title_font.configure(size=-s.px(16))
        self.section_font.configure(size=-s.px(14))
        s.apply()
        style.configure('TButton',padding=s.px((7,4)))
        style.configure('TEntry',padding=s.px((6,3)))
        style.configure('Primary.TButton',padding=s.px((9,5)))
        self.donation_style.apply(s)
        style.configure('Treeview',rowheight=s.px(27))
        style.configure('Treeview.Heading',padding=s.px((3,5)))
        style.configure('Horizontal.TProgressbar',thickness=max(2,s.px(2)))
        style.configure('Vertical.TScrollbar',arrowsize=s.px(12),width=s.px(12))
        s.columns(self.tree,self.font);self.tree.set_scale(s.factor)
        self.root.minsize(s.px(620),s.px(450))
        if initial:self.root.geometry(f'{s.px(650)}x{s.px(480)}')

    def dpi_changed(self,event=None):
        dpi=getattr(self.root,'display_dpi',round(self.scale.factor*96))
        factor=dpi/96
        if abs(factor-self.scale.factor)<.01:return
        self.root.tk.call('tk','scaling',dpi/72)
        self.scale.factor=factor;self.apply_scale()

    def change_language(self,event=None):
        if self.busy:return
        self.language='en' if self.lang_choice.current()==1 else 'ko';self.data['language']=self.language
        try:self.persist()
        except (ValueError,OSError) as exc:self.show_error(exc)
        self.apply_language();self.refresh_library()

    def popup(self,button,entries):
        if self.busy:return
        previous=getattr(self,'popup_menu',None)
        if previous is not None:previous.destroy()
        menu=tk.Menu(self.root,tearoff=False,font=self.body_font);self.popup_menu=menu
        for label,command in entries:
            if label is None:menu.add_separator()
            else:menu.add_command(label=label,command=command)
        try:menu.tk_popup(button.winfo_rootx(),button.winfo_rooty()+button.winfo_height())
        finally:menu.grab_release()

    def add_menu(self):
        self.popup(self.add_button,[(self.tr('add_folder'),self.add_skin),(self.tr('add_zip'),self.add_zip)])

    def maintenance_menu(self):
        entries=[(self.tr('reset_basis'),lambda:self.maintenance('basis')),
                 (self.tr('clear_cache'),lambda:self.maintenance('cache'))]
        if self.data.get('disk_pending'):entries.append((self.tr('retry_disk'),lambda:self.configure_skins(json.loads(json.dumps(self.data)))))
        entries.extend([(None,None),(self.tr('licenses'),self.show_licenses)])
        self.popup(self.maintenance_button,entries)

    def show_licenses(self):
        from resources import resource
        from tkinter.scrolledtext import ScrolledText
        window=tk.Toplevel(self.root);window.title(self.tr('licenses'))
        window.geometry(f'{self.scale.px(680)}x{self.scale.px(460)}');window.iconbitmap(str(resource('assets/app.ico')))
        text=ScrolledText(window,wrap='word',font=self.body_font,padx=self.scale.px(12),pady=self.scale.px(12))
        text.pack(fill='both',expand=True)
        content=resource('LICENSE').read_text(encoding='utf-8')
        content+='\n\n'+resource('THIRD_PARTY_NOTICES.txt').read_text(encoding='utf-8')
        text.insert('1.0',content);text.configure(state='disabled')

    def maintenance(self,action):
        if self.busy or self.load_error:return
        if fm_pids():self.say('maintenance_offline');return
        key='reset_basis' if action=='basis' else 'clear_cache'
        if not messagebox.askokcancel(self.tr(key),self.tr(key+'_confirm'),parent=self.root):return
        snapshot=json.loads(json.dumps(self.data));self.busy=True;self.update_buttons();self.bar.start(15);self.say('working')
        def worker():
            try:
                progress=lambda s:self.events.put(('progress',s))
                result=skin_maintenance.adopt_current(snapshot,progress) if action=='basis' else skin_maintenance.clear_cache(progress)
                self.events.put(('maintenance_done',(action,snapshot,result)))
            except Exception as exc:self.events.put(('maintenance_failed',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def row(self,parent):
        row=ttk.Frame(parent);row.pack(fill='x');return row

    def label(self,parent,text,**pack):
        ttk.Label(parent,text=text,foreground='#56647a').pack(anchor='w',**pack)

    def button(self,parent,text,command):
        button=ttk.Button(parent,text=text,command=command);self.controls.append(button);return button

    def persist(self):
        if self.load_error:raise ValueError(self.tr('stale_settings'))
        self.data['graphics_folder']=self.folder.get();library.save(self.data)
        self.committed_data=json.loads(json.dumps(self.data))

    def dirty(self):
        self.configure_skins(json.loads(json.dumps(self.data)))

    def disk_ready(self):
        # Editing the library never requires the in-game bridge or an idle-state sample.
        return not self.load_error

    def blocked_reason(self,item):
        if self.game['state']=='missing':return ''
        if self.policy_error:return self.policy_error
        if self.live_policy.get('session_error'):return self.live_policy['session_error']
        if self.live_policy.get('checked',{}).get(item['id'])!=item['path']:return self.tr('live_policy_wait')
        return self.live_policy.get('blocked',{}).get(item['id'],'')

    def blocked_switches(self):
        return {i['id'] for i in self.data['skins'] if self.blocked_reason(i)}

    def allow_enable(self,items):
        try:
            pids=fm_pids()
            if len(pids)>1:raise ValueError(self.tr('multiple'))
            if pids:
                probe=dict(self.data,skins=[dict(i,enabled=True) for i in items])
                library.require_live_selection(probe,pids[0])
            return True
        except (ValueError,OSError) as exc:self.show_error(exc);return False

    def configure_skins(self,snapshot,removed=()):
        if self.load_error or not self.disk_ready():
            self.data=json.loads(json.dumps(self.committed_data));self.refresh_library()
            self.show_error(self.load_error) if self.load_error else self.say('disk_state_required')
            return
        previous=json.loads(json.dumps(self.committed_data))
        snapshot['graphics_folder']=self.folder.get()
        self.data=snapshot;self.busy=True;self.guarded=False;self.auto_sync_blocked=True;self.refresh_library();self.update_buttons()
        self.bar.start(15);self.say('disk_work')
        def worker():
            disk=None;errors=[];saved=False
            try:
                disk=library.configure(snapshot,lambda s:self.events.put(('progress',s)))
                saved=True
            except Exception as exc:
                if disk is None:
                    self.events.put(('config_failed',(previous,str(exc))));return
                errors.append(str(exc))
            if disk.get('cleanup_error'):errors.append(disk['cleanup_error'])
            if disk.get('settings_error'):errors.append(disk['settings_error'])
            # Delete after the new selection is saved. Offline restoration is either
            # complete or queued; its backups are independent of the import folder.
            if saved:
                for item in removed:
                    try:library.delete_managed(item,snapshot['skins'])
                    except Exception as exc:errors.append(item['name']+': '+str(exc))
            elif removed:errors.append('설정을 저장하지 못해 보관 스킨 삭제는 보류했습니다.')
            result=dict(disk=disk,removed=len(removed),errors=errors,settings_saved=saved)
            try:save_log(dict(action='configure_skins',result=result))
            except OSError:pass
            self.events.put(('configured',(snapshot,result)))
        threading.Thread(target=worker,daemon=True).start()

    def choose_graphics(self):
        path=filedialog.askdirectory(initialdir=self.folder.get() or None,title=self.tr('choose_graphics'))
        if path:
            self.folder.set(path)
            try:self.persist()
            except (ValueError,OSError) as exc:self.show_error(exc)

    def choose_base(self):
        path=filedialog.askdirectory(initialdir=self.data.get('game_folder') or None,title=self.tr('choose_game'))
        if path:
            try:
                selected=installation.validate(path)
                try:current=installation.locate(self.data)
                except (ValueError,OSError):current=None
                if current is not None and current.resolve()!=(selected/installation.RELATIVE).resolve():
                    if any(i['enabled'] for i in self.data['skins']) or installed_skins.read_state(current)['files']:
                        raise ValueError(self.tr('restore_before_folder'))
                    if (installed_skins.root_for(current)/'pending.json').exists():
                        raise ValueError(self.tr('restore_before_folder'))
                self.data['game_folder']=str(selected);self.persist();self.refresh_library()
            except (ValueError,OSError) as exc:self.show_error(exc)

    def add_skin(self):
        path=filedialog.askdirectory(title=self.tr('choose_skin'))
        if path:self.import_sources([path])

    def add_zip(self):
        paths=filedialog.askopenfilenames(title=self.tr('choose_zip'),filetypes=[('ZIP','*.zip')])
        if paths:self.import_sources(paths)

    def import_sources(self,paths):
        if self.busy:self.say('busy_import');return
        if self.load_error:self.show_error(self.load_error);return
        snapshot=json.loads(json.dumps(self.data))
        self.busy=True;self.update_buttons();self.bar.start(15);self.say('importing')
        def worker():
            try:
                result=library.add_many(snapshot,paths,progress=lambda s:self.events.put(('progress',s)))
                self.events.put(('imported',(snapshot,result)))
            except Exception as exc:self.events.put(('error',('import',str(exc))))
        threading.Thread(target=worker,daemon=True).start()

    def selected_items(self):
        selection=set(self.tree.selection())
        return [item for item in self.data['skins'] if item['id'] in selection]

    def selected(self):
        items=self.selected_items()
        return items[0] if items else None

    def select_all(self,event=None):
        if not self.busy:self.tree.selection_set(self.tree.get_children())
        return 'break'

    def toggle(self,event=None):
        if self.busy or not self.disk_ready():return 'break'
        items=self.selected_items()
        if items:
            active=not all(item['enabled'] for item in items)
            if active and not self.allow_enable(items):return 'break'
            for item in items:item['enabled']=active
            self.dirty()
        return 'break'

    def select_row(self,row,state):
        children=list(self.tree.get_children());selection=set(self.tree.selection())
        if state&0x4:
            if row in selection:self.tree.selection_remove(row)
            else:self.tree.selection_add(row)
            self.anchor=row
        elif state&0x1:
            anchor=self.anchor if self.anchor in children else row
            first,last=sorted((children.index(anchor),children.index(row)))
            self.tree.selection_set(children[first:last+1])
        else:
            if row not in selection:self.tree.selection_set(row)
            self.anchor=row
        self.tree.focus(row);self.tree.focus_set()

    def switch_click(self,row,event):
        if self.busy:return
        self.select_row(row,event.state)
        if event.state&0x5:return
        item=next(i for i in self.data['skins'] if i['id']==row)
        if not item['enabled'] and not self.allow_enable([item]):return
        item['enabled']=not item['enabled'];self.dirty()

    def drag_start(self,event):
        self.tree.hide_tip();self.drag=None
        if self.busy:return 'break'
        row=self.tree.identify_row(event.y)
        if not row or self.tree.identify_region(event.x,event.y)!='cell':return
        self.select_row(row,event.state)
        self.drag=dict(id=row,ids=[i for i in self.tree.get_children() if i in self.tree.selection()],
            x=event.x,y=event.y,column=self.tree.identify_column(event.x),moved=False,modified=bool(event.state&0x5))
        return 'break'

    def drag_move(self,event):
        if self.busy or not self.disk_ready() or not self.drag:return 'break'
        if self.drag['modified'] or self.drag['column']=='#5':return 'break'
        if not self.drag['moved'] and max(abs(event.x-self.drag['x']),abs(event.y-self.drag['y']))<6:return 'break'
        self.drag['moved']=True;self.tree.configure(cursor='fleur')
        if event.y<38:self.tree.yview_scroll(-1,'units')
        elif event.y>self.tree.winfo_height()-22:self.tree.yview_scroll(1,'units')
        target=self.tree.identify_row(event.y);group=self.drag['ids']
        if target in group:return 'break'
        remaining=[key for key in self.tree.get_children() if key not in group]
        if target:
            box=self.tree.bbox(target)
            position=remaining.index(target)+(1 if box and event.y>=box[1]+box[3]/2 else 0)
        else:position=0 if event.y<38 else len(remaining)
        ordered=remaining[:position]+group+remaining[position:]
        self.tree.set_children('',*ordered);self.tree.redraw_later()
        return 'break'

    def drag_end(self,event):
        drag=self.drag;self.drag=None;self.tree.configure(cursor='')
        if self.busy or not drag:return
        if drag['moved']:
            by_id={item['id']:item for item in self.data['skins']}
            self.data['skins']=[by_id[key] for key in self.tree.get_children()]
            self.dirty();self.tree.see(drag['id'])
        elif not drag['modified'] and self.tree.identify_row(event.y)==drag['id']:
            if drag['column']=='#5' and self.tree.identify_column(event.x)=='#5':self.switch_click(drag['id'],event)
            else:self.tree.selection_set(drag['id'])
        return 'break'

    def cancel_drag(self,event=None):
        if self.drag:
            self.tree.set_children('',*[i['id'] for i in self.data['skins']]);self.tree.redraw_later()
        self.drag=None;self.tree.configure(cursor='')
        return 'break'

    def move(self,delta):
        if self.busy or not self.disk_ready():return 'break'
        selected=set(self.tree.selection());items=self.data['skins']
        indices=range(1,len(items)) if delta<0 else range(len(items)-2,-1,-1)
        for index in indices:
            target=index+delta
            if items[index]['id'] in selected and items[target]['id'] not in selected:
                items[index],items[target]=items[target],items[index]
        if selected:
            self.dirty()
            ordered=[i['id'] for i in items if i['id'] in selected]
            self.tree.see(ordered[0] if delta<0 else ordered[-1])
        return 'break'

    def remove(self):
        if self.busy or not self.disk_ready():return
        items=self.selected_items()
        if not items:return
        snapshot=json.loads(json.dumps(self.data))
        ids={i['id'] for i in items};snapshot['skins']=[i for i in snapshot['skins'] if i['id'] not in ids]
        self.configure_skins(snapshot,items)

    def refresh_library(self):
        selected=self.tree.selection();scroll=self.tree.yview();self.preview=None;self.preview_error=''
        try:self.preview=library.preview(self.data)
        except (ValueError,OSError) as exc:self.preview_error=str(exc)
        base=self.preview['base'] if self.preview else None
        self.base.set(str(Path(base).parents[3]) if base else (self.data.get('game_folder') or self.tr('unknown_game')))
        wins={};lost={};conflicts=0
        if self.preview:
            for choices in self.preview['providers'].values():
                wins[choices[0]['id']]=wins.get(choices[0]['id'],0)+1;conflicts+=len(choices)>1
                for item in choices[1:]:lost[item['id']]=lost.get(item['id'],0)+1
        self.tree.delete(*self.tree.get_children())
        self.tree.names={item['id']:item['name'] for item in self.data['skins']}
        for index,item in enumerate(self.data['skins']):
            active=item['enabled'];count=str(wins.get(item['id'],0)) if self.preview else '?'
            parts=item['name'].split(' / ')
            short='\\'.join(['..']*(len(parts)-1)+[parts[-1]])
            self.tree.insert('','end',iid=item['id'],values=(index+1,short,count if active else '—',lost.get(item['id'],0) if active else '—',''),tags=('on' if active else 'off',))
        self.tree.selection_set([key for key in selected if self.tree.exists(key)])
        if scroll:self.tree.yview_moveto(scroll[0])
        self.tree.set_switches({i['id']:i['enabled'] for i in self.data['skins']},self.busy or not self.disk_ready(),self.blocked_switches());self.tree.redraw_later()
        self.summary_values=dict(enabled=sum(i['enabled'] for i in self.data['skins']),files=len(self.preview['providers']) if self.preview else 0,conflicts=conflicts)
        self.show_summary()

    def show_summary(self):
        values=getattr(self,'summary_values',dict(enabled=0,files=0,conflicts=0))
        text=self.tr('invalid_skin') if getattr(self,'preview_error','') else (self.tr('summary',**values) if values['enabled'] else self.tr('summary_off'))
        if self.data.get('disk_pending'):text+=self.tr('pending_short')
        blocked=sum(i['enabled'] and bool(self.blocked_reason(i)) for i in self.data['skins'])
        if blocked:text+=self.tr('live_blocked_count',count=blocked)
        count=len(self.tree.selection());self.summary.set(text+(self.tr('selection',count=count) if count else ''))

    def update_buttons(self):
        self.tree.set_switches({i['id']:i['enabled'] for i in self.data['skins']},self.busy or not self.disk_ready(),self.blocked_switches())
        self.tree.names={i['id']:i['name']+ ('\n\n'+i18n.error(self.blocked_reason(i),self.language) if self.blocked_reason(i) else '') for i in self.data['skins']}
        for control in self.controls:control.configure(state='disabled' if self.busy else 'normal')
        for control in self.disk_controls:control.configure(state='normal' if self.disk_ready() and not self.busy else 'disabled')
        self.lang_choice.configure(state='disabled' if self.busy else 'readonly')
        ready=self.game['state']=='idle' and time.monotonic()-self.state_seen<2.5
        self.refresh.configure(state='normal' if ready and not self.busy else 'disabled')
        blocked=bool(self.policy_error or self.live_policy.get('session_error')) or any(i['enabled'] and self.blocked_reason(i) for i in self.data['skins'])
        for control in (self.all_button,self.apply_button):control.configure(state='normal' if ready and not blocked and not self.busy else 'disabled')
        self.game_label.set(self.tr('locked' if getattr(self,'guarded',False) else self.game['state']))
        self.show_summary()

    def all_off(self):
        if self.busy or not self.disk_ready():return
        for item in self.data['skins']:item['enabled']=False
        self.dirty()

    def start(self,action):
        if self.busy:return
        if action!='check' and (self.game['state']!='idle' or time.monotonic()-self.state_seen>=2.5):
            self.say('state_required');return
        if action in ('apply','all'):
            try:
                library.require_live_selection(self.data,self.game['pid'])
                view=library.preview(self.data);missing=view['missing']
                if missing:
                    raise ValueError('설치 폴더에 없는 파일이 있습니다. FM을 종료한 뒤 스킨을 ON으로 켜면 추가할 수 있습니다: '+', '.join(missing))
                self.data['game_folder']=str(Path(view['base']).parents[3])
            except (ValueError,OSError) as exc:self.show_error(exc);return
            self.data['disk_pending']=True;self.auto_sync_blocked=False
        try:self.persist()
        except (ValueError,OSError) as exc:self.show_error(exc);return
        self.show_summary()
        snapshot=json.loads(json.dumps(self.data));folder=self.folder.get();pid=self.game.get('pid')
        self.busy=True;self.guarded=False;self.update_buttons();self.bar.start(15);self.say('working')
        def worker():
            completed=[];result={}
            try:
                progress=lambda message:self.events.put(('progress',message))
                if action=='check':
                    result=game_state.connect();self.events.put(('connected',result));return
                if not pid:raise RuntimeError(self.tr('state_required'))
                if action in ('apply','all'):library.require_live_selection(snapshot,pid)
                with game_state.Guard(pid):
                    self.events.put(('guarded',None))
                    result={}
                    if action in ('graphics','all'):
                        result['graphics']=run(folder,False,progress);completed.append('graphics')
                    if action in ('apply','all'):
                        result['skins']=library.apply(pid,snapshot,progress);completed.append('skins')
                try:save_log(dict(action=action,result=result))
                except OSError:pass
                self.events.put(('done',(action,result)))
            except Exception as exc:
                if result.get('skins',{}).get('live_applied'):
                    result['skins'].update(restart_required=True,live_error=str(exc))
                    try:save_log(dict(action=action,result=result,warning=str(exc)))
                    except OSError:pass
                    self.events.put(('done',(action,result)));return
                try:save_log(dict(action=action,error=str(exc),completed=completed))
                except OSError:pass
                self.events.put(('error',(action,str(exc),completed)))
        threading.Thread(target=worker,daemon=True).start()

    def monitor(self):
        if self.monitoring or self.busy or time.monotonic()<self.next_monitor:return
        self.monitoring=True;self.next_monitor=time.monotonic()+.75
        snapshot=json.loads(json.dumps(self.data))
        def worker():
            try:result=game_state.read()
            except Exception:result=dict(state='unknown',pid=None)
            result['policy']=dict(blocked={},checked={});result['policy_error']=''
            if result.get('pid'):
                try:result['policy']=library.live_restrictions(snapshot,result['pid'])
                except Exception as exc:result['policy_error']=str(exc)
            elif result['state']!='missing':result['policy_error']=self.tr('live_policy_wait')
            self.events.put(('state',result))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                if kind=='state':
                    self.monitoring=False
                    if not self.busy:
                        if self.game['state']!='missing' and data['state']=='missing':self.auto_sync_blocked=False
                        self.game=data;self.state_seen=time.monotonic()
                        self.live_policy=data.get('policy',dict(blocked={},checked={}))
                        self.policy_error=data.get('policy_error','')
                    self.update_buttons();continue
                if kind=='progress':
                    self.last_status=('progress',dict(message=data));self.status.set(i18n.progress(data,self.language));continue
                if kind=='guarded':self.guarded=True;self.update_buttons();continue
                self.busy=False;self.guarded=False;self.bar.stop()
                # A task can outlast the last sample. Refresh the state before re-enabling actions.
                self.state_seen=0;self.next_monitor=0;self.update_buttons()
                if kind=='connected':
                    self.game=data;self.state_seen=0;self.next_monitor=0;self.say(data['state']);self.refresh_library();self.update_buttons();continue
                if kind=='config_failed':
                    self.data,message=data;self.refresh_library();self.show_error(message);continue
                if kind=='maintenance_done':
                    action,self.data,result=data;self.committed_data=json.loads(json.dumps(self.data))
                    self.refresh_library();self.say('basis_done' if action=='basis' else 'cache_done')
                    try:save_log(dict(action='maintenance_'+action,result=result))
                    except OSError:pass
                    continue
                if kind=='maintenance_failed':
                    try:self.data=library.load();self.committed_data=json.loads(json.dumps(self.data))
                    except (ValueError,OSError):pass
                    self.refresh_library();self.show_error(data);continue
                if kind=='configured':
                    self.data,result=data;self.committed_data=json.loads(json.dumps(self.data))
                    deferred=result['disk'].get('deferred',False)
                    self.auto_sync_blocked=not deferred
                    self.refresh_library();self.say('selection_queued' if deferred else 'disk_done')
                    if result['removed']:self.say('removed_queued' if deferred else 'removed_disk',count=result['removed'])
                    if result['errors']:
                        self.show_error(' / '.join(result['errors']))
                        self.status.set(self.tr('selection_saved_warning' if deferred else 'disk_saved_warning')+' '+i18n.error(' / '.join(result['errors']),self.language))
                    continue
                if kind=='removed':
                    self.data,result=data
                    try:self.persist()
                    except (ValueError,OSError) as exc:self.show_error(exc);self.refresh_library();continue
                    self.refresh_library();self.say('removed',count=len(result['results']))
                    if result['errors']:
                        self.show_error(' / '.join(result['errors']))
                    continue
                if kind=='imported':
                    self.data,result=data
                    try:self.persist()
                    except (ValueError,OSError) as exc:self.show_error(exc);self.refresh_library();continue
                    self.refresh_library();added=result['added']
                    if added:self.tree.selection_set([i['id'] for i in added]);self.tree.see(added[0]['id'])
                    self.say('imported',count=len(added)) if added else self.say('duplicate')
                    if result['errors']:
                        try:save_log(dict(action='import',result=result))
                        except OSError:pass
                        self.show_error(' / '.join(e['error'] for e in result['errors']))
                    continue
                if kind=='error':
                    action,message,*rest=data;self.show_error(message)
                    if action=='all' and rest and 'graphics' in rest[0]:
                        self.status.set(self.tr('partial')+' '+i18n.error(message,self.language))
                    continue
                action,result=data
                skin_result=result.get('skins',{})
                if skin_result.get('restart_required'):
                    self.say('live_restart_all' if action=='all' else 'live_restart')
                    if skin_result.get('live_error'):
                        self.show_error(skin_result['live_error'])
                elif skin_result.get('offline'):self.say('disk_done')
                elif action=='all':self.say('all_queued')
                elif action=='apply':self.say('live_done')
                else:self.say('graphics_done')
        except queue.Empty:pass
        if not self.busy and not self.data.get('disk_pending'):
            self.close_baseline=self.close_state()
        if not self.busy and self.data.get('disk_pending') and self.game['state']=='missing' and time.monotonic()-self.state_seen<2.5 and not self.auto_sync_blocked and not self.load_error:
            self.configure_skins(json.loads(json.dumps(self.data)))
        self.monitor();self.root.after(100,self.poll)

    def close_state(self):
        # Settings loaded at launch are already saved. Keep any deferred disk job,
        # but only prompt for a new pending selection in this app session.
        return (bool(self.data.get('disk_pending')),self.data.get('game_folder',''),
                tuple((i['id'],i['path']) for i in self.data['skins'] if i['enabled']))

    def close(self):
        if self.busy:self.say('wait_close');return
        if self.data.get('disk_pending') and self.close_state()!=self.close_baseline:
            if not messagebox.askyesno(self.tr('title'),self.tr('pending_close'),parent=self.root):return
        try:self.persist()
        except (ValueError,OSError):pass
        self.tree.hide_tip()
        if self.drop:self.drop.close()
        self.root.destroy()
