// SPDX-License-Identifier: MIT
#include <stddef.h>
#include <string.h>
// Small libc operations not exported through MicroPython's native ABI.
int memcmp(const void *a, const void *b, size_t n) {
    const unsigned char *x = a, *y = b;
    while (n--) { if (*x != *y) return (int)*x - (int)*y; ++x; ++y; }
    return 0;
}
void __aeabi_memclr(void *p, size_t n) { memset(p, 0, n); }
void __aeabi_memclr4(void *p, size_t n) { memset(p, 0, n); }
void __aeabi_memclr8(void *p, size_t n) { memset(p, 0, n); }
