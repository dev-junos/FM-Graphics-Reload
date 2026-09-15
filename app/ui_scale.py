"""Scale layout distances alongside Tk's point-sized fonts."""
import tkinter.font as tkfont


class LayoutScale:
    def __init__(self, root):
        self.root=root
        self.factor=float(root.winfo_fpixels('1i'))/96
        self.options=[];self.geometry_options=[]

    def px(self, value):
        if isinstance(value,(tuple,list)):
            return tuple(self.px(v) for v in value)
        return round(float(value)*self.factor)

    def capture(self, parent):
        """Record original 96-DPI spacing once; never rescale scaled values."""
        for widget in parent.winfo_children():
            options={}
            for key in ('padding','padx','pady','wraplength'):
                if key in widget.keys():
                    value=widget.cget(key)
                    parts=widget.tk.splitlist(value) if not isinstance(value,(int,float)) else (value,)
                    if parts:
                        try:options[key]=tuple(float(v) for v in parts)
                        except (TypeError,ValueError):pass
            if options:self.options.append((widget,options))
            manager=widget.winfo_manager()
            if manager in ('pack','grid'):
                info=getattr(widget,manager+'_info')();spacing={}
                for key in ('padx','pady','ipadx','ipady'):
                    value=info.get(key,0)
                    parts=widget.tk.splitlist(value) if not isinstance(value,(int,float)) else (value,)
                    spacing[key]=tuple(float(v) for v in parts)
                self.geometry_options.append((widget,manager,spacing))
            self.capture(widget)

    def apply(self, factor=None):
        if factor is not None:self.factor=factor
        for widget,options in self.options:
            scaled={k:self.px(v) for k,v in options.items()}
            # Only ttk padding accepts a tuple of four distances.
            scaled={k:v if k=='padding' else v[0] for k,v in scaled.items()}
            widget.configure(**scaled)
        for widget,manager,options in self.geometry_options:
            getattr(widget,manager+'_configure')(**{k:self.px(v) for k,v in options.items()})

    def columns(self, tree, font):
        measure=tkfont.Font(root=self.root,font=(font,-self.px(12)))
        for key,width in (('priority',38),('wins',64),('overlap',64),('enabled',54)):
            needed=max(self.px(width),measure.measure(tree.heading(key,'text'))+self.px(14))
            tree.column(key,width=needed,minwidth=needed,stretch=False)
        tree.column('name',minwidth=self.px(160),stretch=True)
