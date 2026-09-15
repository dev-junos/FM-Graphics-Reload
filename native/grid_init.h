/* Diagnostic candidate: initialise runtime resolution data before publishing assets. */
static unsigned full_grid_initialised;
static unsigned full_grid_init(int reverse) {
    wchar_t path[1100];swprintf(path,1100,L"%ls\\grid_init_%d.jsonl",ipc->path,reverse);
    FILE *log=_wfopen(path,L"a");
    for(unsigned i=0;i<full_pair_count;i++) {
        void *next=reverse?full_pairs[i].old:full_pairs[i].next;
        void *old=reverse?full_pairs[i].next:full_pairs[i].old;
        void *k=(void*)q((uintptr_t)next);
        if(strcmp(full_namespace(k),"SI.UI")||strcmp(theme_class_name(k),"GridLayoutSettings"))continue;
        void *active=full_field(k,"<ActiveBreakpointData>k__BackingField");
        void *update=full_method(k,"UpdateActiveBreakpoint",0);
        if(!active||field_offset(active)!=0x40||!update||q((uintptr_t)update)!=(uintptr_t)GetModuleHandleW(L"GameAssembly.dll")+0x16b6f00) {
            if(log)fclose(log);return 84;
        }
        uint64_t before=q((uintptr_t)next+0x40);
        call(update,next,0);
        uint64_t after=q((uintptr_t)next+0x40);
        if(log)fprintf(log,"{\"old\":\"%p\",\"next\":\"%p\",\"old_active\":\"%llx\",\"before\":\"%llx\",\"after\":\"%llx\",\"old_listener\":\"%llx\",\"next_listener\":\"%llx\",\"error\":%u}\n",old,next,(unsigned long long)q((uintptr_t)old+0x40),(unsigned long long)before,(unsigned long long)after,(unsigned long long)q((uintptr_t)old+0x48),(unsigned long long)q((uintptr_t)next+0x48),error);
        if(error||!after){if(log)fclose(log);return error?error:84;}
        full_grid_initialised++;
    }
    if(log)fclose(log);return 0;
}
