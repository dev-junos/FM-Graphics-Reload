/* Separate research build. Never enabled in the released graphics bridge. */
static void *theme_style,*theme_json,*theme_object,*theme_manager,*theme_cache;
static void *theme_scriptable;
static void *(*theme_utf8)(const char*);
/* This Unity 6 IL2CPP build uses pointer-sized handles, not historical uint32 handles. */
typedef uintptr_t ThemeGCHandle;
_Static_assert(sizeof(ThemeGCHandle)==sizeof(void*),"GC handle ABI mismatch");
static ThemeGCHandle (*theme_gcnew)(void*,int);
static void *(*theme_gctarget)(ThemeGCHandle);
static void (*theme_gcfree)(ThemeGCHandle);
static void (*theme_static_get)(void*,void*);
static const char *(*theme_class_name)(void*);
static ThemeGCHandle theme_backup,theme_target;
static uint64_t theme_world;
static int theme_serial=1700000000;
static int theme_handles_checked,theme_clone_checked;

static int theme_string_equals(void *s,const wchar_t *expected) {
    unsigned n=u((uintptr_t)s+16);
    if(n!=wcslen(expected))return 0;
    return !memcmp((char*)s+20,expected,n*2);
}
static int theme_write(void *s,const wchar_t *path) {
    if(!s)return 30;
    unsigned n=u((uintptr_t)s+16);
    if(n>16*1024*1024)return 31;
    int size=WideCharToMultiByte(CP_UTF8,0,(wchar_t*)((char*)s+20),(int)n,0,0,0,0);
    char *data=HeapAlloc(GetProcessHeap(),0,size);if(!data)return 32;
    WideCharToMultiByte(CP_UTF8,0,(wchar_t*)((char*)s+20),(int)n,data,size,0,0);
    HANDLE f=CreateFileW(path,GENERIC_WRITE,0,0,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,0);
    DWORD done=0;int ok=f!=INVALID_HANDLE_VALUE && WriteFile(f,data,size,&done,0) && done==(DWORD)size;
    if(f!=INVALID_HANDLE_VALUE)CloseHandle(f);
    HeapFree(GetProcessHeap(),0,data);return ok?0:33;
}
static void *theme_read(const wchar_t *path) {
    HANDLE f=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,0,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,0);
    if(f==INVALID_HANDLE_VALUE) {error=34;return 0;}
    DWORD size=GetFileSize(f,0),done=0;
    if(size<2 || size>16*1024*1024) {CloseHandle(f);error=35;return 0;}
    char *data=HeapAlloc(GetProcessHeap(),0,size+1);
    if(!data) {CloseHandle(f);error=32;return 0;}
    int ok=ReadFile(f,data,size,&done,0) && done==size;CloseHandle(f);data[size]=0;
    void *result=ok?theme_utf8(data):0;HeapFree(GetProcessHeap(),0,data);
    if(!result)error=36;return result;
}
static void *theme_find(void) {
    /* Only the active manager's sheets: research or other tools may load extra copies. */
    void *manager=unique(theme_manager),*found=0;
    if(error||!manager)return 0;
    void *field=field_get(theme_manager,"m_styleSheets");
    if(!field) {error=38;return 0;}
    uintptr_t list=q((uintptr_t)manager+field_offset(field));
    void *a=(void*)q(list+0x10);
    void *name_method=method_get(theme_object,"get_name",0);
    uint64_t n=list?u(list+0x18):0;unsigned count=0;
    if(n>512 || (n && (!a||n>q((uintptr_t)a+24)))) {error=37;return 0;}
    for(uint64_t i=0;i<n;i++) {
        void *o=(void*)q((uintptr_t)a+32+i*8),*name=call(name_method,o,0);
        if(name && theme_string_equals(name,L"AlwaysAppliedStyleSheet")) {found=o;count++;}
    }
    ipc->completions=count;
    if(count!=1)error=38;return found;
}
static unsigned theme_refresh(void *style) {
    call(method_get(theme_style,"OnEnable",0),style,0);
    /* Regenerated rule indices must not reuse cached property-id arrays. */
    void *field=field_get(theme_cache,"s_RulePropertyIdsCache"),*cache=0;
    if(!field)return 39;
    theme_static_get(field,&cache);
    if(cache)call(method_get((void*)q((uintptr_t)cache),"Clear",0),cache,0);
    int hash=++theme_serial;void *hash_args[]={&hash};
    call(method_get(theme_style,"set_contentHash",1),style,hash_args);
    void *manager=unique(theme_manager);
    if(!manager || error)return error;
    void *action=(void*)q((uintptr_t)manager+0x48),*sheets=(void*)q((uintptr_t)manager+0x40);
    if(action) {void *args[]={sheets};call(method_get((void*)q((uintptr_t)action),"Invoke",1),action,args);}
    call(reload_method,unique(panel_class),0);
    if(!error)ipc->panels++;
    return error;
}
static unsigned theme_check_handles(void) {
    for(int i=0;i<4;i++) {
        void *s=theme_utf8("FM theme pointer-sized handle check");
        ThemeGCHandle h=theme_gcnew(s,0);
        if(!h)return 47;
        void *target=theme_gctarget(h);
        int valid=target==s && theme_string_equals(target,L"FM theme pointer-sized handle check");
        theme_gcfree(h);
        if(!valid)return 48;
    }
    theme_handles_checked=1;ipc->completions=4;return 0;
}
static int theme_json_equal(void *a,void *b) {
    if(!a||!b)return 0;
    unsigned n=u((uintptr_t)a+16);
    return n==u((uintptr_t)b+16) && !memcmp((char*)a+20,(char*)b+20,n*2);
}
static void theme_overwrite(void *method,void *json,void *target) {
    /* Match JsonUtility.FromJsonOverwrite: the native binding requires the actual type. */
    void *klass=(void*)q((uintptr_t)target);
    void *type=klass?type_object(class_type(klass)):0;
    if(!type) {error=56;return;}
    void *args[]={json,target,type};call(method,0,args);
}
static unsigned theme_check_clone(void *style) {
    if(!theme_handles_checked)return 49;
    void *tojson=method_get(theme_json,"ToJson",1),*overwrite=method_get(theme_json,"FromJsonInternal",3);
    if(!tojson||!overwrite)return 55;
    void *args[]={style},*baseline=call(tojson,0,args);
    if(error||!baseline)return 50;
    ThemeGCHandle base_handle=theme_gcnew(baseline,0),patch_handle=0,clone_handle=0;
    unsigned result=0;void *clone=0;
    ipc->code=201;
    void *patch=theme_read(ipc->path);
    if(error) {result=error;goto done;}
    patch_handle=theme_gcnew(patch,0);
    void *type=type_object(class_type(theme_style)),*create_args[]={type};
    clone=call(method_get(theme_scriptable,"CreateInstance",1),0,create_args);
    if(error||!clone) {result=51;goto done;}
    clone_handle=theme_gcnew(clone,0);
    ipc->code=202;
    theme_overwrite(overwrite,theme_gctarget(base_handle),clone);
    if(error) {result=error;goto done;}
    call(method_get(theme_style,"OnEnable",0),clone,0);
    void *clone_args[]={clone};void *copy_json=call(tojson,0,clone_args);
    if(error||!theme_json_equal(copy_json,theme_gctarget(base_handle))) {result=52;goto done;}
    ipc->code=203;
    theme_overwrite(overwrite,theme_gctarget(patch_handle),clone);
    if(!error)call(method_get(theme_style,"OnEnable",0),clone,0);
    if(error) {result=error;goto done;}
    void *patched_json=call(tojson,0,clone_args);
    wchar_t evidence[1100];swprintf(evidence,1100,L"%ls.clone.json",ipc->path);
    if(!error)result=theme_write(patched_json,evidence);
    if(error||result) {if(error)result=error;goto done;}
    ipc->code=204;
    theme_overwrite(overwrite,theme_gctarget(base_handle),clone);
    if(!error)call(method_get(theme_style,"OnEnable",0),clone,0);
    void *restored=call(tojson,0,clone_args);
    if(error||!theme_json_equal(restored,theme_gctarget(base_handle))) {result=53;goto done;}
    void *live_args[]={style};void *live_json=call(tojson,0,live_args);
    if(error||!theme_json_equal(live_json,theme_gctarget(base_handle))) {result=54;goto done;}
    theme_clone_checked=1;ipc->completions=1;
done:
    error=0;
    if(clone) {void *destroy_args[]={clone};call(method_get(theme_object,"Destroy",1),0,destroy_args);}
    if(clone_handle)theme_gcfree(clone_handle);
    if(patch_handle)theme_gcfree(patch_handle);
    theme_gcfree(base_handle);
    return result?result:error;
}
static unsigned theme_run(unsigned op) {
    /* Live mutation is gated by actual pointer-handle and isolated clone tests. */
    if(op==14)return theme_check_handles();
    if(!theme_style||!theme_json||!theme_object||!theme_manager||!theme_cache)return 40;
    if(ipc->path[1023])return 3;
    void *style=theme_find();if(error)return error;
    if(op==15)return theme_check_clone(style);
    if(op==10) {
        void *args[]={style};void *json=call(method_get(theme_json,"ToJson",1),0,args);
        return error?error:theme_write(json,ipc->path);
    }
    if(op!=11 && op!=12)return 3;
    if(!theme_handles_checked||!theme_clone_checked)return 46;
    void *json=0;ThemeGCHandle input_handle=0;
    if(op==11) {
        ipc->code=101;
        json=theme_read(ipc->path);if(error)return error;
        input_handle=theme_gcnew(json,0);if(!input_handle)return 47;
        if(!theme_backup) {
            ipc->code=102;
            void *args[]={style};void *backup=call(method_get(theme_json,"ToJson",1),0,args);
            if(error||!backup) {theme_gcfree(input_handle);return 41;}
            theme_backup=theme_gcnew(backup,0);theme_target=theme_gcnew(style,0);theme_world=world();
        }
    } else {
        if(!theme_backup)return 42;
        json=theme_gctarget(theme_backup);
    }
    ipc->code=103;
    if(theme_world!=world() || theme_gctarget(theme_target)!=style) {
        if(input_handle)theme_gcfree(input_handle);return 43;
    }
    ipc->code=104;
    if(input_handle)json=theme_gctarget(input_handle);
    theme_overwrite(method_get(theme_json,"FromJsonInternal",3),json,style);
    if(input_handle)theme_gcfree(input_handle);
    if(!error) {ipc->code=105;theme_refresh(style);}
    if(error) {
        unsigned failure=error;error=0;
        theme_overwrite(method_get(theme_json,"FromJsonInternal",3),theme_gctarget(theme_backup),style);
        if(!error)theme_refresh(style);
        return error?45:failure;
    }
    return 0;
}
