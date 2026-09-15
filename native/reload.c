/* Graphics-only bridge, FM26 26.3.2. Game calls execute on the UI tick.
   File hashes are checked by the launcher; RVAs are checked again here. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <wchar.h>
#include <stdio.h>
#include "MinHook.h"
#ifdef FM_THEME_LAB
#define FM_THEME_SUPPORT
#endif

typedef struct {
    uint64_t magic, version;
    volatile LONG state; /* 0 idle, 1 requested, 2 enumerating, 3 done, 4 failed */
    DWORD code;
    uint64_t deadline, heartbeat, completions, panels, operation;
    wchar_t path[1024];
    uint64_t status_tick, observed_world;
    volatile LONG activity; /* 0 unknown, 1 idle, 2 busy, 3 guarded */
    DWORD reserved;
    volatile uint64_t guard_token, lease_until, request_token;
} Shared;
_Static_assert(sizeof(Shared)==2160,"Shared wire size differs from the Python client");
_Static_assert(offsetof(Shared,status_tick)==2112,"Shared status offset mismatch");
_Static_assert(offsetof(Shared,request_token)==2152,"Shared guard offset mismatch");
static Shared *ipc;
static void (*original_tick)(void*,void*);
/* Win64 passes the 16-byte AsyncOperationHandle value by reference. */
static void (*original_complete)(void*,void*,void*);
static void *(*invoke)(void*,void*,void**,void**);
static void *(*method_get)(void*,const char*,int);
static void *(*class_parent)(void*), *(*class_type)(void*), *(*type_object)(void*);
static void *(*str_new)(const wchar_t*,int);
static void *(*field_get)(void*,const char*);
static size_t (*field_offset)(void*);
static void *resource_class,*panel_class,*continue_class,*find_method;
static void *register_method,*reload_method;
static size_t folder_offset;
static uintptr_t plugin;
static void *active_resource;
static wchar_t active_path[1024];
static volatile LONG completed;
static unsigned completion_status;
static uint64_t active_deadline, active_world;
static unsigned error;
static uint64_t guard_owner,guard_world;
static HWND guard_window;
static void (*original_continue)(void*,int,void*);
static void (*original_flow)(void*,void*,void*);
static void (*original_event_flow)(void*,void*,void*);
static unsigned char (*original_pause_countdown)(void*,void*);

static int guarded(void) {return guard_owner!=0;}
static void guard_continue(void *self,int timer,void *method) {
    if(!guarded())original_continue(self,timer,method);
}
static void guard_flow(void *self,void *action,void *method) {
    if(!guarded())original_flow(self,action,method);
}
static void guard_event_flow(void *self,void *event,void *method) {
    if(!guarded())original_event_flow(self,event,method);
}
static unsigned char guard_pause_countdown(void *self,void *method) {
    return guarded()?1:original_pause_countdown(self,method);
}
static BOOL CALLBACK find_game_window(HWND window,LPARAM unused) {
    (void)unused;DWORD pid=0;wchar_t klass[80];
    GetWindowThreadProcessId(window,&pid);
    if(pid==GetCurrentProcessId() && IsWindowVisible(window) && !GetWindow(window,GW_OWNER)
       && GetClassNameW(window,klass,80) && wcscmp(klass,L"UnityWndClass")==0) {
        guard_window=window;return FALSE;
    }
    return TRUE;
}
static void guard_release(void) {
    if(guard_window && IsWindow(guard_window))EnableWindow(guard_window,TRUE);
    guard_window=0;guard_owner=guard_world=0;
    if(ipc)ipc->guard_token=0;
}

static int read_at(uintptr_t p,void *out,size_t n) {
    SIZE_T got=0;
    if(p<65536 || !ReadProcessMemory(GetCurrentProcess(),(void*)p,out,n,&got) || got!=n) {
        ZeroMemory(out,n); return 0;
    } return 1;
}
static uint64_t q(uintptr_t p) {uint64_t x;read_at(p,&x,8);return x;}
static unsigned u(uintptr_t p) {unsigned x;read_at(p,&x,4);return x;}
static unsigned char byte(uintptr_t p) {unsigned char x;read_at(p,&x,1);return x;}
static void *call(void *m,void *self,void **args) {
    if(error)return 0;
    if(!m) {error=10;return 0;}
    void *exception=0,*result=invoke(m,self,args,&exception);
    if(exception) error=11;
    return result;
}
static void *objects(void *klass) {
    void *type=type_object(class_type(klass)),*args[]={type};
    return call(find_method,0,args);
}
static void *unique(void *klass) {
    void *a=objects(klass);
    if(!a || q((uintptr_t)a+24)!=1) {error=12;return 0;}
    return (void*)q((uintptr_t)a+32);
}
static uint64_t world(void) {return q(q(plugin+0x4e35f60)+0xb8);}
static int idle(void) {
    uintptr_t root=q(plugin+0x4e35f60);
    if(!root || !u(root+0xb8) || !u(root+0xbc) || byte(root+0xd8) || byte(root+0xd9))return 0;
    void *a=objects(continue_class);unsigned matches=0;
    uint64_t n=a?q((uintptr_t)a+24):0;
    if(error || n>128)return 0;
    for(uint64_t i=0;i<n;i++) {
        uintptr_t c=q((uintptr_t)a+32+i*8);
        if(byte(c+0x38) && byte(c+0x191)) {
            /* Only normal/needs-action/needs-manager states; exclude waiting, matches, holiday,
               run-to-date and all unfamiliar flags. Never infer idle from UI focus. */
            if((q(c+0x58)&~3ULL) || q(c+0x70) || byte(c+0x190) || byte(c+0x88))return 0;
            matches++;
        }
    }
    return matches==1;
}
#ifdef FM_THEME_SUPPORT
#include "theme_lab.h"
#endif
#ifdef FM_THEME_LAB
#include "full_skin_routes.h"
#endif
static void finish(unsigned code) {
    ipc->code=code;MemoryBarrier();InterlockedExchange(&ipc->state,code?4:3);
}
static void complete(void *self,void *handle,void *method) {
    int match=0; unsigned status=0;
    uintptr_t op=q((uintptr_t)handle);
    if(ipc && ipc->state==2 && self==active_resource && op) {
        uintptr_t s=q(op+folder_offset); unsigned n=u(s+16);
        wchar_t folder[1024];
        if(n<1024 && read_at(s+20,folder,n*2)) {
            folder[n]=0;
            match=wcscmp(folder,active_path)==0;
        }
        if(match) {
            void *klass=(void*)q(op),*getter=0;
            while(klass && !getter) {getter=method_get(klass,"get_Status",0);klass=class_parent(klass);}
            void *exception=0,*boxed=getter?invoke(getter,(void*)op,0,&exception):0;
            if(boxed && !exception)status=u((uintptr_t)boxed+16);
        }
    }
    original_complete(self,handle,method);
    /* Publish only after FM has finished updating its resource dictionary. */
    if(match) {completion_status=status;MemoryBarrier();InterlockedExchange(&completed,1);}
}
static void tick(void *self,void *method) {
    original_tick(self,method);
    if(!ipc)return;
    ipc->heartbeat=GetTickCount64();
    if(guard_owner && (world()!=guard_world ||
       (GetTickCount64()>ipc->lease_until && ipc->state!=2)))guard_release();
    if(GetTickCount64()-ipc->status_tick>=250) {
        unsigned saved_error=error;error=0;
        ipc->observed_world=world();
        ipc->activity=IsDebuggerPresent() || (ipc->state==4 && ipc->code==21)?0:
            (guard_owner?3:(idle()?1:2));
        error=saved_error;MemoryBarrier();ipc->status_tick=GetTickCount64();
    }
    if(InterlockedCompareExchange(&ipc->state,2,1)==1) {
        error=0;completed=0;completion_status=0;active_resource=0;
        active_deadline=ipc->deadline;
        if(IsDebuggerPresent() || active_deadline<GetTickCount64() || active_deadline-GetTickCount64()>300000) {finish(2);return;}
        if(ipc->operation==5) {
            if(!guard_owner || ipc->request_token!=guard_owner) {finish(25);return;}
            guard_release();finish(0);return;
        }
        if(!idle()) {finish(20);return;}
        active_world=world();
        if(ipc->operation==4) {
            if(guard_owner || !ipc->request_token || ipc->lease_until<GetTickCount64()
               || ipc->lease_until-GetTickCount64()>10000) {finish(25);return;}
            guard_window=0;EnumWindows(find_game_window,0);
            if(!guard_window || !IsWindowEnabled(guard_window)) {guard_window=0;finish(26);return;}
            guard_owner=ipc->request_token;guard_world=world();
            EnableWindow(guard_window,FALSE);
            ipc->guard_token=guard_owner;ipc->activity=3;finish(0);return;
        }
        if(ipc->operation!=1 && (!guard_owner || ipc->request_token!=guard_owner
           || guard_world!=world() || GetTickCount64()>ipc->lease_until)) {finish(25);return;}
#ifdef FM_THEME_LAB
        if(ipc->operation>=20) {unsigned result=full_start((unsigned)ipc->operation);if(result!=1000)finish(result);return;}
#endif
#ifdef FM_THEME_SUPPORT
        if(ipc->operation>=10) {finish(theme_run((unsigned)ipc->operation));return;}
#endif
        if(ipc->operation==1) {finish(0);return;} /* preflight: no graphics changes */
        if(ipc->operation!=2) {finish(3);return;}
        memcpy(active_path,ipc->path,sizeof(active_path));
        if(active_path[1023] || !active_path[0]) {finish(3);return;}
        DWORD attributes=GetFileAttributesW(active_path);
        if(active_path[1023] || !active_path[0] || attributes==INVALID_FILE_ATTRIBUTES || !(attributes&FILE_ATTRIBUTE_DIRECTORY)) {finish(3);return;}
        active_resource=unique(resource_class);
        if(error) {finish(error);return;}
        void *s=str_new(active_path,(int)wcslen(active_path)),*args[]={s,0};
        call(register_method,active_resource,args);
        if(error) {finish(error);return;}
    }
    if(ipc->state!=2)return;
#ifdef FM_THEME_LAB
    if(ipc->operation>=20) {unsigned result=full_poll();if(result!=1000)finish(result);return;}
#endif
    if(GetTickCount64()>active_deadline) {finish(21);return;}
    if(world()!=active_world) {finish(22);return;}
    if(InterlockedCompareExchange(&completed,0,1)==1) {
        ipc->completions++;
        if(completion_status!=1) {finish(23);return;}
        error=0;
        if(IsDebuggerPresent() || !idle()) {finish(24);return;}
        void *panel=unique(panel_class);
        call(reload_method,panel,0);
        if(!error)ipc->panels++;
        finish(error);
    }
}

#ifdef FM_THEME_LAB
#define StartGraphicsReload StartSkinThemeProbe
#endif
__declspec(dllexport) DWORD WINAPI StartGraphicsReload(void *unused) {
    (void)unused;if(ipc)return ipc->magic?0:8;
    uintptr_t assembly=(uintptr_t)GetModuleHandleW(L"GameAssembly.dll");
    plugin=(uintptr_t)GetModuleHandleW(L"game_plugin.dll");
    if(!assembly || !plugin || IsDebuggerPresent())return 1;
    typedef void *(*Domain)(void);typedef void *(*Attach)(void*);typedef void(*Detach)(void*);
    typedef const void **(*Assemblies)(void*,size_t*);typedef const void *(*Image)(const void*);
    typedef void *(*Class)(const void*,const char*,const char*);
#define API(type,n) type n=(type)GetProcAddress((HMODULE)assembly,"il2cpp_"#n);if(!n)return 2
#define LOAD(v,n) v=(void*)GetProcAddress((HMODULE)assembly,"il2cpp_"n);if(!v)return 2
    API(Domain,domain_get);API(Attach,thread_attach);API(Detach,thread_detach);
    API(Assemblies,domain_get_assemblies);API(Image,assembly_get_image);API(Class,class_from_name);
    LOAD(invoke,"runtime_invoke");LOAD(method_get,"class_get_method_from_name");
    LOAD(class_parent,"class_get_parent");LOAD(class_type,"class_get_type");LOAD(type_object,"type_get_object");
    LOAD(str_new,"string_new_utf16");LOAD(field_get,"class_get_field_from_name");LOAD(field_offset,"field_get_offset");
#ifdef FM_THEME_SUPPORT
    LOAD(theme_utf8,"string_new");LOAD(theme_gcnew,"gchandle_new");LOAD(theme_gctarget,"gchandle_get_target");
    LOAD(theme_gcfree,"gchandle_free");
    LOAD(theme_static_get,"field_static_get_value");LOAD(theme_class_name,"class_get_name");
#endif
#ifdef FM_THEME_LAB
    LOAD(full_namespace,"class_get_namespace");
    LOAD(full_field_set,"field_set_value_object");
    LOAD(full_array_new,"array_new");LOAD(full_element_class,"class_get_element_class");
    LOAD(full_value_type,"class_is_valuetype");LOAD(full_field_type,"field_get_type");
    LOAD(full_type_kind,"type_get_type");LOAD(full_type_class,"class_from_type");
    LOAD(full_object_new,"object_new");
#endif
    void *d=domain_get(),*thread=thread_attach(d),*resources=0,*tick_class=0,*enumerate_class=0;
    size_t n=0;const void **assemblies=domain_get_assemblies(d,&n);
#define CLASS(v,ns,name) if(!v)v=class_from_name(im,ns,name)
    for(size_t i=0;i<n;i++) {
        const void *im=assembly_get_image(assemblies[i]);
        CLASS(resources,"UnityEngine","Resources");CLASS(resource_class,"SI.Core","ResourcesSubsystem");
        CLASS(panel_class,"SI.Bindable","PanelManager");CLASS(tick_class,"SI.Core","TickSubsystem");
        CLASS(enumerate_class,"SI.Core","EnumerateLocalAssetsOp");
        CLASS(continue_class,"FM.UI","ContinueManagerModule");
#ifdef FM_THEME_SUPPORT
        CLASS(theme_style,"UnityEngine.UIElements","StyleSheet");CLASS(theme_json,"UnityEngine","JsonUtility");
        CLASS(theme_object,"UnityEngine","Object");CLASS(theme_manager,"SI.UI","StylesheetManager");
        CLASS(theme_cache,"UnityEngine.UIElements.StyleSheets","StyleSheetCache");
        CLASS(theme_scriptable,"UnityEngine","ScriptableObject");
#endif
#ifdef FM_THEME_LAB
        CLASS(full_visual,"UnityEngine.UIElements","VisualElement");CLASS(full_vta,"UnityEngine.UIElements","VisualTreeAsset");
        CLASS(full_render_chain,"UnityEngine.UIElements.UIR","RenderChain");
        CLASS(full_vta_extensions,"SI.Core","VisualTreeAssetExtensions");
        CLASS(full_bundle,"UnityEngine","AssetBundle");CLASS(full_async,"UnityEngine","AsyncOperation");
        CLASS(full_bundle_request,"UnityEngine","AssetBundleCreateRequest");CLASS(full_asset_request,"UnityEngine","AssetBundleRequest");
        CLASS(full_addressables,"UnityEngine.AddressableAssets","Addressables");
        CLASS(full_operation_interface,"UnityEngine.ResourceManagement.AsyncOperations","IAsyncOperation");
        CLASS(full_bundle_resource,"UnityEngine.ResourceManagement.ResourceProviders","AssetBundleResource");
#endif
    }
    if(!resources||!resource_class||!panel_class||!tick_class||!enumerate_class||!continue_class) {thread_detach(thread);return 3;}
    find_method=method_get(resources,"FindObjectsOfTypeAll",1);
    register_method=method_get(resource_class,"RegisterLocalPath",2);
    reload_method=method_get(panel_class,"ReloadPanels",0);
    void *tm=method_get(tick_class,"Update",0),*cm=method_get(resource_class,"EnumerateLocalAssetsComplete",1);
    void *continue_method=method_get(continue_class,"ContinueGame",1);
    void *pause_method=method_get(continue_class,"ShouldPauseCountdown",0);
    typedef void *(*Methods)(void*,void**);
    API(Methods,class_get_methods);
    void *iterator=0,*candidate=0,*flow_method=0,*event_method=0;
    while((candidate=class_get_methods(continue_class,&iterator))) {
        if(q((uintptr_t)candidate)==assembly+0x74fe00)flow_method=candidate;
        if(q((uintptr_t)candidate)==assembly+0x74ff10)event_method=candidate;
    }
    void *field=field_get(enumerate_class,"m_baseFolder");folder_offset=field?field_offset(field):0;
    thread_detach(thread);
    if(!find_method||!register_method||!reload_method||!tm||!cm||!folder_offset)return 4;
    if(q((uintptr_t)register_method)!=assembly+0x1667370 || q((uintptr_t)reload_method)!=assembly+0x16028a0 || q((uintptr_t)cm)!=assembly+0x16654d0 || folder_offset!=0x98)return 5;
    if(!continue_method || !pause_method || !flow_method || !event_method
       || q((uintptr_t)continue_method)!=assembly+0x74b690 || q((uintptr_t)pause_method)!=assembly+0x750900)return 5;
    wchar_t name[100];
#ifdef FM_THEME_LAB
    swprintf(name,100,L"Local\\FMSkinThemeProbe10_%lu",GetCurrentProcessId());
#else
    swprintf(name,100,L"Local\\FMGraphicsReload2_%lu",GetCurrentProcessId());
#endif
    HANDLE mapping=CreateFileMappingW(INVALID_HANDLE_VALUE,0,PAGE_READWRITE,0,sizeof(Shared),name);
    if(!mapping)return 6;
    ipc=MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Shared));
    if(!ipc) {CloseHandle(mapping);return 6;}
    ZeroMemory(ipc,sizeof(Shared));
    void *tt=(void*)q((uintptr_t)tm),*ct=(void*)q((uintptr_t)cm);
    if(MH_Initialize()!=MH_OK)return 7;
    if(MH_CreateHook(ct,complete,(void**)&original_complete)!=MH_OK || MH_CreateHook(tt,tick,(void**)&original_tick)!=MH_OK)return 7;
    void *cg=(void*)q((uintptr_t)continue_method),*pc=(void*)q((uintptr_t)pause_method);
    void *cf=(void*)q((uintptr_t)flow_method),*ef=(void*)q((uintptr_t)event_method);
    if(MH_CreateHook(cg,guard_continue,(void**)&original_continue)!=MH_OK
       || MH_CreateHook(pc,guard_pause_countdown,(void**)&original_pause_countdown)!=MH_OK
       || MH_CreateHook(cf,guard_flow,(void**)&original_flow)!=MH_OK
       || MH_CreateHook(ef,guard_event_flow,(void**)&original_event_flow)!=MH_OK)return 7;
    void *targets[]={ct,tt,cg,pc,cf,ef};unsigned enabled=0;
    for(;enabled<6;enabled++)if(MH_EnableHook(targets[enabled])!=MH_OK) {
        while(enabled)MH_DisableHook(targets[--enabled]);return 7;
    }
    ipc->version=1;MemoryBarrier();ipc->magic=0x464d475241504831ULL;
    return 0;
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,void *p) {
    (void)p;if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;
}

