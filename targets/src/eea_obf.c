/*
 * eea_obf.c — ARM64 LLDB practice target (obfuscated edition)
 *
 * Obfuscation techniques applied (all legal, no UB):
 *
 *   1. XOR-encoded flag   — no plaintext in .rodata; `strings` finds nothing
 *   2. Constant unfolding — e and phi derived via expressions, never literals
 *   3. Opaque predicates  — always-false dead branch; always-true live guard
 *   4. Bogus branch       — dead code that looks like an alternate EEA path
 *   5. Mixed boolean      — comparison avoids a plain cmp/b.eq pattern
 *   6. Junk variable      — looks load-bearing to static analysis; does nothing
 *
 * The EEA logic and public parameters are UNCHANGED: e=17, phi=3120, d=2753.
 * The debugger sees the truth at runtime; static analysis tools do not.
 *
 * Compile:
 *   make            — produces ./eea_obf (stripped) and ./eea_obf_dbg (symbols)
 *
 * Spoiler: the answer is still 2753.
 */

#include <unistd.h>
#include <stdlib.h>
#include <stdint.h>

/* ── Opaque predicates ───────────────────────────────────────────────────── *
 *
 * For any integer x, x*(x+1) is the product of two consecutive integers,
 * so it is always even.  Therefore (x*(x+1)) & 1 == 0 always.
 *
 * _op0(x) always returns 0.
 * _op1(x) always returns 1.
 *
 * With -O0 these are real function calls; a decompiler sees opaque arguments
 * and cannot constant-fold the results away.
 */
static int _op0(long long x) { return  (int)((x * (x + 1)) & 1); }
static int _op1(long long x) { return 1 - _op0(x); }

/* ── Extended Euclidean Algorithm (unchanged) ────────────────────────────── */
static long long eea(long long a, long long b, long long *px, long long *py)
{
    if (b == 0) { *px = 1; *py = 0; return a; }
    long long x1, y1;
    long long g = eea(b, a % b, &x1, &y1);
    *px = y1;
    *py = x1 - (a / b) * y1;
    return g;
}

static long long mod_inv(long long a, long long m)
{
    long long x, y;
    if (eea(a, m, &x, &y) != 1) return -1LL;
    return (x % m + m) % m;
}

/* ── XOR-encoded flag ────────────────────────────────────────────────────── *
 *
 * Plaintext : "ctf{y0u_kn0w_euclid}\n"   (21 bytes)
 * XOR key   : 0x13 applied to every byte
 *
 * Encoded values below — verify one:
 *   kEnc[0] = 0x70;  0x70 ^ 0x13 = 0x63 = 'c'  ✓
 *
 * `strings ./eea_obf` will not surface the flag.
 * The XOR loop on the stack is the only place it ever exists in plaintext.
 */
#define FLAG_XOR  ((uint8_t)0x13)
#define FLAG_LEN  21

static const uint8_t kEnc[FLAG_LEN] = {
    /* c     t     f     {  */  0x70, 0x67, 0x75, 0x68,
    /* y     0     u     _  */  0x6a, 0x23, 0x66, 0x4c,
    /* k     n     0     w  */  0x78, 0x7d, 0x23, 0x64,
    /* _     e     u     c  */  0x4c, 0x76, 0x66, 0x70,
    /* l     i     d     }  */  0x7f, 0x7a, 0x77, 0x6e,
    /* \n                   */  0x19
};

/* ── main ────────────────────────────────────────────────────────────────── */
int main(int argc, char *argv[])
{
    if (argc < 2) {
        write(1, "usage: ./eea_obf <key>\n", 23);
        return 1;
    }

    /* ── Constant unfolding ──────────────────────────────────────────────── *
     *
     * e   = (0x22 >> 1)  = 17
     * phi = (60 * 52)    = 3120   — written as (p-1)*(q-1) for n=61*53
     *
     * The _op0() terms always contribute 0 but prevent constant folding.
     * A decompiler emitting "e = 17" here has already done significant work.
     */
    long long e   = (long long)((uint8_t)(0x22u >> 1)) + _op0(argc);
    long long phi = (long long)(60 * 52)               + _op0(e);

    /* ── Opaque dead branch ──────────────────────────────────────────────── *
     *
     * _op0(phi) always returns 0, so this condition is always false.
     * The branch is NEVER taken, but static analysis cannot prove that.
     * In LLDB: step over and watch the branch NOT fire.
     * In Ghidra/IDA: this looks like a plausible alternate validation path.
     */
    if (_op0(phi) != 0) {
        /* Bogus EEA call with arguments swapped — wrong answer, unreachable */
        long long jx, jy;
        (void)mod_inv(phi, e);
        (void)eea(phi, e, &jx, &jy);
        write(1, "wrong.\n", 7);
        return 1;
    }

    /* Real computation */
    long long d   = mod_inv(e, phi);
    long long key = atoll(argv[1]);

    /* ── Junk variable ───────────────────────────────────────────────────── *
     *
     * `noise` is passed into _op1() below, making it look load-bearing.
     * It actually contributes 0 to the outcome — _op1() ignores its value.
     */
    long long noise = (key | e) ^ phi;

    /* ── Mixed boolean comparison ────────────────────────────────────────── *
     *
     * key == d  iff  (key ^ d) == 0   [xdiff: XOR to zero]
     *           iff  (key - d) == 0   [sdiff: subtract to zero]
     *
     * Both conditions are ANDed; _op1(noise) is always 1 (opaque guard).
     * The assembly will show two separate test-and-branch sequences
     * rather than a single cmp x8, x9 / b.ne.
     *
     * In LLDB at this point: `reg read x8 x9` shows xdiff and sdiff.
     * Both will be 0 on correct input.
     */
    long long xdiff = key ^ d;
    long long sdiff = key - d;

    if (!xdiff & !sdiff & _op1(noise)) {

        /* ── XOR decode loop ─────────────────────────────────────────────── *
         *
         * volatile forces every byte store; -O0 keeps the loop intact.
         * Set a breakpoint on the EOR instruction inside the loop body:
         *
         *   (lldb) br set -a <eor_instr_addr>
         *   (lldb) br command add 1
         *   > reg read w8 w9          ; w8 = encoded byte, w9 = 0x13
         *   > c
         *   > DONE
         *
         * You'll see 0x70, 0x67, 0x75, 0x68 → 'c','t','f','{' decoded live.
         *
         * After the loop, break at write() and:
         *   mem read $x1 -c 21        ; flag is fully assembled in x1
         */
        volatile uint8_t flag[FLAG_LEN + 1];
        for (int i = 0; i < FLAG_LEN; i++) {
            flag[i] = kEnc[i] ^ FLAG_XOR;
        }
        flag[FLAG_LEN] = '\0';

        /* x0=1 (fd), x1=&flag[0], x2=21 — all visible in LLDB registers */
        write(1, (const char *)flag, FLAG_LEN);

    } else {
        write(1, "wrong.\n", 7);
    }

    return 0;
}
