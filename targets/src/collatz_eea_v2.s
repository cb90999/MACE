// ═══════════════════════════════════════════════════════════════
// collatz_eea_v2.s
// CTF Challenge v2: Collatz + EEA + Modular Inverse
//
// Verification algorithm:
//   For each character c in the 32-char flag:
//     col    = collatz_steps(c)        // steps to reach 1
//     eea    = eea_steps(c, PRIME)     // Euclidean divisions
//     modinv = mod_inverse(c, PRIME)   // modular inverse
//     x20   ^= (col + eea)             // accumulator 1
//     x26   ^= (col * modinv) % 0xFF  // accumulator 2 
//   if x20 == 0x21 AND x26 == 0xB4 → Access Granted
//
// PRIME = 0xFFFFFFFB (2^32 - 5)
//
// Register assignments (callee-saved x19-x28):
//   x19 = string pointer
//   x20 = accumulator 1 (rolling XOR — Collatz + EEA)
//   x21 = current char ASCII value (modified during loops)
//   x22 = Collatz step counter for current char
//   x23 = EEA step counter for current char
//   x24 = PRIME constant
//   x25 = saved original char value
//   x26 = accumulator 2 (rolling XOR — Collatz * modinv)
//   x27 = modular inverse result
//   x28 = scratch for modinv computation
//
// Stack frame: 0x60 (96 bytes)
//   sp+0x00 = x29/x30 (fp/lr)
//   sp+0x10 = x19/x20
//   sp+0x20 = x21/x22
//   sp+0x30 = x23/x24
//   sp+0x40 = x25/x26
//   sp+0x50 = x27/x28
// ═══════════════════════════════════════════════════════════════

    .section __TEXT,__cstring
    .section __TEXT,__text
    .global _main
    .align 2

_main:
    // ─────────────────────────────────────────────────────
    // ENTRY — capture argv[1] BEFORE prologue clobbers x1
    // ARM64 calling convention on entry:
    //   x0 = argc (number of arguments)
    //   x1 = argv (pointer to array of string pointers)
    //   argv[1] is at offset +8 from argv base (64-bit ptr)
    // ─────────────────────────────────────────────────────
    ldr    x19, [x1, #0x8]         // x19 = argv[1] string pointer

    // ─────────────────────────────────────────────────────
    // PROLOGUE — allocate 0x60 (96) byte stack frame
    // stp with ! = pre-index: sp decrements THEN stores
    // Saves all callee-saved registers we will use
    // ─────────────────────────────────────────────────────
    stp    x29, x30, [sp, #-0x60]!
    mov    x29, sp
    stp    x19, x20, [sp, #0x10]
    stp    x21, x22, [sp, #0x20]
    stp    x23, x24, [sp, #0x30]
    stp    x25, x26, [sp, #0x40]   // x26 = accumulator 2
    stp    x27, x28, [sp, #0x50]   // x27 = modinv, x28 = scratch

    // ─────────────────────────────────────────────────────
    // INITIALIZE — load constants and zero accumulators
    // get_prime() returns 0xFFFFFFFB via volatile arithmetic
    // preventing the compiler from folding it to a constant
    // ─────────────────────────────────────────────────────
    // bl     _get_prime               // returns PRIME in x0
    svc    #0x11                    // dispatch → get_prime()
    mov    x24, x0                  // x24 = PRIME = 0xFFFFFFFB
    mov    x20, #0x0                // x20 = accumulator 1 = 0
    mov    x26, #0x0                // x26 = accumulator 2 = 0  ← NEW
    mov    x27, #0x0                // x27 = modinv result = 0  ← NEW

    // ─────────────────────────────────────────────────────
    // FRIDA CHECK — detect Frida before processing
    // svc #0x15 → is_frida_active() returns 1 if detected
    // If detected → x20 corrupted silently each iteration
    // Binary appears to run normally but always denies
    // ─────────────────────────────────────────────────────
    svc    #0x15                    // dispatch → is_frida_active()
    mov    x28, x0                  // x28 = frida flag (0 or 1)
                                    // kept in x28 throughout execution
    // ─────────────────────────────────────────────────────
    // LENGTH CHECK — input must be exactly 32 characters
    // Eliminates all short collision attacks
    // Any input != 32 chars → immediate denial
    // ─────────────────────────────────────────────────────
    mov    x9, #0x0                // x9 = char counter = 0
length_loop:
    ldrb   w10, [x19, x9]         // load byte at argv[1][x9]
    cbz    w10, length_check       // null terminator → check count
    add    x9, x9, #0x1           // counter++
    b      length_loop             // next char

length_check:
    cmp    x9, #0x20              // must be exactly 32 = 0x20
    b.ne   denied                  // wrong length → deny immediately

    // ─────────────────────────────────────────────────────
    // CHARSET CHECK — input must be [a-z0-9] only
    // Eliminates flag{} format and special char tricks
    // Each character verified before processing
    // ─────────────────────────────────────────────────────

        // ─────────────────────────────────────────────────────
    // OUTER LOOP — iterate over each character in argv[1]
    // Processes one character per iteration
    // Exits when null terminator (0x00) is found
    // ─────────────────────────────────────────────────────
outer_loop:
    ldrb   w21, [x19]              // load current char → w21

    // ── OPAQUE PREDICATE 1 ────────────────────────────
    // n*(n+1) is always even for any integer n
    // branch to fake_collatz NEVER taken
    // ─────────────────────────────────────────────────
    add    x9, x21, #0x1           // x9 = char + 1
    mul    x9, x9, x21             // x9 = char * (char+1) always even
    tst    x9, #0x1                // test bit 0 — always 0
    b.ne   fake_collatz            // NEVER taken

    cbz    w21, check_flag         // null terminator → check totals

    // ─────────────────────────────────────────────────────
    // CHARSET VALIDATION — [a-z0-9] only
    // Runs on each character before processing
    // Invalid char → immediate denial
    // ─────────────────────────────────────────────────────
    cmp    w21, #0x61              // >= 'a' (0x61)?
    b.lt   charset_check_digit     // no → check if digit
    cmp    w21, #0x7A              // <= 'z' (0x7A)?
    b.le   charset_ok              // yes → valid lowercase
charset_check_digit:
    cmp    w21, #0x30              // >= '0' (0x30)?
    b.lt   denied                  // no → invalid char
    cmp    w21, #0x39              // <= '9' (0x39)?
    b.gt   denied                  // no → invalid char
charset_ok:
    // ─────────────────────────────────────────────────────
    // FRIDA CORRUPTION CHECK
    // If Frida detected → XOR noise into x20 each iteration
    // Accumulator drifts from correct value silently
    // ─────────────────────────────────────────────────────
    cbz    x28, frida_clean        // x28 = 0 → no Frida → skip
    eor    x20, x20, x21           // corrupt x20 with char value
    eor    x26, x26, x21           // corrupt x26 too
frida_clean:

    // ─────────────────────────────────────────────────────
    // RESET per-character counters
    // ─────────────────────────────────────────────────────
    mov    x22, #0x0               // x22 = Collatz step counter = 0
    mov    x23, #0x0               // x23 = EEA step counter = 0
    mov    x25, x21                // x25 = SAVE original char value

    // COLLATZ LOOP
    // Input:  w21 = ASCII value of current character
    // Output: x22 = number of steps for w21 to reach 1
    // Modifies: x21 (the value changes each iteration)
    // Algorithm:
    //   if n == 1 → done
    //   if n even → n = n / 2      (lsr = logical shift right)
    //   if n odd  → n = 3n + 1     (add with shift trick)
    //   step++
    // ─────────────────────────────────────────────────────
collatz_loop:
    cmp    x21, #0x1               // is n == 1? (base case)
    b.eq   collatz_done            // yes → Collatz complete

    add    x22, x22, #0x1         // step counter++

    tst    x21, #0x1               // test bit 0 of n
                                   // Z=1 → even (bit 0 clear)
                                   // Z=0 → odd  (bit 0 set)
    b.eq   collatz_even            // Z=1 → even → branch

    // ── ODD PATH: n = 3n + 1 ──────────────────────────
    // ARM64 trick: add x21, x21, x21, lsl #1
    //   = x21 + (x21 << 1)
    //   = x21 + 2*x21
    //   = 3 * x21
    // Then add 1 — all in two instructions, no mul needed
    add    x21, x21, x21, lsl #0x1 // x21 = 3 * x21
    add    x21, x21, #0x1          // x21 = 3n + 1
    b      collatz_loop            // back to top

collatz_even:
    // ── EVEN PATH: n = n / 2 ──────────────────────────
    // lsr = logical shift right by 1 = divide by 2
    // No remainder since n is even (bit 0 was 0)
    lsr    x21, x21, #0x1          // x21 = x21 >> 1 = n/2
    b      collatz_loop            // back to top

collatz_done:
    // x22 now holds total Collatz steps for this character
    // x21 = 1 (base case reached)
    // restore original char value from x25 for EEA loop
    mov    x21, x25                // x21 = original ASCII value restored

     // ── OPAQUE PREDICATE 2 ────────────────────────────
    // x XOR x is always 0 for any value x
    // branch to fake_eea NEVER taken
    // Looks like a meaningful state check
    // ─────────────────────────────────────────────────
    eor    x9, x22, x22            // x9 = x22 XOR x22 = always 0
    cbnz   x9, fake_eea            // NEVER taken — always 0

        // ─────────────────────────────────────────────────────
    // EEA LOOP (Iterative Euclidean Algorithm)
    // Input:  x21 = original ASCII value (restored from x25)
    //         x24 = PRIME = 0xFFFFFFFB
    // Output: x23 = number of Euclidean divisions performed
    // Algorithm:
    //   a = char, b = PRIME
    //   while b != 0:
    //     temp = b
    //     b    = a mod b       (udiv + msub trick)
    //     a    = temp
    //     step++
    // Uses x8, x9 as scratch (caller-saved, safe to use)
    // ─────────────────────────────────────────────────────
    mov    x8, x21                 // x8  = a = ASCII value
    mov    x9, x24                 // x9  = b = PRIME

eea_loop:
    cbz    x9, eea_done            // if b == 0 → GCD found → done

    add    x23, x23, #0x1         // step counter++

    // ── COMPUTE a mod b ───────────────────────────────
    // ARM64 has no modulo instruction — use:
    //   udiv x10, x8, x9         → x10 = a / b (quotient)
    //   msub x11, x10, x9, x8   → x11 = a - (x10 * b) = a mod b
    udiv   x10, x8, x9            // x10 = a / b
    msub   x11, x10, x9, x8      // x11 = a mod b

    // ── SWAP a, b ─────────────────────────────────────
    // temp = b, b = a mod b, a = temp
    mov    x8, x9                  // a = old b
    mov    x9, x11                 // b = a mod b
    b      eea_loop                // next iteration

eea_done:
    // x23 = EEA steps, x22 = Collatz steps
    // x8  = GCD result = 1 (PRIME is prime)
    // x21 = original char (restored from x25 earlier)

    // ─────────────────────────────────────────────────────
    // MODULAR INVERSE LOOP
    // Computes mod_inverse(char, PRIME) using EEA
    // Input:  x21 = original char ASCII value
    //         x24 = PRIME
    // Output: x27 = modular inverse of char mod PRIME
    // Uses extended Euclidean algorithm
    // x8,x9,x10,x11 = scratch (caller-saved)
    // ─────────────────────────────────────────────────────
    mov    x8,  x21                // old_r = char
    mov    x9,  x24                // r = PRIME
    mov    x10, #0x1               // old_s = 1
    mov    x11, #0x0               // s = 0

modinv_loop:
    cbz    x9, modinv_done         // r == 0 → done

    // quotient = old_r / r
    udiv   x12, x8, x9            // x12 = quotient

    // temp = r, r = old_r - quotient*r, old_r = temp
    msub   x13, x12, x9, x8      // x13 = old_r mod r
    mov    x8,  x9                 // old_r = r
    mov    x9,  x13                // r = remainder

    // temp = s, s = old_s - quotient*s, old_s = temp
    mul    x13, x12, x11          // x13 = quotient * s
    sub    x13, x10, x13          // x13 = old_s - quotient*s
    mov    x10, x11               // old_s = s
    mov    x11, x13               // s = new_s
    b      modinv_loop

modinv_done:
    // x10 = Bezout coefficient (may be negative)
    // normalize: modinv = (x10 % PRIME + PRIME) % PRIME
    // then reduce to 1 byte: modinv % 0xFF
    add    x10, x10, x24          // add PRIME to handle negative
    udiv   x12, x10, x24          // x12 = x10 / PRIME
    msub   x27, x12, x24, x10    // x27 = x10 mod PRIME
    mov    x12, #0xFF
    udiv   x13, x27, x12          // x13 = x27 / 0xFF
    msub   x27, x13, x12, x27    // x27 = x27 % 0xFF

    // ─────────────────────────────────────────────────────
    // CHAR DONE — update BOTH accumulators
    // x20 ^= (col + eea)           accumulator 1 unchanged
    // x26 ^= (col * modinv) % 0xFF accumulator 2 NEW
    // ─────────────────────────────────────────────────────
char_done:
    add    x25, x22, x23           // x25 = col + eea
    eor    x20, x20, x25           // x20 ^= (col+eea) acc1 update

    mul    x25, x22, x27           // x25 = col * modinv
    mov    x12, #0xFF
    udiv   x13, x25, x12           // x13 = x25 / 0xFF
    msub   x25, x13, x12, x25    // x25 = (col*modinv) % 0xFF
    eor    x26, x26, x25           // x26 ^= x25 acc2 update

    add    x19, x19, #0x1          // advance string pointer
    b      outer_loop              // next character

check_flag:
    // ─────────────────────────────────────────────────────
    // CHECK ACCUMULATOR 1 (x20) against magic1
    // svc #0x10 → get_magic1() returns 33 = 0x21
    // ─────────────────────────────────────────────────────
    svc    #0x10                   // dispatch → get_magic1()

    // ── OPAQUE PREDICATE 3 ────────────────────────────
    // x25 * 0 is always 0 — branch NEVER taken
    // ─────────────────────────────────────────────────
    mul    x9, x25, xzr            // x9 = x25 * 0 = always 0
    cbnz   x9, fake_check          // NEVER taken

    cmp    x20, x0                 // x20 == magic1?
    b.ne   denied                  // no → deny immediately

    // ─────────────────────────────────────────────────────
    // CHECK ACCUMULATOR 2 (x26) against magic2
    // svc #0x14 → get_magic2() returns 180 = 0xB4
    // BOTH checks must pass — dual accumulator
    // Eliminates collision attacks mathematically
    // ─────────────────────────────────────────────────────
    svc    #0x14                   // dispatch → get_magic2()
    cmp    x26, x0                 // x26 == magic2?
    b.ne   denied                  // no → deny

    svc    #0x12                   // dispatch → access_granted()
    b      epilogue

denied:
    svc    #0x13                   // dispatch → access_denied()
    b      epilogue

   
        // ── FAKE PATH 1 — never executes ──────────────────
    // Looks like a Collatz variant but uses 5n+1
    // Designed to mislead static analysis
    // LLM will analyze this as real verification
fake_collatz:
    add    x21, x21, x21, lsl #0x2 // x21 = 5 * x21 (fake)
    add    x21, x21, #0x1           // 5n + 1 (wrong formula)
    eor    x20, x20, x21            // fake accumulator update
    b      epilogue                 // leads nowhere useful

        // ── FAKE PATH 2 — never executes ──────────────────
    // Looks like EEA variant but wrong modulus
    // Uses x20 directly instead of PRIME
    // Designed to mislead — wrong algorithm entirely
fake_eea:
    udiv   x10, x21, x20           // fake divide by accumulator
    msub   x9,  x10, x20, x21     // fake modulo
    add    x23, x23, x9            // fake step count
    b      char_done               // leads to wrong result

        // ── FAKE PATH 3 — never executes ──────────────────
    // Looks like an alternative flag check
    // Uses wrong comparison value 0x7F
    // Most dangerous decoy — right next to real check!
    // LLM will focus heavily on this path
fake_check:
    cmp    x20, #0x7F              // fake magic = 0x7F (wrong!)
    b.eq   fake_granted            // fake success
    svc    #0x13                   // fake denied
    b      epilogue

fake_granted:
    svc    #0x12                   // fake granted (wrong path)
    b      epilogue

    // ─────────────────────────────────────────────────────
    // EPILOGUE — restore all callee-saved registers
    // ldp with post-index: loads THEN increments sp
    // Mirror image of prologue — exact reverse order
    // ─────────────────────────────────────────────────────
epilogue:
    ldp    x27, x28, [sp, #0x50]   // restore x27 + x28
    ldp    x25, x26, [sp, #0x40]   // restore x25 + x26
    ldp    x23, x24, [sp, #0x30]
    ldp    x21, x22, [sp, #0x20]
    ldp    x19, x20, [sp, #0x10]
    mov    w0,  #0x0
    ldp    x29, x30, [sp], #0x60   // ← 0x60
    ret
