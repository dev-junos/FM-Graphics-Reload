/* Full pack research: independently loaded copies; no bundle is unloaded here. */
static void *full_bundle,*full_async,*full_bundle_request,*full_asset_request;
static const char *(*full_namespace)(void*);
static void (*full_field_set)(void*,void*,void*);
static ThemeGCHandle full_roots[32],full_pending;
static unsigned full_root_count,full_pending_kind;
static void *full_bundles[128];
static unsigned full_bundle_count;
typedef struct {int id;void *object;} FullObject;
static FullObject *full_objects;static uint64_t full_object_count;
static void full_put(HANDLE f,const char *s) {DWORD n;WriteFile(f,s,(DWORD)strlen(s),&n,0);}
static void full_string(HANDLE f,const wchar_t *s,unsigned n) {
    full_put(f,"\"");
    for(unsigned i=0;i<n;i++) {
        wchar_t ch=s[i];char out[16];
        if(ch=='"'||ch=='\\') {out[0]='\\';out[1]=(char)ch;out[2]=0;}
        else if(ch<32)snprintf(out,sizeof(out),"\\u%04x",(unsigned)ch);
        else {int count=WideCharToMultiByte(CP_UTF8,0,&ch,1,out,8,0,0);out[count]=0;}
        full_put(f,out);
    }
    full_put(f,"\"");
}
static int full_id(void *obj) {
    void *boxed=call(method_get(theme_object,"GetInstanceID",0),obj,0);
    return boxed?(int)u((uintptr_t)boxed+16):0;
}
static void *full_find(int id) {
    for(uint64_t i=0;i<full_object_count;i++)if(full_objects[i].id==id)return full_objects[i].object;
    error=61;return 0;
}
static unsigned full_inventory(void) {
    if(full_root_count>=32)return 62;
    void *arr=objects(theme_object);if(error)return error;
    uint64_t n=q((uintptr_t)arr+24);if(n>500000)return 63;
    full_roots[full_root_count++]=theme_gcnew(arr,0);
    if(full_objects)HeapFree(GetProcessHeap(),0,full_objects);
    full_objects=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,(size_t)n*sizeof(FullObject));
    if(!full_objects)return 32;full_object_count=0;
    HANDLE f=CreateFileW(ipc->path,GENERIC_WRITE,0,0,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,0);
    if(f==INVALID_HANDLE_VALUE)return 33;
    for(uint64_t i=0;i<n;i++) {
        void *obj=(void*)q((uintptr_t)arr+32+i*8),*klass=(void*)q((uintptr_t)obj);
        const char *name=theme_class_name(klass),*ns=full_namespace(klass);
        /* Inventory objects; serialize only selected assets in a separate command. */
        void *s=call(method_get(theme_object,"get_name",0),obj,0);int id=full_id(obj);
        if(error)break;
        full_objects[full_object_count++]=(FullObject){id,obj};
        char line[1024];snprintf(line,sizeof(line),"{\"id\":%d,\"class\":\"%s.%s\",\"name\":",id,ns,name);
        full_put(f,line);full_string(f,s?(wchar_t*)((char*)s+20):L"",s?u((uintptr_t)s+16):0);full_put(f,"}\n");
    }
    CloseHandle(f);ipc->completions=n;return error;
}
static unsigned full_dump(void) {
    wchar_t ids_path[1100];swprintf(ids_path,1100,L"%ls\\ids.txt",ipc->path);
    FILE *ids=_wfopen(ids_path,L"r");if(!ids)return 34;
    int id;unsigned count=0;
    while(fscanf(ids,"%d",&id)==1) {
        void *obj=full_find(id);if(error)break;
        void *args[]={obj},*json=call(method_get(theme_json,"ToJson",1),0,args);
        if(error)break;
        wchar_t dest[1100];swprintf(dest,1100,L"%ls\\%d.json",ipc->path,id);
        error=theme_write(json,dest);if(error)break;count++;
    }
    fclose(ids);ipc->completions=count;return error;
}
static int full_scriptable(void *obj) {
    void *klass=(void*)q((uintptr_t)obj);
    for(;klass;klass=class_parent(klass))if(klass==theme_scriptable)return 1;
    return 0;
}
static unsigned full_clone_tests(void) {
    /* Quarantined: FontAsset.OnDestroy owns shared atlas/material references.
       JSON equality alone does not establish an isolated clone's safety. */
    return 76;
    wchar_t path[1100];swprintf(path,1100,L"%ls\\pairs.txt",ipc->path);
    FILE *pairs=_wfopen(path,L"r");if(!pairs)return 34;
    int oldid,newid;unsigned count=0,result=0;
    while(fscanf(pairs,"%d %d",&oldid,&newid)==2) {
        void *old=full_find(oldid),*src=full_find(newid),*clone=0;
        ThemeGCHandle ah=0,bh=0,ch=0;
        if(error) {result=error;break;}
        if(!full_scriptable(old)||q((uintptr_t)old)!=q((uintptr_t)src)) {result=69;break;}
        void *tojson=method_get(theme_json,"ToJson",1),*overwrite=method_get(theme_json,"FromJsonInternal",3);
        void *args[]={old};void *a=call(tojson,0,args);if(error||!a) {result=70;break;}
        ah=theme_gcnew(a,0);args[0]=src;void *b=call(tojson,0,args);
        if(error||!b) {result=71;goto end_one;}
        bh=theme_gcnew(b,0);
        void *type=type_object(class_type((void*)q((uintptr_t)old))),*ca[]={type};
        clone=call(method_get(theme_scriptable,"CreateInstance",1),0,ca);
        if(error||!clone) {result=72;goto end_one;}
        ch=theme_gcnew(clone,0);
        theme_overwrite(overwrite,theme_gctarget(ah),clone);
        args[0]=clone;void *json=call(tojson,0,args);
        if(error||!theme_json_equal(json,theme_gctarget(ah))) {result=73;goto evidence;}
        theme_overwrite(overwrite,theme_gctarget(bh),clone);json=call(tojson,0,args);
        if(error||!theme_json_equal(json,theme_gctarget(bh))) {result=74;goto evidence;}
        theme_overwrite(overwrite,theme_gctarget(ah),clone);json=call(tojson,0,args);
        if(error||!theme_json_equal(json,theme_gctarget(ah))) {result=75;goto evidence;}
        count++;goto end_one;
evidence:
        if(json) {swprintf(path,1100,L"%ls\\failed_%d_%u.json",ipc->path,oldid,result);theme_write(json,path);}
end_one:
        error=0;
        if(clone) {void *da[]={clone};call(method_get(theme_object,"Destroy",1),0,da);}
        if(ah)theme_gcfree(ah);if(bh)theme_gcfree(bh);if(ch)theme_gcfree(ch);
        if(result||error) {if(!result)result=error;ipc->code=(unsigned)oldid;break;}
    }
    fclose(pairs);ipc->completions=count;return result;
}
static void *full_field(void *obj,const char *name) {
    for(void *klass=(void*)q((uintptr_t)obj);klass;klass=class_parent(klass)) {
        void *f=field_get(klass,name);if(f)return f;
    }
    error=10;return 0;
}
static void *full_ref(void *obj,const char *name) {
    void *f=full_field(obj,name);return f?(void*)q((uintptr_t)obj+field_offset(f)):0;
}
static unsigned full_repair_font(void) {
    /* Narrow recovery for the font atlas/material lost by the isolated clone cleanup. */
    FILE *f=_wfopen(ipc->path,L"r");int targetid=0,sourceid=0;
    if(!f)return 34;int n=fscanf(f,"%d %d",&targetid,&sourceid);fclose(f);if(n!=2)return 3;
    void *dst=full_find(targetid),*src=full_find(sourceid);if(error)return error;
    if(q((uintptr_t)dst)!=q((uintptr_t)src)||strcmp(theme_class_name((void*)q((uintptr_t)dst)),"FontAsset"))return 69;
    void *name=call(method_get(theme_object,"get_name",0),dst,0);
    if(error||!theme_string_equals(name,L"ABCSocial-Regular SDF"))return 69;
    void *mat=full_ref(dst,"m_Material"),*atlases=full_ref(dst,"m_AtlasTextures");
    void *tex=atlases&&q((uintptr_t)atlases+24)?(void*)q((uintptr_t)atlases+32):0;
    if(mat&&q((uintptr_t)mat+16)&&tex&&q((uintptr_t)tex+16))return 77;
    void *replacement_mat=full_ref(src,"m_Material"),*replacement_atlases=full_ref(src,"m_AtlasTextures");
    void *replacement_tex=replacement_atlases&&q((uintptr_t)replacement_atlases+24)?(void*)q((uintptr_t)replacement_atlases+32):0;
    void *original_font=full_ref(dst,"m_SourceFontFile");
    if(error||!replacement_mat||!q((uintptr_t)replacement_mat+16)||!replacement_tex||!q((uintptr_t)replacement_tex+16)||!original_font||!q((uintptr_t)original_font+16))return 78;
    void *clear=method_get((void*)q((uintptr_t)dst),"ClearFontAssetData",1);
    void *mf=full_field(dst,"m_Material"),*af=full_field(dst,"m_AtlasTextures"),*tf=full_field(dst,"m_AtlasTexture");
    if(error||!clear||!mf||!af||!tf)return 10;
    full_field_set(dst,mf,&replacement_mat);full_field_set(dst,af,&replacement_atlases);full_field_set(dst,tf,&replacement_tex);
    unsigned char zero=0;void *args[]={&zero};call(clear,dst,args);
    if(error)return error;
    /* Font source, face metrics, and the game's common stylesheet are retained. */
    call(reload_method,unique(panel_class),0);if(!error)ipc->panels++;
    ipc->completions=1;return error;
}
static unsigned full_start(unsigned op) {
    if(op==20)return full_inventory();
    if(op==21)return full_dump();
    if(op==24)return full_clone_tests();
    if(op==27)return full_repair_font();
    if(op==22) {
        if(full_bundle_count>=128)return 64;
        void *s=str_new(ipc->path,(int)wcslen(ipc->path)),*args[]={s};
        void *req=call(method_get(full_bundle,"LoadFromFileAsync",1),0,args);
        if(error||!req)return error?error:65;
        full_pending=theme_gcnew(req,0);full_pending_kind=22;return 1000;
    }
    if(op==23) {
        unsigned index=(unsigned)ipc->completions;if(index>=full_bundle_count)return 66;
        void *req=call(method_get(full_bundle,"LoadAllAssetsAsync",0),full_bundles[index],0);
        if(error||!req)return error?error:65;
        full_pending=theme_gcnew(req,0);full_pending_kind=23;return 1000;
    }
    return 3;
}
static unsigned full_poll(void) {
    void *req=theme_gctarget(full_pending);
    void *done=call(method_get(full_async,"get_isDone",0),req,0);
    if(!error && (!done||!byte((uintptr_t)done+16)))return 1000;
    if(!error) {
        if(full_pending_kind==22) {
            void *bundle=call(method_get(full_bundle_request,"get_assetBundle",0),req,0);
            if(!bundle)error=67;
            else {full_bundles[full_bundle_count]=bundle;theme_gcnew(bundle,0);ipc->completions=full_bundle_count++;}
        } else {
            void *arr=call(method_get(full_asset_request,"get_allAssets",0),req,0);
            if(!arr)error=68;
            else {theme_gcnew(arr,0);ipc->completions=q((uintptr_t)arr+24);}
        }
    }
    theme_gcfree(full_pending);full_pending=0;return error;
}
