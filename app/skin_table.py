"""Compact tree with actual drawn switches in the final column."""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk


class SkinTable(ttk.Treeview):
    def __init__(self,parent,on_switch,**kwargs):
        super().__init__(parent,**kwargs)
        self.on_switch=on_switch;self.switches={};self.states={};self.pending=None;self.locked=False;self.blocked=set()
        self.images={};self.names={};self.tip=None;self.tip_timer=None;self.tip_row=None
        self.factor=1
        self.bind('<Configure>',lambda e:self.redraw_later(),add='+')
        self.bind('<<TreeviewSelect>>',lambda e:self.redraw_later(),add='+')
        self.bind('<Motion>',self.hover,add='+')
        self.bind('<Leave>',lambda e:self.hide_tip(),add='+')
        self.bind('<ButtonPress-1>',lambda e:self.hide_tip(),add='+')

    def set_switches(self,states,locked=False,blocked=()):
        blocked=set(blocked)
        if states==self.states and locked==self.locked and blocked==self.blocked:return
        self.states=states;self.locked=locked;self.blocked=blocked;self.redraw_later()

    def set_scale(self,factor):
        if abs(factor-self.factor)<.01:return
        self.factor=factor;self.images.clear();self.redraw_later()

    def px(self,value):return round(value*self.factor)

    def redraw_later(self):
        self.hide_tip()
        if self.pending is None:self.pending=self.after_idle(self.redraw)

    def switch_image(self,active,disabled=False):
        disabled=disabled or self.locked
        key=(active,disabled)
        if key not in self.images:
            scale=4
            image=Image.new('RGBA',(36*scale,20*scale))
            draw=ImageDraw.Draw(image)
            color=('#a8b7d5' if active else '#e4e8ef') if disabled else ('#356ae6' if active else '#cbd2dc')
            draw.rounded_rectangle((scale,scale,35*scale,19*scale),radius=9*scale,fill=color)
            left=19 if active else 3
            draw.ellipse((left*scale,3*scale,(left+14)*scale,17*scale),fill='white')
            image=image.resize((self.px(36),self.px(20)),Image.Resampling.LANCZOS)
            self.images[key]=ImageTk.PhotoImage(image,master=self)
        return self.images[key]

    def hover(self,event):
        row=self.identify_row(event.y) if self.identify_column(event.x)=='#2' else None
        if not row or row not in self.names:self.hide_tip();return
        if row==self.tip_row:return
        self.hide_tip();self.tip_row=row
        x,y=event.x_root,event.y_root
        self.tip_timer=self.after(450,lambda:self.show_tip(row,x,y))

    def show_tip(self,row,x,y):
        self.tip_timer=None
        if row!=self.tip_row or row not in self.names:return
        self.tip=tk.Toplevel(self);self.tip.overrideredirect(True)
        self.tip.attributes('-topmost',True)
        tk.Label(self.tip,text=self.names[row],font=(getattr(self,'display_font','Segoe UI'),-self.px(12)),bg='#233044',fg='white',
                 padx=self.px(10),pady=self.px(7),wraplength=self.px(550),justify='left').pack()
        self.tip.update_idletasks()
        x=max(0,min(x+12,self.winfo_screenwidth()-self.tip.winfo_reqwidth()-8))
        y=max(0,min(y+18,self.winfo_screenheight()-self.tip.winfo_reqheight()-8))
        self.tip.geometry(f'+{x}+{y}')

    def hide_tip(self):
        if self.tip_timer is not None:self.after_cancel(self.tip_timer);self.tip_timer=None
        if self.tip is not None:self.tip.destroy();self.tip=None
        self.tip_row=None

    def redraw(self):
        self.pending=None
        selected=set(self.selection());visible=set()
        for key,active in self.states.items():
            if not self.exists(key):continue
            box=self.bbox(key,'enabled')
            if not box:continue
            x,y,w,h=box
            if y<self.px(20) or y+h>self.winfo_height():continue
            visible.add(key)
            switch=self.switches.get(key)
            if switch is None:
                switch=tk.Canvas(self,width=36,height=20,highlightthickness=0,bd=0,takefocus=False)
                switch.bind('<Button-1>',lambda event,k=key:self.activate(k,event))
                switch.bind('<MouseWheel>',lambda event:self.event_generate('<MouseWheel>',delta=event.delta))
                self.switches[key]=switch
            disabled=self.locked or (key in self.blocked and not active)
            switch.configure(bg='#e9efff' if key in selected else '#ffffff',cursor='arrow' if disabled else 'hand2')
            switch.delete('all')
            switch.create_image(0,0,anchor='nw',image=self.switch_image(active,disabled))
            width,height=self.px(36),self.px(20)
            switch.place(x=x+(w-width)//2,y=y+(h-height)//2,width=width,height=height)
        for key in list(self.switches):
            if key not in self.states:self.switches.pop(key).destroy()
            elif key not in visible:self.switches[key].place_forget()

    def activate(self,key,event):
        if not self.locked:self.on_switch(key,event)
        return 'break'
