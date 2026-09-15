#undef NDEBUG
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "../native/full_pair_index.h"

int main(void) {
    /* More than the formerly failing 40,998 links, many-to-one restoration. */
    for(unsigned round=0;round<20;round++) {
        for(unsigned i=0;i<100000;i++)assert(full_pair_append((void*)(uintptr_t)(i+1),(void*)(uintptr_t)(1000000+i/4)));
        assert(full_index_pairs()==1);
        for(unsigned i=0;i<100000;i++) {
            assert(full_map((void*)(uintptr_t)(i+1),0)==(void*)(uintptr_t)(1000000+i/4));
            assert(full_map((void*)(uintptr_t)(1000000+i/4),1)==(void*)(uintptr_t)(i/4*4+1));
        }
        assert(full_map(0,0)==0);
        assert(full_map((void*)9999999,0)==(void*)9999999);
        full_discard_pairs();assert(!full_pair_capacity&&!full_forward&&!full_reverse);
    }
    assert(full_pair_append((void*)1,(void*)3));assert(full_pair_append((void*)1,(void*)4));
    assert(full_index_pairs()==-1);full_discard_pairs();
    puts("PASS: 20 x 100000 links, restoration order, duplicate rejection, storage release");
    return 0;
}
