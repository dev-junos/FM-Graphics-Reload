/* Stage replacement layer trees before touching the live hierarchy. */
static void *full_visual,*full_vta,*full_vta_extensions;
typedef struct {void *description,*before,*after,*sections_before,*sections_after,*parent;int index;int committed;} UILayer;
static UILayer ui_layers[12];static unsigned ui_layer_count;
static ThemeGCHandle ui_pins[1024];static unsigned ui_pin_count;
static void ui_release_pins(void) {
    while(ui_pin_count)theme_gcfree(ui_pins[--ui_pin_count]);
}
static int ui_pin(void *o) {
    if(!o||ui_pin_count>=1024){error=85;return 0;}
    ThemeGCHandle h=theme_gcnew(o,0);if(!h){error=47;return 0;}ui_pins[ui_pin_count++]=h;return 1;
}

static void *ui_invoke(void *o,const char *name,int argc,void **args) {
    if(!o){error=85;return 0;}
    void *klass=(void*)q((uintptr_t)o),*method=full_method(klass,name,argc);
    if(!method) {char explicit_name[160];snprintf(explicit_name,sizeof(explicit_name),"UnityEngine.UIElements.IStyle.%s",name);method=full_method(klass,explicit_name,argc);}
    if(!method) {
        wchar_t path[1100];swprintf(path,1100,L"%ls\\ui_method_error.txt",ipc->path);FILE *f=_wfopen(path,L"a");
        if(f){fprintf(f,"%s.%s :: %s / %d\n",full_namespace(klass),theme_class_name(klass),name,argc);fclose(f);}
    }
    return call(method,o,args);
}
static unsigned ui_count(void *o) {
    void *n=ui_invoke(o,"get_childCount",0,0);return n?u((uintptr_t)n+16):0;
}
static void *ui_child(void *o,int index) {
    void *args[]={&index};return ui_invoke(o,"ElementAt",1,args);
}
static void *ui_query(void *o,const wchar_t *name,unsigned depth) {
    if(!o||depth>80||error)return 0;
    void *n=ui_invoke(o,"get_name",0,0);if(theme_string_equals(n,name))return o;
    unsigned count=ui_count(o);if(count>5000){error=85;return 0;}
    for(unsigned i=0;i<count&&!error;i++){void *found=ui_query(ui_child(o,(int)i),name,depth+1);if(found)return found;}
    return 0;
}
static void *ui_method_at(void *k,uintptr_t rva) {
    void *(*methods)(void*,void**)= (void*)GetProcAddress(GetModuleHandleW(L"GameAssembly.dll"),"il2cpp_class_get_methods");
    if(!methods){error=85;return 0;}
    for(;k;k=class_parent(k)) {void *it=0,*m;while((m=methods(k,&it)))if(q((uintptr_t)m)==(uintptr_t)GetModuleHandleW(L"GameAssembly.dll")+rva)return m;}
    error=85;return 0;
}
static void ui_set_ref(void *o,const char *name,void *value) {
    void *f=full_field((void*)q((uintptr_t)o),name);if(!f){error=85;return;}full_field_set(o,f,value);
}
typedef struct {void *panel,*before,*after,*old_binding,*new_binding,*parent;uint64_t key;int index,committed;} UIPanel;
static UIPanel ui_panels[128];static unsigned ui_panel_count;
static void ui_copy_sheets(void *from,void *to) {
    void *a=ui_invoke(from,"get_styleSheets",0,0),*b=ui_invoke(to,"get_styleSheets",0,0);
    if(!a||!b){error=85;return;}
    void *ak=(void*)q((uintptr_t)a),*bk=(void*)q((uintptr_t)b);
    void *n=call(full_method(ak,"get_count",0),(char*)a+16,0);unsigned count=n?u((uintptr_t)n+16):0;
    if(count>512){error=85;return;}
    for(int i=0;i<(int)count&&!error;i++){void *args[]={&i};void *sheet=call(full_method(ak,"get_Item",1),(char*)a+16,args);void *add[]={sheet};call(full_method(bk,"Add",1),(char*)b+16,add);}
}
static void *ui_binding(void *o,unsigned depth) {
    if(!o||depth>80||error)return 0;
    for(void *k=(void*)q((uintptr_t)o);k;k=class_parent(k))
        if(!strcmp(full_namespace(k),"SI.Bindable")&&!strcmp(theme_class_name(k),"BindingRoot"))return o;
    unsigned count=ui_count(o);if(count>5000){error=85;return 0;}
    for(unsigned i=0;i<count&&!error;i++){void *found=ui_binding(ui_child(o,(int)i),depth+1);if(found)return found;}
    return 0;
}
static int ui_tree_valid(void *node,unsigned depth) {
    if(!node||depth>80||error){error=85;return 0;}
    for(void *k=(void*)q((uintptr_t)node);k;k=class_parent(k)) {
        if(strcmp(theme_class_name(k),"TextElement")||strcmp(full_namespace(k),"UnityEngine.UIElements"))continue;
        void *text=ui_invoke(node,"get_text",0,0);
        if(text&&u((uintptr_t)text+16)>=17&&!wmemcmp((wchar_t*)((char*)text+20),L"Unknown Template:",17)){error=85;return 0;}
        break;
    }
    unsigned n=ui_count(node);if(n>5000){error=85;return 0;}
    for(unsigned i=0;i<n&&!error;i++)if(!ui_tree_valid(ui_child(node,(int)i),depth+1))return 0;
    return !error;
}
static void *ui_clone(void *asset) {
    void *m=full_vta_extensions?method_get(full_vta_extensions,"InstantiateSI",1):0;
    if(!m||q((uintptr_t)m)!=(uintptr_t)GetModuleHandleW(L"GameAssembly.dll")+0x1672cd0){error=85;return 0;}
    void *args[]={asset};void *tree=call(m,0,args);
    return tree&&ui_pin(tree)&&ui_tree_valid(tree,0)?tree:0;
}
static unsigned ui_stage_panels(void *layers,int reverse) {
    ui_panel_count=0;
    for(unsigned i=0;i<12&&!error;i++) {
        void *list=(void*)q((uintptr_t)layers+32+i*32+16);
        void *items=full_ref(list,"_items");void *f=list?full_field((void*)q((uintptr_t)list),"_size"):0;
        unsigned count=f?u((uintptr_t)list+field_offset(f)):0;if(count>128)return 85;
        for(unsigned j=0;j<count&&!error;j++) {
            void *panel=(void*)q((uintptr_t)items+32+j*8),*binding=full_ref(panel,"m_bindingRoot");
            if(!binding)continue;
            void *asset=0;
            for(void *node=binding;node&&!asset;node=ui_invoke(node,"get_parent",0,0)) {
                asset=ui_invoke(node,"get_visualTreeAssetSource",0,0);if(node==panel)break;
            }
            if(!asset)continue;
            void *target=full_map(asset,reverse);if(target==asset)continue;
            if((void*)q((uintptr_t)target)!=full_vta||ui_panel_count>=128)return 85;
            void *before=binding,*parent=ui_invoke(before,"get_parent",0,0);
            for(unsigned depth=0;parent&&parent!=panel&&depth<80;depth++){before=parent;parent=ui_invoke(before,"get_parent",0,0);}
            if(parent!=panel)return 85;
            void *after=ui_clone(target);
            if(!after||!ui_pin(before)||!ui_pin(after))return error?error:85;
            void *new_binding=ui_binding(after,0);if(!new_binding)return 85;
            if(before==binding){ui_copy_sheets(after,new_binding);after=new_binding;}
            void *key=ui_invoke(binding,"get_Key",0,0),*args[]={before};
            void *index=ui_invoke(panel,"IndexOf",1,args);if(!key||!index)return 85;
            ui_panels[ui_panel_count++]=(UIPanel){panel,before,after,binding,new_binding,panel,q((uintptr_t)key+16),(int)u((uintptr_t)index+16),0};
        }
    }
    return error;
}
static unsigned ui_commit_panel(UIPanel *p,int rollback) {
    void *before=rollback?p->after:p->before,*after=rollback?p->before:p->after;
    void *from=rollback?p->new_binding:p->old_binding,*to=rollback?p->old_binding:p->new_binding;
    unsigned char remove_key=0;void *unbind_args[]={&remove_key};ui_invoke(from,"Unbind",1,unbind_args);
    if(error)return error;
    ui_invoke(before,"RemoveFromHierarchy",0,0);
    void *args[]={&p->index,after};ui_invoke(p->parent,"Insert",2,args);
    ui_set_ref(p->panel,"m_bindingRoot",to);
    void *bind_args[]={&p->key};ui_invoke(to,"Bind",1,bind_args);
    return error;
}
static unsigned ui_style_hashes(int reverse) {
    unsigned changed=0;
    for(unsigned i=0;i<full_pair_count&&!error;i++) {
        void *o=reverse?full_pairs[i].old:full_pairs[i].next,*k=(void*)q((uintptr_t)o);
        if(k==full_vta) {
            int h=++theme_serial;void *args[]={&h};call(method_get(full_vta,"set_contentHash",1),o,args);
            o=full_ref(o,"inlineSheet");k=o?(void*)q((uintptr_t)o):0;
        }
        if(k==theme_style) {
            int h=++theme_serial;void *args[]={&h};call(method_get(theme_style,"set_contentHash",1),o,args);changed++;
        }
    }
    return changed;
}
static unsigned ui_renderer_reset(void) {
    void *manager=unique(panel_class),*doc=full_ref(manager,"m_mainUIDocument");
    void *root=ui_invoke(doc,"get_rootVisualElement",0,0),*panel=ui_invoke(root,"get_panel",0,0);
    int phase=6;void *args[]={&phase};void *renderer=ui_invoke(panel,"GetUpdater",1,args);
    void *m=renderer?full_method((void*)q((uintptr_t)renderer),"Reset",0):0;
    if(!m||q((uintptr_t)m)!=(uintptr_t)GetModuleHandleW(L"GameAssembly.dll")+0x2071390)return 85;
    call(m,renderer,0);return error;
}
static unsigned ui_stage(int reverse) {
    ui_release_pins();ui_layer_count=0;ui_panel_count=0;
    void *manager=unique(panel_class),*layers=full_ref(manager,"<Layers>k__BackingField");
    unsigned count=layers?(unsigned)q((uintptr_t)layers+24):0;
    if(count!=12||!full_visual||!full_vta)return 85;
    const wchar_t *sections[]={L"Title",L"Header",L"Body",L"Footer",L"FullScreen"};
    for(unsigned i=0;i<count&&!error;i++) {
        void *description=(void*)q((uintptr_t)layers+32+i*32+8);
        void *before=full_ref(description,"layerRoot"),*prior_sections=full_ref(description,"sectionRoots");
        if(!before||!prior_sections||q((uintptr_t)prior_sections+24)!=5)return 85;
        void *asset=ui_invoke(before,"get_visualTreeAssetSource",0,0);
        if(!asset){void *reference=full_ref(description,"layerTemplate");if(reference)asset=ui_invoke(reference,"get_Asset",0,0);}
        if(!asset)continue;
        void *target=full_map(asset,reverse);if(target==asset)continue;
        if((void*)q((uintptr_t)target)!=full_vta)return 85;
        if(!ui_pin(before)||!ui_pin(prior_sections))return error;
        void *container=ui_clone(target);
        if(!container||!ui_pin(container))return error?error:85;
        void *after=ui_query(container,L"Root",0);if(!after)return 85;
        /* Match FM's layer callback: transfer the template container's styles to Root. */
        void *sheetset=ui_invoke(container,"get_styleSheets",0,0),*targetset=ui_invoke(after,"get_styleSheets",0,0);
        if(!sheetset||!targetset)return 85;
        void *sk=(void*)q((uintptr_t)sheetset),*tk=(void*)q((uintptr_t)targetset);
        void *boxed=call(full_method(sk,"get_count",0),(char*)sheetset+16,0);
        unsigned n=boxed?u((uintptr_t)boxed+16):0;if(n>512)return 85;
        for(unsigned j=0;j<n&&!error;j++){int index=(int)j;void *getargs[]={&index};void *sheet=call(full_method(sk,"get_Item",1),(char*)sheetset+16,getargs);void *addargs[]={sheet};call(full_method(tk,"Add",1),(char*)targetset+16,addargs);}
        void *name=ui_invoke(before,"get_name",0,0),*nameargs[]={name};ui_invoke(after,"set_name",1,nameargs);
        /* FM keeps unused overlay layers hidden; preserve that runtime visibility. */
        void *old_style=ui_invoke(before,"get_style",0,0),*new_style=ui_invoke(after,"get_style",0,0);
        void *display=ui_invoke(old_style,"get_display",0,0);if(!display)return error?error:85;
        void *display_args[]={(char*)display+16};ui_invoke(new_style,"set_display",1,display_args);
        void *new_sections=full_array_new(full_visual,5);if(!new_sections||!ui_pin(new_sections))return error?error:85;
        /* SetValue invokes the runtime write barrier for the managed array. */
        for(int j=0;j<5&&!error;j++) {
            void *section=ui_query(after,sections[j],0);if(!section)section=after;
            void *args[]={section,&j};call(ui_method_at((void*)q((uintptr_t)new_sections),0x13d1ab0),new_sections,args);
        }
        void *parent=ui_invoke(before,"get_parent",0,0);if(!parent)return 85;
        void *indexargs[]={before};void *index=ui_invoke(parent,"IndexOf",1,indexargs);if(!index)return 85;
        ui_layers[ui_layer_count++]=(UILayer){description,before,after,prior_sections,new_sections,parent,(int)u((uintptr_t)index+16),0};
    }
    return error?error:ui_stage_panels(layers,reverse);
}
static unsigned ui_commit_layer(UILayer *layer,int rollback) {
    void *before=rollback?layer->after:layer->before,*after=rollback?layer->before:layer->after;
    void *from=rollback?layer->sections_after:layer->sections_before,*to=rollback?layer->sections_before:layer->sections_after;
    /* Move open panels, leaving each template's own named section nodes intact. */
    for(int j=0;j<5&&!error;j++) {
        void *a=(void*)q((uintptr_t)from+32+j*8),*b=(void*)q((uintptr_t)to+32+j*8);
        int n=(int)ui_count(a);
        for(int k=n-1;k>=0&&!error;k--) {
            void *child=ui_child(a,k),*klass=child?(void*)q((uintptr_t)child):0;
            if(klass&&!strcmp(full_namespace(klass),"SI.Bindable")&&!strcmp(theme_class_name(klass),"Panel")) {
                int zero=0;void *args[]={&zero,child};ui_invoke(b,"Insert",2,args);
            }
        }
    }
    if(error)return error;
    ui_invoke(before,"RemoveFromHierarchy",0,0);
    void *args[]={&layer->index,after};ui_invoke(layer->parent,"Insert",2,args);
    ui_set_ref(layer->description,"layerRoot",after);ui_set_ref(layer->description,"sectionRoots",to);
    return error;
}
static unsigned ui_commit(void) {
    wchar_t path[1100];swprintf(path,1100,L"%ls\\ui_commit.txt",ipc->path);FILE *f=_wfopen(path,L"a");
    if(f){fprintf(f,"layers=%u panels=%u\n",ui_layer_count,ui_panel_count);fclose(f);}
    for(unsigned i=0;i<ui_layer_count&&!error;i++) {
        ui_layers[i].committed=1;ui_commit_layer(&ui_layers[i],0);
    }
    for(unsigned i=0;i<ui_panel_count&&!error;i++){ui_panels[i].committed=1;ui_commit_panel(&ui_panels[i],0);}
    if(!error){void *manager=unique(panel_class);ui_invoke(manager,"RecalculateScreenScaling",0,0);ui_invoke(manager,"UpdateLayersToNewBreakpoint",0,0);}
    return error;
}
static void ui_rollback(void) {
    for(unsigned i=ui_panel_count;i>0&&!error;i--)if(ui_panels[i-1].committed)ui_commit_panel(&ui_panels[i-1],1);
    for(unsigned i=ui_layer_count;i>0&&!error;i--)if(ui_layers[i-1].committed)ui_commit_layer(&ui_layers[i-1],1);
}
static unsigned ui_inspect(void) {
    void *manager=unique(panel_class),*layers=full_ref(manager,"<Layers>k__BackingField");
    HANDLE f=CreateFileW(ipc->path,GENERIC_WRITE,0,0,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,0);if(f==INVALID_HANDLE_VALUE)return 33;
    for(unsigned i=0;layers&&i<q((uintptr_t)layers+24)&&i<12&&!error;i++) {
        void *desc=(void*)q((uintptr_t)layers+32+i*32+8),*root=full_ref(desc,"layerRoot"),*ref=full_ref(desc,"layerTemplate");
        void *asset=root?ui_invoke(root,"get_visualTreeAssetSource",0,0):0;
        void *cached=ref?ui_invoke(ref,"get_Asset",0,0):0;
        char prefix[128];snprintf(prefix,sizeof(prefix),"{\"layer\":%u,\"name\":",i);full_put(f,prefix);
        full_string(f,root?ui_invoke(root,"get_name",0,0):0);
        full_put(f,",\"guid\":");full_string(f,full_ref(ref,"m_AssetGUID"));
        full_put(f,",\"asset\":");if(asset)full_describe(f,asset);else full_put(f,"null");
        full_put(f,",\"cached\":");if(cached)full_describe(f,cached);else full_put(f,"null");
        full_put(f,"}\n");
    }
    CloseHandle(f);ipc->completions=ui_layer_count;return error;
}
