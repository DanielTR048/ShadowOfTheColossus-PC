/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Regression: fragmented memory operations must not stop at 64 GPU callbacks.
 * Include the implementation to exercise its locked queue without mapping a game. */
#include "../src/runtime_memory.c"
#include <assert.h>

/* Unused runtime entry points must never be reached by this isolated test. */
uintptr_t runtime_lookup(const RuntimeExport *table, size_t count, const char *nid) {
    (void)table; (void)count; (void)nid; abort();
}
#ifdef _WIN32
void compat_sleep_ns(uint64_t ns) { (void)ns; abort(); }
#endif

static size_t received;
static void record(uintptr_t address, uint64_t size) {
    assert(address==received);
    assert(size==16384);
    ++received;
    /* The GPU callback may reenter the runtime. It must run outside the lock. */
    assert(exclusive_depth==0);
    if (received==1) {
        write_lock();
        for (uintptr_t i=256;i<320;++i) queue_hook(HOOK_MAP,i,16384);
        write_unlock();
    }
}

int main(void) {
    hook_map=record;
    write_lock();
    for (uintptr_t i=0;i<256;++i) queue_hook(HOOK_MAP,i,16384);
    write_unlock();
    flush_hooks();
    assert(received==320 && pending_count==0);
    flush_hooks();
    assert(received==320);
    puts("PASS: 320 ordered GPU callbacks, including reentrant enqueue");
    return 0;
}
