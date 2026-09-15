/* Process-local lookup storage. No Unity object ownership or destruction. */
#include <stdlib.h>
typedef struct {void *old,*next;} FullPair;
typedef struct {uintptr_t key;void *value;unsigned order;} FullLookup;
static FullPair *full_pairs;
static unsigned full_pair_count,full_pair_capacity;
static FullLookup *full_forward,*full_reverse;

static int full_lookup_compare(const void *a,const void *b) {
    const FullLookup *x=a,*y=b;
    if(x->key!=y->key)return x->key<y->key?-1:1;
    return x->order<y->order?-1:x->order>y->order;
}
static int full_pair_append(void *old,void *next) {
    if(full_pair_count>=500000)return 0;
    if(full_pair_count==full_pair_capacity) {
        unsigned size=full_pair_capacity?full_pair_capacity*2:4096;
        if(size>500000)size=500000;
        FullPair *p=realloc(full_pairs,(size_t)size*sizeof(*p));
        if(!p)return 0;full_pairs=p;full_pair_capacity=size;
    }
    full_pairs[full_pair_count++]=(FullPair){old,next};return 1;
}
static int full_index_pairs(void) {
    FullLookup *forward=malloc((size_t)full_pair_count*sizeof(*forward));
    FullLookup *reverse=malloc((size_t)full_pair_count*sizeof(*reverse));
    if(!forward||!reverse){free(forward);free(reverse);return 0;}
    for(unsigned i=0;i<full_pair_count;i++) {
        forward[i]=(FullLookup){(uintptr_t)full_pairs[i].old,full_pairs[i].next,i};
        reverse[i]=(FullLookup){(uintptr_t)full_pairs[i].next,full_pairs[i].old,i};
    }
    qsort(forward,full_pair_count,sizeof(*forward),full_lookup_compare);
    qsort(reverse,full_pair_count,sizeof(*reverse),full_lookup_compare);
    for(unsigned i=1;i<full_pair_count;i++)if(forward[i-1].key==forward[i].key) {
        free(forward);free(reverse);return -1;
    }
    free(full_forward);free(full_reverse);full_forward=forward;full_reverse=reverse;return 1;
}
static void *full_map(void *object,int reverse) {
    if(!object)return 0;
    const FullLookup *table=reverse?full_reverse:full_forward;
    if(!table)return object;
    unsigned lo=0,hi=full_pair_count;uintptr_t key=(uintptr_t)object;
    while(lo<hi){unsigned mid=lo+(hi-lo)/2;if(table[mid].key<key)lo=mid+1;else hi=mid;}
    return lo<full_pair_count&&table[lo].key==key?table[lo].value:object;
}
static void full_discard_pairs(void) {
    free(full_pairs);free(full_forward);free(full_reverse);
    full_pairs=0;full_forward=full_reverse=0;full_pair_count=full_pair_capacity=0;
}
