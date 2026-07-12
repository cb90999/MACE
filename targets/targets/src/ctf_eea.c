/*
 * CTF Practice: Extended Euclidean Algorithm Challenge
 * Inspired by Google Android CTF 2020 "Reverse" challenge
 *
 * The flag is verified using modular inverse via the Extended Euclidean
 * Algorithm. Each character of the flag is "encoded" and checked against
 * a table of expected values.
 *
 * Compile for ARM64 (Apple Silicon):
 *   clang -O1 -arch arm64 -o ctf_eea ctf_eea.c && strip ctf_eea
 *
 * LLDB practice:
 *   lldb ./ctf_eea
 *   (lldb) breakpoint set --name check_flag   <- before strip; after strip use addresses
 *   (lldb) run ctf{y0u_kn0w_euclid}
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/* -----------------------------------------------------------------------
 * Extended Euclidean Algorithm
 * Returns gcd(a, b) and sets *x, *y such that a*x + b*y = gcd(a,b)
 * In LLDB you'll see a0/a1 loaded with the two operands on each call.
 * ----------------------------------------------------------------------- */
static long long ext_gcd(long long a, long long b, long long *x, long long *y)
{
    if (b == 0) {
        *x = 1;
        *y = 0;
        return a;
    }
    long long x1, y1;
    long long g = ext_gcd(b, a % b, &x1, &y1);
    *x = y1;
    *y = x1 - (a / b) * y1;
    return g;
}

/* Modular inverse of a mod m using Extended GCD */
static long long mod_inv(long long a, long long m)
{
    long long x, y;
    long long g = ext_gcd(a, m, &x, &y);
    if (g != 1) return -1;          /* no inverse */
    return (x % m + m) % m;
}

/* -----------------------------------------------------------------------
 * Flag parameters
 *
 * The "encoding": for each flag character c at position i,
 *   encoded[i] = mod_inv(c + i, PRIME) * KEY % PRIME
 *
 * These were precomputed from the real flag: ctf{y0u_kn0w_euclid}
 * ----------------------------------------------------------------------- */
#define PRIME  0xFFFFFFFB           /* large prime (2^32 - 5)               */
#define KEY    0xDEADBEEF           /* mixing constant visible in registers  */

/* Flag:  c  t  f  {  y  0  u  _  k  n  0  w  _  e  u  c  l  i  d  }      */
static const uint32_t EXPECTED[] = {
    0x1EB197E8, 0xDEE50A5E, 0xBAC1ABAB, 0xAA66F758,
    0x370788B1, 0xF5B5FEC1, 0x1275F725, 0x8733E641,
    0x73777E50, 0xE19A3311, 0x9E5271A0, 0xC89AEFBB,
    0xB5853668, 0x8671CE04, 0xABB71114, 0x8671CE04,
    0x20C37737, 0x96CF103E, 0x5AD61523, 0x951A186D
};

#define FLAG_LEN  (sizeof(EXPECTED) / sizeof(EXPECTED[0]))

/* -----------------------------------------------------------------------
 * Core check — this is where LLDB magic happens.
 *
 * Set a breakpoint here (by address after strip) and watch:
 *   x0  = character value being checked
 *   x1  = position index
 *   x2  = computed encoded value
 *   x3  = expected value
 *
 * When input matches, x0 will spell out flag chars as you step.
 * ----------------------------------------------------------------------- */
static int check_flag(const char *input, size_t len)
{
    if (len != FLAG_LEN) return 0;

    /* Load the flag chars into x0..x3 one by one — visible in LLDB */
    for (size_t i = 0; i < FLAG_LEN; i++) {
        uint32_t c   = (uint8_t)input[i];          /* x0: current char      */
        uint32_t idx = (uint32_t)i;                 /* x1: index             */

        /* This computation is what you'd reverse-engineer from the binary   */
        long long base    = (long long)(c + idx);
        long long inv     = mod_inv(base, (long long)PRIME);
        uint32_t  encoded = (uint32_t)(((unsigned long long)inv * KEY) % PRIME);

        /* x2 = encoded, x3 = expected — diff goes to zero on correct char   */
        volatile uint32_t computed = encoded;       /* keep in register       */
        volatile uint32_t expected = EXPECTED[i];

        if (computed != expected) return 0;
    }
    return 1;
}

/* -----------------------------------------------------------------------
 * A secondary "reveal" path — called only on success.
 * The flag string is built char-by-char in x0 here, so even if you
 * miss check_flag you can catch it in reveal_flag via:
 *   watchpoint set variable flag_buf   (before strip)
 *   or step through the store instructions in LLDB
 * ----------------------------------------------------------------------- */
static void reveal_flag(void)
{
    /* Characters stored one per register write — watch w0 / w1 / strb */
    static const char flag[] = "ctf{y0u_kn0w_euclid}";
    volatile char flag_buf[32];
    for (size_t i = 0; i < sizeof(flag); i++) {
        flag_buf[i] = flag[i];      /* each strb is a LLDB watchpoint target */
    }
    printf("\n[+] Correct! Flag: %s\n", (const char *)flag_buf);
}

/* -----------------------------------------------------------------------
 * main — entry point; also a good breakpoint target.
 * argv[1] is loaded into x0 early; sp points to the input string.
 * ----------------------------------------------------------------------- */
int main(int argc, char *argv[])
{
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <flag_guess>\n", argv[0]);
        fprintf(stderr, "Example: %s ctf{y0u_kn0w_euclid}\n", argv[0]);
        return 1;
    }

    const char *input = argv[1];
    size_t       len   = strlen(input);

    printf("[*] Checking flag (%zu chars)...\n", len);

    /* ---- breakpoint bait ----
     * The branch to check_flag loads:
     *   x0 = pointer to input string   (you can read the flag from memory)
     *   x1 = length
     * Set:  br set -a <addr_of_bl_check_flag>
     *       then: mem read $x0 -c 32
     */
    if (check_flag(input, len)) {
        reveal_flag();
    } else {
        printf("[-] Wrong flag. Keep reversing!\n");
    }

    return 0;
}