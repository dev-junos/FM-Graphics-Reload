/* Retained bundle routing. Never destroy or JSON-overwrite fonts/native assets. */
static void *full_bundle,*full_async,*full_bundle_request,*full_asset_request;
static void *full_addressables,*full_operation_interface,*full_bundle_resource;
static const char *(*full_namespace)(void*);
static void (*full_field_set)(void*,void*,void*);
static void *(*full_array_new)(void*,uintptr_t),*(*full_element_class)(void*);
static int (*full_value_type)(void*),(*full_type_kind)(void*);
static void *(*full_field_type)(void*),*(*full_type_class)(void*);
static void *(*full_object_new)(void*);
static int full_abi_checked;
typedef struct {int id;void *object;} FullObject;
#include "full_pair_index.h"
typedef struct {wchar_t name[160];void *next;} FullRoute;
static FullObject *full_objects;static uint64_t full_object_count;
static FullRoute full_routes[128];static unsigned full_route_count;
static ThemeGCHandle full_bundle_roots[256],full_asset_roots[256],full_inventory_root,full_pending;
static unsigned full_pending_kind,full_pending_index;
static uint64_t full_released_snapshots;
static void *full_bundles[256];static unsigned full_bundle_count;
static void *full_kept_operations[20000];static unsigned full_kept_count;
static int full_prepared,full_active,full_hooked;static uint64_t full_world,full_hits;
static void *(*full_original_bundle)(void*,void*);
typedef struct {void *target,*field,*old,*next;int index;} FullChange;
static FullChange full_changes[50000];static unsigned full_change_count;

static void *full_method(void *k,const char *name,int argc) {
    for(;k;k=class_parent(k)){void *m=method_get(k,name,argc);if(m)return m;}return 0;
}
static void *full_field(void *k,const char *name) {
    for(;k;k=class_parent(k)){void *f=field_get(k,name);if(f)return f;}return 0;
}
static void *full_ref(void *o,const char *name) {
    if(!o)return 0;void *f=full_field((void*)q((uintptr_t)o),name);
    return f?(void*)q((uintptr_t)o+field_offset(f)):0;
}
static int full_replace_root(ThemeGCHandle *slot,void *o) {
    if(!o){error=62;return 0;}
    ThemeGCHandle h=theme_gcnew(o,0);if(!h){error=47;return 0;}
    ThemeGCHandle previous=*slot;*slot=h;
    if(previous){theme_gcfree(previous);full_released_snapshots++;}return 1;
}
static int full_id(void *o) {
    void *b=call(method_get(theme_object,"GetInstanceID",0),o,0);
    return b?(int)u((uintptr_t)b+16):0;
}
static void *full_find(int id) {
    uint64_t lo=0,hi=full_object_count;
    while(lo<hi){uint64_t mid=lo+(hi-lo)/2;if(full_objects[mid].id<id)lo=mid+1;else hi=mid;}
    if(lo<full_object_count&&full_objects[lo].id==id)return full_objects[lo].object;
    error=61;return 0;
}
static int full_object_compare(const void *a,const void *b) {
    int x=((const FullObject*)a)->id,y=((const FullObject*)b)->id;return x<y?-1:x>y;
}
static void full_put(HANDLE f,const char *s) {
    DWORD n=0,len=(DWORD)strlen(s);if(!WriteFile(f,s,len,&n,0)||n!=len)error=33;
}
static void full_string(HANDLE f,void *s) {
    full_put(f,"\"");unsigned n=s?u((uintptr_t)s+16):0;
    if(n>65536){error=63;return;}
    for(unsigned i=0;i<n;i++) {
        wchar_t ch=0;read_at((uintptr_t)s+20+i*2,&ch,2);char out[16];
        if(ch=='"'||ch=='\\'){out[0]='\\';out[1]=(char)ch;out[2]=0;}
        else if(ch<32||ch>126)snprintf(out,sizeof(out),"\\u%04x",(unsigned)ch);
        else {out[0]=(char)ch;out[1]=0;}full_put(f,out);
    }full_put(f,"\"");
}
static void full_describe(HANDLE f,void *o) {
    void *k=(void*)q((uintptr_t)o),*s=call(method_get(theme_object,"get_name",0),o,0);
    int id=full_id(o);if(error)return;
    char line[1024];snprintf(line,sizeof(line),"{\"id\":%d,\"class\":\"%s.%s\",\"name\":",id,full_namespace(k),theme_class_name(k));
    full_put(f,line);full_string(f,s);full_put(f,"}\n");
}
static unsigned full_inventory(void) {
    /* Routes must be restored before replacing their only global snapshot root. */
    if(full_active||full_pending)return 77;
    void *arr=objects(theme_object);if(error||!arr)return error?error:63;
    uint64_t n=q((uintptr_t)arr+24);if(n>500000)return 63;
    ThemeGCHandle root=theme_gcnew(arr,0);if(!root)return 47;
    FullObject *next=HeapAlloc(GetProcessHeap(),HEAP_ZERO_MEMORY,(size_t)n*sizeof(FullObject));
    if(!next){theme_gcfree(root);return 32;}
    HANDLE f=CreateFileW(ipc->path,GENERIC_WRITE,0,0,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,0);
    if(f==INVALID_HANDLE_VALUE){HeapFree(GetProcessHeap(),0,next);theme_gcfree(root);return 33;}
    for(uint64_t i=0;i<n&&!error;i++) {
        void *o=(void*)q((uintptr_t)arr+32+i*8);next[i]=(FullObject){full_id(o),o};full_describe(f,o);
    }CloseHandle(f);
    if(error){HeapFree(GetProcessHeap(),0,next);theme_gcfree(root);return error;}
    qsort(next,(size_t)n,sizeof(*next),full_object_compare);
    full_prepared=0;full_route_count=0;full_discard_pairs();
    if(full_objects)HeapFree(GetProcessHeap(),0,full_objects);
    if(full_inventory_root){theme_gcfree(full_inventory_root);full_released_snapshots++;}
    full_inventory_root=root;
    full_objects=next;full_object_count=n;ipc->completions=n;return 0;
}
static unsigned full_dump(void) {
    wchar_t path[1100];swprintf(path,1100,L"%ls\\ids.txt",ipc->path);
    FILE *f=_wfopen(path,L"r");if(!f)return 34;int id;unsigned count=0;
    while(!error&&fscanf(f,"%d",&id)==1) {
        void *o=full_find(id),*args[]={o};void *s=call(method_get(theme_json,"ToJson",1),0,args);
        swprintf(path,1100,L"%ls\\%d.json",ipc->path,id);
        if(!error)error=theme_write(s,path);count++;
    }fclose(f);ipc->completions=count;return error;
}
static void *full_get_bundle(void *self,void *method) {
    void *bundle=full_original_bundle(self,method);
    /* Read only immutable strings; invoke with a separate exception slot. */
    if(!full_active||!bundle)return bundle;
    void *ex=0,*s=invoke(method_get(theme_object,"get_name",0),bundle,0,&ex);
    if(ex||!s)return bundle;
    for(unsigned i=0;i<full_route_count;i++)if(theme_string_equals(s,full_routes[i].name)) {
        full_hits++;return full_routes[i].next;
    }
    return bundle;
}
static unsigned full_prepare(void) {
    if(full_active)return 77;
    full_prepared=0;full_discard_pairs();
    wchar_t path[1100];swprintf(path,1100,L"%ls\\pairs.txt",ipc->path);
    FILE *f=_wfopen(path,L"r");if(!f)return 34;int a,b;full_pair_count=0;
    while(fscanf(f,"%d %d",&a,&b)==2) {
        void *old=full_find(a),*next=full_find(b);if(error)break;
        if(old==next||q((uintptr_t)old)!=q((uintptr_t)next)){error=78;break;}
        if(!full_pair_append(old,next)){error=63;break;}
    }fclose(f);if(error)return error;
    int indexed=full_index_pairs();if(indexed!=1)return indexed<0?78:32;
    swprintf(path,1100,L"%ls\\bundles.txt",ipc->path);f=_wfopen(path,L"r");if(!f)return 34;
    char name[160];int id;full_route_count=0;
    while(fscanf(f,"%159s %d",name,&id)==2) {
        if(full_route_count>=128){error=63;break;}void *o=full_find(id);if(error)break;
        if((void*)q((uintptr_t)o)!=full_bundle){error=78;break;}
        FullRoute *r=&full_routes[full_route_count++];MultiByteToWideChar(CP_UTF8,0,name,-1,r->name,160);r->next=o;
    }fclose(f);if(error)return error;
    if(!full_pair_count||!full_route_count)return 78;
    void *m=method_get(full_bundle_resource,"GetAssetBundle",0),*target=m?(void*)q((uintptr_t)m):0;
    if(target!=(void*)((uintptr_t)GetModuleHandleW(L"GameAssembly.dll")+0x1d6aba0))return 5;
    if(!full_hooked) {
        if(MH_CreateHook(target,full_get_bundle,(void**)&full_original_bundle)!=MH_OK)return 7;
        if(MH_EnableHook(target)!=MH_OK)return 7;full_hooked=1;
    }
    full_world=world();full_prepared=1;ipc->completions=full_pair_count;return 0;
}
static void *full_operations(void) {
    void *rm=call(method_get(full_addressables,"get_ResourceManager",0),0,0);
    void *cache=full_ref(rm,"m_AssetOperationCache");if(!cache){error=79;return 0;}
    void *values=call(full_method((void*)q((uintptr_t)cache),"get_Values",0),cache,0);
    void *boxed=call(full_method((void*)q((uintptr_t)values),"get_Count",0),values,0);
    unsigned n=boxed?u((uintptr_t)boxed+16):0;if(error||n>50000){error=79;return 0;}
    void *arr=full_array_new(full_operation_interface,n);if(!arr){error=32;return 0;}
    ThemeGCHandle h=theme_gcnew(arr,0);int start=0;void *args[]={arr,&start};
    call(full_method((void*)q((uintptr_t)values),"CopyTo",2),values,args);theme_gcfree(h);
    return error?0:arr;
}
static int full_keep_operation(void *o) {
    for(unsigned i=0;i<full_kept_count;i++)if(full_kept_operations[i]==o)return 1;
    if(full_kept_count>=20000){error=63;return 0;}
    void *m=full_method((void*)q((uintptr_t)o),"IncrementReferenceCount",0);
    if(!m){error=80;return 0;}call(m,o,0);if(error)return 0;
    /* Addressables reference count retains this operation and its dependencies. */
    full_kept_operations[full_kept_count++]=o;return 1;
}
static int full_record(void *target,void *field,void *old,void *next,int index) {
    if(full_change_count>=50000){error=63;return 0;}
    full_changes[full_change_count++]=(FullChange){target,field,old,next,index};return 1;
}
static unsigned full_list(void *list,int reverse,int apply) {
    if(!list)return 0;
    void *items=full_ref(list,"_items"),*sf=full_field((void*)q((uintptr_t)list),"_size");
    if(!items||!sf)return 0;
    void *elem=full_element_class((void*)q((uintptr_t)items));if(!elem||full_value_type(elem))return 0;
    unsigned n=u((uintptr_t)list+field_offset(sf));if(n>50000||n>q((uintptr_t)items+24)){error=79;return 0;}
    void *setter=full_method((void*)q((uintptr_t)list),"set_Item",2);if(!setter){error=80;return 0;}
    unsigned changed=0;
    for(unsigned i=0;i<n&&!error;i++) {
        void *o=(void*)q((uintptr_t)items+32+i*8),*next=full_map(o,reverse);
        if(o!=next){changed++;if(apply&&full_record(list,0,o,next,(int)i)){int index=(int)i;void *args[]={&index,next};call(setter,list,args);}}
    }return changed;
}
static int full_reference_field(void *f) {
    void *t=full_field_type(f);int kind=t?full_type_kind(t):0;
    if(kind==0x12||kind==0x1c||kind==0x1d||kind==0x14||kind==0x0e)return 1;
    if(kind==0x15){void *k=full_type_class(t);return k&&!full_value_type(k);}return 0;
}
static unsigned full_cache_pass(int reverse,int apply) {
    void *arr=full_operations();if(error||!arr)return 0;
    ThemeGCHandle root=theme_gcnew(arr,0);unsigned count=0;uint64_t n=q((uintptr_t)arr+24);
    for(uint64_t i=0;i<n&&!error;i++) {
        void *op=(void*)q((uintptr_t)arr+32+i*8);if(!op)continue;
        void *f=full_field((void*)q((uintptr_t)op),"<Result>k__BackingField");if(!f||!full_reference_field(f))continue;
        void *o=(void*)q((uintptr_t)op+field_offset(f));if(!o)continue;
        void *next=full_map(o,reverse);
        if(next!=o) {
            count++;
            if(apply&&full_keep_operation(op)&&full_record(op,f,o,next,-1)) {
                /* Explicit object setter accepts the object itself, not its address.
                   Verified export 0x22b630 -> 0x1c57b0 -> 0x208ab0 in this build. */
                full_field_set(op,f,next);
                if((void*)q((uintptr_t)op+field_offset(f))!=next)error=82;
            }
        }else {
            unsigned changes=full_list(o,reverse,0);count+=changes;
            if(changes&&apply&&full_keep_operation(op))full_list(o,reverse,1);
        }
    }theme_gcfree(root);return count;
}
static unsigned full_check_reference_abi(void) {
    void *arr=full_operations();if(error||!arr)return error?error:79;
    ThemeGCHandle root=theme_gcnew(arr,0);unsigned result=83;
    for(uint64_t i=0;i<q((uintptr_t)arr+24);i++) {
        void *op=(void*)q((uintptr_t)arr+32+i*8),*klass=(void*)q((uintptr_t)op);
        void *f=op?full_field(klass,"<Result>k__BackingField"):0;
        if(!f||!full_reference_field(f))continue;
        void *value=(void*)q((uintptr_t)op+field_offset(f));if(!value)continue;
        /* Plain managed operation shell, never started or inserted in any cache. */
        void *shell=full_object_new(klass);if(!shell){result=32;break;}
        ThemeGCHandle h=theme_gcnew(shell,0);full_field_set(shell,f,value);
        int valid=(void*)q((uintptr_t)shell+field_offset(f))==value;
        full_field_set(shell,f,0);valid=valid&&!q((uintptr_t)shell+field_offset(f));
        theme_gcfree(h);result=valid?0:82;break;
    }
    theme_gcfree(root);if(!result)full_abi_checked=1;ipc->completions=!result;return result;
}
static unsigned full_ui_pass(int reverse,int apply) {
    void *m=unique(theme_manager);if(error)return 0;
    unsigned count=full_list(full_ref(m,"m_styleSheets"),reverse,apply);
    void *configs=full_ref(m,"m_configsAndHandles"),*items=full_ref(configs,"_items");
    void *sz=configs?full_field((void*)q((uintptr_t)configs),"_size"):0;
    unsigned n=sz?u((uintptr_t)configs+field_offset(sz)):0;if(n>512){error=79;return count;}
    for(unsigned i=0;i<n&&!error;i++)count+=full_list(full_ref((void*)q((uintptr_t)items+32+i*8),"LoadedSheets"),reverse,apply);
    void *panels=unique(panel_class);if(!error)count+=full_list(full_ref(panels,"<Panels>k__BackingField"),reverse,apply);
    return count;
}
#include "grid_init.h"
#include "full_ui.h"
#include "full_render.h"
static unsigned full_switch(int reverse) {
    if(!full_abi_checked)return 83;
    if(!full_prepared||world()!=full_world)return 43;
    if((!reverse&&full_active)||(reverse&&!full_active))return 77;
    unsigned n=full_cache_pass(reverse,0)+full_ui_pass(reverse,0);if(error)return error;if(!n)return 81;
    unsigned grid_error=full_grid_init(reverse);if(grid_error)return grid_error;
    unsigned render_error=ui_render_install();if(render_error)return render_error;
    ui_style_hashes(reverse);if(error)return error;
    /* FM's synchronous template resolver must see the new resource cache while
       staging offscreen trees. All cache writes remain in the rollback journal. */
    ui_layer_count=0;ui_panel_count=0;
    full_change_count=0;full_active=!reverse;ipc->code=301;
    unsigned changed=full_cache_pass(reverse,1);ipc->code=302;
    if(!error)changed+=full_ui_pass(reverse,1);ipc->code=303;
    if(!error)error=ui_stage(reverse);
    if(!error)error=ui_renderer_reset();
    if(!error){ui_render_enabled=1;error=ui_commit();}
    if(!error){void *s=theme_find();if(!error)error=theme_refresh(s);}
    if(!error)error=ui_renderer_reset();
    if(error) {
        unsigned failure=error;error=0;full_active=reverse;ipc->code=304;ui_rollback();
        /* Roll back only writes recorded in this transaction, in reverse order. */
        for(unsigned i=full_change_count;i>0&&!error;i--) {
            FullChange *c=&full_changes[i-1];
            if(c->field)full_field_set(c->target,c->field,c->old);
            else {void *args[]={&c->index,c->old};call(full_method((void*)q((uintptr_t)c->target),"set_Item",2),c->target,args);}
        }
        if(!error){void *s=theme_find();if(!error)error=theme_refresh(s);}
        ui_release_pins();return error?45:failure;
    }
    ui_release_pins();ipc->completions=changed;return error;
}
static unsigned full_start(unsigned op) {
    if(ipc->path[1023]||!full_bundle||!full_operation_interface||!full_addressables||!full_bundle_resource)return 60;
    if(op==20)return full_inventory();if(op==21)return full_dump();
    if(op==28)return full_prepare();
    if(op==29){ipc->completions=full_cache_pass(0,0)+full_ui_pass(0,0);return error;}
    if(op==30)return full_switch(0);if(op==31)return full_switch(1);
    if(op==32){
        HANDLE f=CreateFileW(ipc->path,GENERIC_WRITE,0,0,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,0);
        if(f==INVALID_HANDLE_VALUE)return 33;
        char line[420];snprintf(line,sizeof(line),"{\"active\":%s,\"prepared\":%s,\"reference_check\":%s,\"bundles\":%u,\"pairs\":%u,\"route_hits\":%llu,\"retained_operations\":%u,\"deferred_render_passes\":%llu,\"released_snapshots\":%llu,\"pool_version\":1}",full_active?"true":"false",full_prepared?"true":"false",full_abi_checked?"true":"false",full_bundle_count,full_pair_count,(unsigned long long)full_hits,full_kept_count,(unsigned long long)ui_render_deferred,(unsigned long long)full_released_snapshots);
        full_put(f,line);CloseHandle(f);ipc->completions=full_hits;return error;
    }
    if(op==33)return full_check_reference_abi();
    if(op==34)return ui_inspect();
    if(full_pending)return 77;
    void *request=0;
    if(op==22) {
        if(full_bundle_count>=256)return 63;
        void *s=str_new(ipc->path,(int)wcslen(ipc->path)),*args[]={s};
        request=call(method_get(full_bundle,"LoadFromFileAsync",1),0,args);
    }else if(op==23) {
        unsigned i=(unsigned)ipc->completions;if(i>=full_bundle_count)return 61;
        full_pending_index=i;
        request=call(method_get(full_bundle,"LoadAllAssetsAsync",0),full_bundles[i],0);
    }else return 76;
    if(error||!request)return error?error:64;
    full_pending=theme_gcnew(request,0);full_pending_kind=op;return 1000;
}
static unsigned full_poll(void) {
    if(!full_pending)return 64;
    if(GetTickCount64()>active_deadline)return 21;
    if(world()!=active_world)return 22;
    void *r=theme_gctarget(full_pending),*b=call(method_get(full_async,"get_isDone",0),r,0);
    if(error)return error;if(!b||!byte((uintptr_t)b+16))return 1000;
    if(full_pending_kind==22) {
        void *bundle=call(method_get(full_bundle_request,"get_assetBundle",0),r,0);
        if(error||!bundle)return error?error:64;
        if(!full_replace_root(&full_bundle_roots[full_bundle_count],bundle))return error;
        ipc->completions=full_bundle_count;full_bundles[full_bundle_count++]=bundle;
    }else {
        void *arr=call(method_get(full_asset_request,"get_allAssets",0),r,0);
        if(error||!arr)return error?error:64;
        if(!full_replace_root(&full_asset_roots[full_pending_index],arr))return error;
        uint64_t n=q((uintptr_t)arr+24);if(n>500000)return 63;
        HANDLE f=CreateFileW(ipc->path,GENERIC_WRITE,0,0,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,0);
        if(f==INVALID_HANDLE_VALUE)return 33;
        for(uint64_t i=0;i<n&&!error;i++)full_describe(f,(void*)q((uintptr_t)arr+32+i*8));
        CloseHandle(f);ipc->completions=n;
    }
    theme_gcfree(full_pending);full_pending=0;return error;
}
