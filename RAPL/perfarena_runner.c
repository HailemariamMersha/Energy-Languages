/*
 * PerfArena RAPL runner.
 *
 * A drop-in companion to the original ``RAPL/main`` tool. Rather
 * than a single pair of RAPL reads around a single ``system()``
 * call, the runner:
 *
 *   1. Samples an idle baseline for a configurable number of
 *      seconds before any benchmark work.
 *   2. Runs a configurable number of warm-up iterations to let the
 *      target runtime (JIT, GC, caches) reach steady state.
 *   3. Runs a configurable number of measurement iterations, each
 *      of which forks the benchmark command, samples the RAPL
 *      package energy counter at ~10 Hz while the child runs, and
 *      records per-iteration start / end / delta.
 *   4. Emits one JSONL row per idle / warm-up / measurement
 *      iteration to ``../<language>.jsonl``, next to the original
 *      ``<language>.csv`` file that the 2017 ``main`` tool writes.
 *
 * The row schema is deliberately flat so downstream ingestion
 * (``perfarena measurement ingest``) can load it without any
 * schema migration.
 *
 * Usage:
 *   perfarena_runner "<command>" <language> <test>
 *                    [warmup=10] [measure=20] [idle_s=5]
 *
 * The original ``main`` binary is intentionally left in place so
 * that the 2017 replication runs continue to work byte-for-byte.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>

#include "rapl.h"

#define DEFAULT_WARMUP          10
#define DEFAULT_MEASURE         20
#define DEFAULT_IDLE_SECONDS    5
#define SAMPLE_INTERVAL_US      100000   /* 100 ms, ~10 Hz */

static int msr_fd = -1;

static long long read_pkg_energy_raw(int core)
{
    if (msr_fd < 0) {
        msr_fd = open_msr(core);
    }
    if (msr_fd < 0) {
        return -1;
    }
    return read_msr(msr_fd, MSR_PKG_ENERGY_STATUS);
}

static double elapsed_ms(const struct timeval *a, const struct timeval *b)
{
    return (double)((b->tv_sec  - a->tv_sec)  * 1000.0)
         + (double)((b->tv_usec - a->tv_usec) / 1000.0);
}

static void write_row(FILE *out,
                      const char *test,
                      const char *language,
                      int iteration,
                      const char *phase,
                      double wall_ms,
                      long long rapl_start,
                      long long rapl_end,
                      long samples,
                      int exit_code)
{
    long long rapl_delta = (rapl_start >= 0 && rapl_end >= 0)
        ? (rapl_end - rapl_start)
        : -1;
    fprintf(out,
        "{"
        "\"schema_version\":1,"
        "\"test\":\"%s\","
        "\"language\":\"%s\","
        "\"iteration\":%d,"
        "\"phase\":\"%s\","
        "\"wall_ms\":%.3f,"
        "\"rapl_pkg_start_raw\":%lld,"
        "\"rapl_pkg_end_raw\":%lld,"
        "\"rapl_pkg_delta_raw\":%lld,"
        "\"samples\":%ld,"
        "\"exit_code\":%d"
        "}\n",
        test, language, iteration, phase,
        wall_ms, rapl_start, rapl_end, rapl_delta,
        samples, exit_code);
    fflush(out);
}

static int run_child_with_sampling(const char *command, long *out_samples)
{
    pid_t child = fork();
    if (child == 0) {
        execlp("sh", "sh", "-c", command, (char *)NULL);
        _exit(127);
    }
    if (child < 0) {
        perror("perfarena_runner: fork");
        return -1;
    }

    long samples = 0;
    int status = 0;
    for (;;) {
        usleep(SAMPLE_INTERVAL_US);
        /*
         * We poll the RAPL counter while the child runs so the
         * MSR read path stays warm and, in a future patch, so we
         * can emit a full sample trace. For now we only count
         * samples; the per-iteration delta is the authoritative
         * integrated-energy number.
         */
        (void)read_pkg_energy_raw(0);
        samples++;

        pid_t r = waitpid(child, &status, WNOHANG);
        if (r == child) {
            break;
        }
        if (r < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("perfarena_runner: waitpid");
            break;
        }
    }

    *out_samples = samples;
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        return -WTERMSIG(status);
    }
    return -1;
}

int main(int argc, char **argv)
{
    if (argc < 4) {
        fprintf(stderr,
            "usage: perfarena_runner \"<command>\" <language> <test> "
            "[warmup=%d] [measure=%d] [idle_s=%d]\n",
            DEFAULT_WARMUP, DEFAULT_MEASURE, DEFAULT_IDLE_SECONDS);
        return 2;
    }
    const char *command  = argv[1];
    const char *language = argv[2];
    const char *test     = argv[3];
    int warmup  = (argc > 4) ? atoi(argv[4]) : DEFAULT_WARMUP;
    int measure = (argc > 5) ? atoi(argv[5]) : DEFAULT_MEASURE;
    int idle_s  = (argc > 6) ? atoi(argv[6]) : DEFAULT_IDLE_SECONDS;

    rapl_init(0);

    char out_path[512];
    snprintf(out_path, sizeof(out_path), "../%s.jsonl", language);
    FILE *out = fopen(out_path, "a");
    if (!out) {
        perror("perfarena_runner: fopen");
        return 1;
    }

    /* --- Idle baseline --- */
    {
        struct timeval t0, t1;
        gettimeofday(&t0, NULL);
        long long rapl_start = read_pkg_energy_raw(0);
        sleep(idle_s);
        long long rapl_end = read_pkg_energy_raw(0);
        gettimeofday(&t1, NULL);
        write_row(out, test, language, 0, "idle",
                  elapsed_ms(&t0, &t1),
                  rapl_start, rapl_end, 0, 0);
    }

    /* --- Warm-up + measurement iterations --- */
    int total = warmup + measure;
    for (int i = 0; i < total; i++) {
        const char *phase = (i < warmup) ? "warmup" : "measure";

        struct timeval t0, t1;
        gettimeofday(&t0, NULL);
        long long rapl_start = read_pkg_energy_raw(0);

        long samples = 0;
        int exit_code = run_child_with_sampling(command, &samples);

        long long rapl_end = read_pkg_energy_raw(0);
        gettimeofday(&t1, NULL);

        write_row(out, test, language, i + 1, phase,
                  elapsed_ms(&t0, &t1),
                  rapl_start, rapl_end, samples, exit_code);
    }

    fclose(out);
    return 0;
}
