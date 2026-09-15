/* Dynamic binding widgets can appear after clipping. Defer their first paint
   until Unity has computed clipping in the next render pass. */
static void *full_render_chain;
static void (*ui_render_original)(void*,void*);
static void (*ui_visual_original)(void*,void*,unsigned,unsigned char,void*,void*);
static void (*ui_render_clip)(void*,void*,unsigned char,void*);
static void (*ui_render_visual)(void*,void*,unsigned char,void*);
static unsigned char (*ui_render_displayed)(void*,void*);
static int ui_render_hooked,ui_render_enabled;
static uint64_t ui_render_deferred;
typedef struct {void *chain;int deferred;} UIRenderPass;
static _Thread_local UIRenderPass *ui_render_pass;
static void ui_visual_process(void *self,void *ve,unsigned dirty,unsigned char hierarchical,void *stats,void *method) {
    UIRenderPass *pass=ui_render_pass;
    if(pass&&pass->chain==(void*)q((uintptr_t)self+0x10)
       &&dirty!=u((uintptr_t)ve+0xc4)&&(u((uintptr_t)ve+0xb8)&1)
       &&!u((uintptr_t)ve+0xec)&&ui_render_displayed(ve,0)) {
        /* An Undetermined clip state cannot be drawn. Do not change allocator
           IDs or dirty registration inside Unity's locked render phase. */
        pass->deferred=1;return;
    }
    ui_visual_original(self,ve,dirty,hierarchical,stats,method);
}
static void ui_render_process(void *chain,void *method) {
    if(!ui_render_enabled){ui_render_original(chain,method);return;}
    UIRenderPass pass={chain,0},*previous=ui_render_pass;ui_render_pass=&pass;
    ui_render_original(chain,method);ui_render_pass=previous;
    if(pass.deferred&&!byte((uintptr_t)chain+0x80)) {
        void *panel=(void*)q((uintptr_t)chain+0x100);
        void *root=panel?(void*)q((uintptr_t)panel+0xe0):0;
        if(root&&(u((uintptr_t)root+0xb8)&1)) {
            /* Dirty tracking was reset by ProcessChanges. Queue both phases:
               next frame computes clipping before the deferred paint. */
            ui_render_clip(chain,root,1,0);ui_render_visual(chain,root,1,0);
            ui_render_deferred++;
        }
    }
}
static unsigned ui_render_install(void) {
    if(ui_render_hooked)return 0;
    uintptr_t base=(uintptr_t)GetModuleHandleW(L"GameAssembly.dll");
    void *m=full_render_chain?method_get(full_render_chain,"ProcessChanges",0):0;
    void *c=full_render_chain?method_get(full_render_chain,"UIEOnClippingChanged",2):0;
    void *v=full_render_chain?method_get(full_render_chain,"UIEOnVisualsChanged",2):0;
    void *d=full_visual?full_method(full_visual,"get_areAncestorsAndSelfDisplayed",0):0;
    void *(*nested)(void*,void**)= (void*)GetProcAddress((HMODULE)base,"il2cpp_class_get_nested_types");
    void *processor=0,*it=0,*k;
    if(nested&&full_render_chain)while((k=nested(full_render_chain,&it)))
        if(!strcmp(theme_class_name(k),"VisualChangesProcessor")){processor=k;break;}
    void *p=processor?method_get(processor,"DepthFirstOnVisualsChanged",4):0;
    if(!m||!c||!v||!d||!p||q((uintptr_t)m)!=base+0x1f95890
       ||q((uintptr_t)c)!=base+0x1f96c30||q((uintptr_t)v)!=base+0x1f96f70
       ||q((uintptr_t)d)!=base+0x1f37630||q((uintptr_t)p)!=base+0x1fa0480)return 85;
    ui_render_clip=(void*)q((uintptr_t)c);ui_render_visual=(void*)q((uintptr_t)v);
    ui_render_displayed=(void*)q((uintptr_t)d);
    void *target=(void*)q((uintptr_t)m),*visual=(void*)q((uintptr_t)p);
    if(MH_CreateHook(target,ui_render_process,(void**)&ui_render_original)!=MH_OK)return 7;
    if(MH_CreateHook(visual,ui_visual_process,(void**)&ui_visual_original)!=MH_OK){MH_RemoveHook(target);return 7;}
    if(MH_EnableHook(target)!=MH_OK){MH_RemoveHook(visual);MH_RemoveHook(target);return 7;}
    if(MH_EnableHook(visual)!=MH_OK){MH_DisableHook(target);MH_RemoveHook(visual);MH_RemoveHook(target);return 7;}
    ui_render_hooked=1;return 0;
}
