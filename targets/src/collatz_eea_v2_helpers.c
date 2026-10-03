#define _XOPEN_SOURCE 700
#include <stdio.h>
#include <signal.h>
#include <ucontext.h>
#include <stdint.h>
#include <string.h>
#include <sys/time.h>  
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

// ═══════════════════════════════════════════════════════════
// FRIDA DETECTION
// Checks for frida-server on default port 27042
// If detected → sets flag → assembly corrupts accumulator
// Silent corruption — binary appears to run normally
// Player gets Access Denied every time with no obvious reason
// Forces player to find and understand detection mechanism
// ═══════════════════════════════════════════════════════════
static volatile int frida_detected = 0;

__attribute__((constructor))
static void check_frida(void) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return;

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons(27042);
    addr.sin_addr.s_addr = htonl(0x7F000001);  // 127.0.0.1 without string

    struct timeval tv;
    tv.tv_sec  = 0;
    tv.tv_usec = 100000;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

    if (connect(sock, (struct sockaddr*)&addr,
                sizeof(addr)) == 0) {
        frida_detected = 1;
    }
    close(sock);
}

// ═══════════════════════════════════════════════════════════
// FRIDA CORRUPTION
// Called from assembly when processing each character
// If Frida detected → corrupts x20 accumulator subtly
// Returns 1 if corrupted, 0 if clean
// Assembly checks return value and XORs noise into x20
// ═══════════════════════════════════════════════════════════
int is_frida_active(void) {
    return frida_detected;
}

// ═══════════════════════════════════════════════════════════
// SVC DISPATCH TABLE
// Maps SVC immediate → function
// SVC #0x10 → get_magic1()
// SVC #0x11 → get_prime()
// SVC #0x12 → access_granted()
// SVC #0x13 → access_denied()
// SVC #0x14 → get_magic2()
// SVC #0x15 → is_frida_active()
// ═══════════════════════════════════════════════════════════
int get_magic1(void);
long get_prime(void);
void access_granted(void);
void access_denied(void);
int get_magic2(void);

static void *dispatch_table[] = {
    (void*)get_magic1,      // SVC #0x10
    (void*)get_prime,       // SVC #0x11
    (void*)access_granted,  // SVC #0x12
    (void*)access_denied,   // SVC #0x13
    (void*)get_magic2,      // SVC #0x14
    (void*)is_frida_active, // SVC #0x15
};

// ═══════════════════════════════════════════════════════════
// SIGSYS HANDLER
// ═══════════════════════════════════════════════════════════
static void svc_handler(int sig, siginfo_t *info,
                         void *ucontext) {
    ucontext_t *uc = (ucontext_t *)ucontext;
    uint64_t pc    = uc->uc_mcontext->__ss.__pc;
    uint32_t instr = *(uint32_t *)(pc - 4);
    uint32_t svc_num = (instr >> 5) & 0xFFFF;
    uint32_t idx     = svc_num - 0x10;
    if (idx < 6) {
        typedef uint64_t (*fn_t)(void);
        fn_t fn = (fn_t)dispatch_table[idx];
        uc->uc_mcontext->__ss.__x[0] = fn();
    }
}

__attribute__((constructor))
static void install_svc_handler(void) {
    struct sigaction sa;
    sa.sa_sigaction = svc_handler;
    sa.sa_flags     = SA_SIGINFO;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGSYS, &sa, NULL);
}

// ═══════════════════════════════════════════════════════════
// get_magic1()
// Returns expected value for x20 accumulator
// magic1 = 33 = 0x21
// Obfuscated: 0x42 >> 1
// ═══════════════════════════════════════════════════════════
int get_magic1(void) {
    volatile int a = 0x42;
    volatile int b = 0x1;
    return a >> b;             // 66 >> 1 = 33
}

// ═══════════════════════════════════════════════════════════
// get_magic2()
// Returns expected value for x26 accumulator
// magic2 = 180 = 0xB4
// Obfuscated: 0xC8 - 0x14
// ═══════════════════════════════════════════════════════════
int get_magic2(void) {
    volatile int a = 0xC8;
    volatile int b = 0x14;
    return a - b;              // 200 - 20 = 180
}

// ═══════════════════════════════════════════════════════════
// get_prime()
// Returns PRIME = 0xFFFFFFFB
// ═══════════════════════════════════════════════════════════
long get_prime(void) {
    volatile long a = 0xFFFFFFFF;
    volatile long b = 0x4;
    return a - b;              // 0xFFFFFFFF - 4 = 0xFFFFFFFB
}

// ═══════════════════════════════════════════════════════════
// access_granted()
// NO FLAG IN BINARY — prints success only
// Flag must be derived from algorithm understanding
// ═══════════════════════════════════════════════════════════
void access_granted(void) {
    // XOR encrypted "Access Granted!"
    // key = 0x5C
    unsigned char enc[] = {
        0x1d,0x3f,0x3f,0x39,0x2f,0x2f,0x7c,0x1b,
        0x2e,0x3d,0x32,0x28,0x39,0x38,0x7d,0x00
    };
    for (int i = 0; enc[i]; i++) enc[i] ^= 0x5C;
    puts((char*)enc);
}

// ═══════════════════════════════════════════════════════════
// access_denied()
// XOR encrypted "Access Denied. Keep trying!"
// key = 0x5C
// ═══════════════════════════════════════════════════════════
void access_denied(void) {
    unsigned char enc[] = {
        0x1d,0x3f,0x3f,0x39,0x2f,0x2f,0x7c,0x18,
        0x39,0x32,0x35,0x39,0x38,0x72,0x7c,0x17,
        0x39,0x39,0x2c,0x7c,0x28,0x2e,0x25,0x35,
        0x32,0x3b,0x7d,0x00
    };
    for (int i = 0; enc[i]; i++) enc[i] ^= 0x5C;
    puts((char*)enc);
}
